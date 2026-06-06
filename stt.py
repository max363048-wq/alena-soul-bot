# stt.py — Распознавание речи через Groq Whisper (бесплатно, быстро)

import os
import requests
from typing import Optional, List, Tuple

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Адрес Space для анализа фоновых звуков
SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Отправляет аудио (OGG) в Groq Whisper и возвращает текст."""
    try:
        # Groq принимает файл с типом audio/ogg
        files = {
            'file': ('voice.ogg', audio_bytes, 'audio/ogg'),
            'model': (None, 'whisper-large-v3'),
            'language': (None, lang),
            'response_format': (None, 'text'),
        }
        headers = {'Authorization': f'Bearer {GROQ_API_KEY}'}
        resp = requests.post(GROQ_WHISPER_URL, headers=headers, files=files, timeout=30)
        print(f"[Whisper] Статус: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text.strip()
            print(f"[Whisper] Распознано: {text}")
            return text
        else:
            print(f"[Whisper] Ошибка: {resp.text}")
            return None
    except Exception as e:
        print(f"[Whisper] Исключение: {e}")
        return None

def classify_sounds_remote(audio_bytes: bytes) -> List[Tuple[str, float]]:
    """Отправляет аудио на Space с YAMNet для классификации фоновых звуков."""
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

# Для обратной совместимости (не используется в новом main.py, но оставим)
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True
