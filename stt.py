# stt.py — Распознавание речи через Cloudflare Whisper (рабочая версия)

import os
import base64
import requests
from typing import Optional, List, Tuple

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper-large-v3-turbo'

# Адрес Space для анализа фоновых звуков (опционально, можно не использовать)
SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Распознаёт речь через Cloudflare Whisper (прямая отправка OGG)."""
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
        print(f"[STT] Cloudflare статус: {resp.status_code}")
        if data.get('success'):
            text = data['result'].get('text', '').strip()
            print(f"[STT] Распознано: {text}")
            return text
        else:
            print(f"[STT] Ошибка: {data}")
            return None
    except Exception as e:
        print(f"[STT] Исключение: {e}")
        return None

def classify_sounds_remote(audio_bytes: bytes) -> List[Tuple[str, float]]:
    """Опционально: анализ фоновых звуков (пока не используется)."""
    return []

def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List[Tuple[str, float]]]:
    text = speech_to_text(audio_bytes, lang)
    return text, []   # звуки пока игнорируем

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True
