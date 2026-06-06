# stt.py — Распознавание речи (STT) через Cloudflare Whisper + фоновые звуки (YAMNet)

import os
import base64
import requests
import tempfile
import numpy as np
from typing import Optional, List, Tuple

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# ---------- Базовое распознавание речи ----------
def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Распознаёт речь через Cloudflare Whisper."""
    try:
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        url = f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{WHISPER_MODEL}'
        headers = {
            'Authorization': f'Bearer {CF_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {'audio': audio_base64, 'language': lang}
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        data = resp.json()
        if data.get('success'):
            return data['result'].get('text', '').strip()
        else:
            print(f"Ошибка Whisper: {data}")
            return None
    except Exception as e:
        print(f"Ошибка распознавания речи: {e}")
        return None

# ---------- Опциональная классификация фоновых звуков (YAMNet) ----------
_YAMNET = None
_VAD = None

def _load_yamnet():
    """Загружает YAMNet и VAD (один раз)."""
    global _YAMNET, _VAD
    if _YAMNET is not None:
        return
    try:
        import tensorflow_hub as hub
        import torch
        from silero_vad import load_silero_vad, get_speech_timestamps
        print("[STT] Загрузка YAMNet...")
        _YAMNET = hub.load('https://tfhub.dev/google/yamnet/1')
        print("[STT] Загрузка Silero VAD...")
        _VAD = load_silero_vad()
        print("[STT] Модели звуков загружены.")
    except Exception as e:
        print(f"[STT] Не удалось загрузить модели звуков: {e}")
        _YAMNET = False

def _convert_ogg_to_wav(ogg_bytes: bytes) -> Optional[bytes]:
    """Конвертирует OGG (Telegram) в WAV 16 kHz mono с помощью ffmpeg."""
    try:
        import subprocess
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f_in:
            f_in.write(ogg_bytes)
            in_path = f_in.name
        out_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        # ffmpeg -i input.ogg -acodec pcm_s16le -ac 1 -ar 16000 output.wav
        subprocess.run([
            'ffmpeg', '-i', in_path, '-acodec', 'pcm_s16le',
            '-ac', '1', '-ar', '16000', out_path, '-y'
        ], check=True, capture_output=True)
        with open(out_path, 'rb') as f:
            wav_bytes = f.read()
        os.unlink(in_path)
        os.unlink(out_path)
        return wav_bytes
    except Exception as e:
        print(f"[STT] Ошибка конвертации OGG->WAV: {e}")
        return None

def classify_sounds(audio_bytes: bytes, top_k: int = 3) -> List[Tuple[str, float]]:
    """
    Анализирует фоновые звуки через YAMNet.
    Возвращает список (название_звука, вероятность).
    Если модели нет или ошибка – пустой список.
    """
    _load_yamnet()
    if _YAMNET is None or _YAMNET is False:
        return []
    # Конвертируем в WAV
    wav_bytes = _convert_ogg_to_wav(audio_bytes)
    if not wav_bytes:
        return []
    try:
        import numpy as np
        from scipy.io.wavfile import read as read_wav
        import io
        # Читаем WAV из байтов
        with io.BytesIO(wav_bytes) as buf:
            sr, audio = read_wav(buf)
        if sr != 16000:
            # Простой ресэмплинг (если нужно)
            pass
        # YAMNet ожидает float32 в диапазоне [-1,1]
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        scores, _, _ = _YAMNet(audio)
        mean_scores = scores.numpy().mean(axis=0)
        class_names = _YAMNet.class_names()
        top_indices = np.argsort(mean_scores)[-top_k:][::-1]
        results = []
        # Игнорируем классы речи
        speech_classes = {
            'Speech', 'Child speech, kid speaking', 'Conversation',
            'Narration, monologue', 'Male speech, man speaking',
            'Female speech, woman speaking', 'Whispering'
        }
        for idx in top_indices:
            name = class_names[idx].decode('utf-8') if isinstance(class_names[idx], bytes) else class_names[idx]
            if name in speech_classes:
                continue
            prob = float(mean_scores[idx])
            results.append((name, prob))
        return results[:2]  # не более двух
    except Exception as e:
        print(f"[STT] Ошибка классификации звуков: {e}")
        return []

# ---------- Главная функция для голосовых сообщений ----------
def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List[Tuple[str, float]]]:
    """
    Возвращает (текст_речи, список_фоновых_звуков).
    """
    text = speech_to_text(audio_bytes, lang)
    sounds = []
    if text:
        sounds = classify_sounds(audio_bytes)
    return text, sounds

# ---------- Совместимость со старым интерфейсом (process_voice_message) ----------
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    """
    Старая функция для обратной совместимости.
    В новом коде main.py мы её не используем.
    """
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        text, sounds = speech_to_text_with_sounds(downloaded, lang)
        if not text:
            bot.send_message(message.chat.id, "Прости, я не смогла разобрать твой голос... Может, напишешь? 😊")
            return True
        # Подменяем текст и передаём в основной обработчик
        if sounds:
            top_sound = sounds[0][0] if sounds else ""
            message.text = f"{text} [фоновый звук: {top_sound}]"
        else:
            message.text = text
        # Вызываем основной обработчик
        from main import handle_message
        message.should_voice_reply = True
        handle_message(message)
        return True
    except Exception as e:
        print(f"Ошибка обработки голосового сообщения: {e}")
        try:
            bot.send_message(message.chat.id, "Что-то не так с голосовым сообщением... Попробуй ещё раз 😊")
        except:
            pass
        return True
