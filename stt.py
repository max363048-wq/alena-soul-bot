# stt.py — Распознавание речи (STT) через Cloudflare Whisper + удалённый анализ звуков на Space

import os
import base64
import requests
from typing import Optional, List, Tuple

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# Адрес Space для анализа фоновых звуков (замени, если назвал по-другому)
SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

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


# ---------- Удалённая классификация фоновых звуков (через Space) ----------
def classify_sounds_remote(audio_bytes: bytes) -> List[Tuple[str, float]]:
    """
    Отправляет аудио (OGG от Telegram) на Space с YAMNet.
    Возвращает список кортежей (название_звука, вероятность).
    """
    try:
        files = {'audio': ('voice.ogg', audio_bytes, 'audio/ogg')}
        resp = requests.post(f"{SOUND_SPACE_URL}/classify", files=files, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            sounds = data.get('sounds', [])
            return [(item['label'], item['score']) for item in sounds]
        else:
            print(f"Sound Space error: {resp.status_code} - {resp.text}")
            return []
    except Exception as e:
        print(f"Ошибка вызова классификатора звуков: {e}")
        return []


# ---------- Главная функция для голосовых сообщений ----------
def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List[Tuple[str, float]]]:
    """
    Возвращает (текст_речи, список_фоновых_звуков).
    """
    text = speech_to_text(audio_bytes, lang)
    sounds = []
    if text:
        sounds = classify_sounds_remote(audio_bytes)
    return text, sounds


# ---------- Совместимость со старым интерфейсом (не используется в новом main.py, но оставим) ----------
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    """Старая функция для обратной совместимости (вызывается только если нет нового обработчика)."""
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        text, sounds = speech_to_text_with_sounds(downloaded, lang)
        if not text:
            bot.send_message(message.chat.id, "Прости, я не смогла разобрать твой голос... Может, напишешь? 😊")
            return True
        if sounds:
            top_sound = sounds[0][0] if sounds else ""
            message.text = f"{text} [фоновый звук: {top_sound}]"
        else:
            message.text = text
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
