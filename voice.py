# voice.py — Модуль голоса и слуха Алёны (синтез через Cloudflare MeloTTS)

import os
import re
import json
import requests
import tempfile
import time
import base64
from typing import Optional, Tuple, List

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'
TTS_MODEL = '@cf/facebook/mms-tts'

# YAMNet (загружается один раз)
_YAMNET_MODEL = None

# ---------- ИНИЦИАЛИЗАЦИЯ YAMNet ----------
def _load_yamnet():
    global _YAMNET_MODEL
    if _YAMNET_MODEL is None:
        try:
            import tensorflow_hub as hub
            import tensorflow as tf
            _YAMNET_MODEL = hub.load('https://tfhub.dev/google/yamnet/1')
        except ImportError:
            print("⚠️ TensorFlow или TensorFlow Hub не установлены. Анализ фоновых звуков будет отключён.")
            _YAMNET_MODEL = False
    return _YAMNET_MODEL

SOUND_MAP = {
    'Bird': 'птиц',
    'Water': 'воду',
    'Wind': 'ветер',
    'Ocean': 'море',
    'Forest': 'лес',
    'Rain': 'дождь',
    'Traffic': 'городской трафик',
    'Music': 'музыку',
}
YAMNET_CLASSES_URL = 'https://raw.githubusercontent.com/nicolabernini/YAMNet/master/yamnet/yamnet_class_map.csv'

def _get_sound_comment(audio_bytes: bytes) -> str:
    model = _load_yamnet()
    if model is False:
        return ''
    try:
        import tensorflow as tf
        import csv
        import io
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        waveform, sr = tf.audio.decode_wav(tf.io.read_file(tmp_path))
        waveform = tf.squeeze(waveform, axis=-1)
        if sr != 16000:
            waveform = tf.image.resize(tf.expand_dims(waveform, 0), [16000])[0]
        scores, embeddings, spectrogram = model(waveform)
        class_names = _get_yamnet_class_names()
        mean_scores = tf.reduce_mean(scores, axis=0).numpy()
        top_idx = mean_scores.argsort()[-1]
        top_score = mean_scores[top_idx]
        top_class = class_names.get(top_idx, '')
        os.unlink(tmp_path)
        if top_score > 0.3 and top_class in SOUND_MAP:
            return f'Ой, я слышу {SOUND_MAP[top_class]}! '
    except Exception as e:
        print(f"Ошибка анализа звуков: {e}")
    return ''

def _get_yamnet_class_names() -> dict:
    try:
        resp = requests.get(YAMNET_CLASSES_URL, timeout=5)
        reader = csv.reader(io.StringIO(resp.text))
        class_names = {}
        for row in reader:
            if len(row) >= 2:
                try:
                    idx = int(row[0])
                    name = row[1].strip()
                    class_names[idx] = name
                except ValueError:
                    continue
        return class_names
    except:
        return {}

# ---------- РАСПОЗНАВАНИЕ РЕЧИ (Whisper) ----------
def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    try:
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        url = f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{WHISPER_MODEL}'
        headers = {
            'Authorization': f'Bearer {CF_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'audio': audio_base64,
            'language': lang
        }
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

# ---------- СИНТЕЗ РЕЧИ (Cloudflare MeloTTS) ----------
def text_to_speech(text: str) -> Optional[bytes]:
    try:
        url = f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{TTS_MODEL}'
        headers = {
            'Authorization': f'Bearer {CF_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'text': text,
            'language': 'rus'
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        data = resp.json()
        if data.get('success'):
            result = data.get('result', {})
            audio_base64 = result.get('audio', '')
            if audio_base64:
                return base64.b64decode(audio_base64)
        print(f"Ошибка MMS-TTS: {data}")
        return None
    except Exception as e:
        print(f"Ошибка синтеза речи: {e}")
        return None

# ---------- ОСНОВНАЯ ОБРАБОТКА ГОЛОСОВОГО СООБЩЕНИЯ ----------
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        audio_bytes = downloaded

        text = speech_to_text(audio_bytes, lang)
        if not text:
            bot.send_message(message.chat.id, "Прости, я не смогла разобрать твой голос... Может, напишешь? 😊")
            return True

        sound_comment = _get_sound_comment(audio_bytes)
        from main import handle_message
        message.text = text
        return False
    except Exception as e:
        print(f"Ошибка обработки голосового сообщения: {e}")
        try:
            bot.send_message(message.chat.id, "Что-то не так с голосовым сообщением... Попробуй ещё раз 😊")
        except:
            pass
        return True
