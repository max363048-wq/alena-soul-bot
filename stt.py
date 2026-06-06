# stt.py — Распознавание речи через Cloudflare Whisper (рабочая версия)

import os
import base64
import requests
from typing import Optional, List, Tuple

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper-large-v3-turbo'

# Адрес Space для анализа фоновых звуков
SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

# ---------- Базовое распознавание речи ----------
def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Распознаёт речь через Cloudflare Whisper (OGG напрямую)."""
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

# ---------- Классификация фоновых звуков (опционально) ----------
def classify_sounds_remote(audio_bytes: bytes) -> List[Tuple[str, float]]:
    try:
        files = {'audio': ('voice.ogg', audio_bytes, 'audio/ogg')}
        resp = requests.post(f"{SOUND_SPACE_URL}/classify", files=files, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            sounds = data.get('sounds', [])
            return [(item['label'], item['score']) for item in sounds]
        else:
            print(f"Sound Space error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"Ошибка классификации звуков: {e}")
        return []

# ---------- Главная функция ----------
def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List[Tuple[str, float]]]:
    text = speech_to_text(audio_bytes, lang)
    sounds = []
    if text:
        sounds = classify_sounds_remote(audio_bytes)
    return text, sounds

# Для обратной совместимости
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True
