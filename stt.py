# stt.py — распознавание через Groq Whisper

import os
import requests
from typing import Optional, Tuple, List

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    try:
        files = {
            'file': ('voice.ogg', audio_bytes, 'audio/ogg'),
            'model': (None, 'whisper-large-v3'),
            'language': (None, lang),
            'response_format': (None, 'text'),
        }
        headers = {'Authorization': f'Bearer {GROQ_API_KEY}'}
        resp = requests.post(GROQ_WHISPER_URL, headers=headers, files=files, timeout=30)
        print(f"[STT] Groq статус: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            print(f"[STT] Распознано: {text}")
            return text
        else:
            print(f"[STT] Ошибка: {resp.text}")
            return None
    except Exception as e:
        print(f"[STT] Исключение: {e}")
        return None

def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List]:
    text = speech_to_text(audio_bytes, lang)
    return text, []

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True
