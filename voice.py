# voice.py — Модуль голоса и слуха Алёны (Edge TTS через subprocess – стабильно)

import os
import re
import json
import requests
import tempfile
import time
import base64
import subprocess
import asyncio
from typing import Optional, Tuple, List

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# YAMNet
_YAMNET_MODEL = None

# ... (функции _load_yamnet, _get_sound_comment, _get_yamnet_class_names – оставь без изменений)

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

# ---------- ОЧИСТКА ТЕКСТА ОТ ЭМОДЗИ ----------
def _clean_text_for_tts(text: str) -> str:
    cleaned = re.sub(r'[^\w\s.,!?:;—–-]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

# ---------- СИНТЕЗ РЕЧИ (Edge TTS через subprocess) ----------
def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    """Синтезирует голос Алёны через Edge TTS в отдельном процессе."""
    text = _clean_text_for_tts(text)
    if not text:
        return None

    # Выбираем голос: русский – DariyaNeural, английский – AriaNeural
    voice = "ru-RU-DariyaNeural" if lang == 'ru' else "en-US-AriaNeural"

    # Создаём временный файл для аудио
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Запускаем edge-tts в отдельном процессе
        subprocess.run(
            ['edge-tts', '--voice', voice, '--text', text, '--write-media', tmp_path],
            capture_output=True,
            timeout=30
        )
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()
        return audio_bytes
    except Exception as e:
        print(f"Ошибка синтеза речи (edge-tts subprocess): {e}")
        return None
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ... (process_voice_message – без изменений)
