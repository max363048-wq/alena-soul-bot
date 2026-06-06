# stt.py — распознавание через свой Space alena-stt

import os
import requests
from typing import Optional, List, Tuple

STT_SPACE_URL = "https://max363048-alena-stt.hf.space"  # замени на адрес твоего Space

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    try:
        files = {'audio': ('voice.ogg', audio_bytes, 'audio/ogg')}
        resp = requests.post(f"{STT_SPACE_URL}/transcribe", files=files, timeout=30)
        data = resp.json()
        if resp.status_code == 200 and 'text' in data:
            text = data['text'].strip()
            print(f"[STT] Распознано: {text}")
            return text
        else:
            print(f"[STT] Ошибка: {data}")
            return None
    except Exception as e:
        print(f"[STT] Исключение: {e}")
        return None

def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List]:
    text = speech_to_text(audio_bytes, lang)
    return text, []

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True
