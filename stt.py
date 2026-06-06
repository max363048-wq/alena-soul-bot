# stt.py — распознавание речи через собственный Space alena-stt

import os
import requests
from typing import Optional, List, Tuple

STT_SPACE_URL = "https://max363048-alena-stt.hf.space"

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """
    Отправляет аудио (OGG) на Space alena-stt и возвращает распознанный текст.
    """
    try:
        files = {'audio': ('voice.ogg', audio_bytes, 'audio/ogg')}
        resp = requests.post(f"{STT_SPACE_URL}/transcribe", files=files, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            text = data.get('text', '').strip()
            if text:
                print(f"[STT] Распознано: {text}")
                return text
            else:
                print(f"[STT] Пустой ответ от Space")
                return None
        else:
            print(f"[STT] Ошибка Space: статус {resp.status_code}, тело: {resp.text}")
            return None
    except Exception as e:
        print(f"[STT] Исключение: {e}")
        return None

def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List]:
    """
    Возвращает текст и пустой список звуков (звуки пока не анализируем).
    """
    text = speech_to_text(audio_bytes, lang)
    return text, []

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    """
    Заглушка для обратной совместимости.
    """
    return True
