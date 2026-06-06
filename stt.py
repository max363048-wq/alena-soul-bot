# stt.py — распознавание речи через Cloudflare Whisper (с fallback на Groq)

import os
import base64
import requests
from typing import Optional, List, Tuple

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper-large-v3-turbo'

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

def speech_to_text_cloudflare(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    print("[STT] Cloudflare попытка...")
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
            print(f"[STT] Cloudflare распознано: {text}")
            return text
        else:
            print(f"[STT] Cloudflare ошибка: {data}")
            return None
    except Exception as e:
        print(f"[STT] Cloudflare исключение: {e}")
        return None

def speech_to_text_groq(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    print("[STT] Groq попытка...")
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
            print(f"[STT] Groq распознано: {text}")
            return text
        else:
            print(f"[STT] Groq ошибка: {resp.text}")
            return None
    except Exception as e:
        print(f"[STT] Groq исключение: {e}")
        return None

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    text = speech_to_text_cloudflare(audio_bytes, lang)
    if text:
        return text
    if GROQ_API_KEY:
        return speech_to_text_groq(audio_bytes, lang)
    return None

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

def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List[Tuple[str, float]]]:
    text = speech_to_text(audio_bytes, lang)
    sounds = []
    if text:
        sounds = classify_sounds_remote(audio_bytes)
    return text, sounds

# Для обратной совместимости
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True
