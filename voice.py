# voice.py — Модуль голоса и слуха Алёны (синтез через Edge TTS, стабильный)

import os
import re
import json
import requests
import tempfile
import time
import base64
import asyncio
import threading
from typing import Optional, Tuple, List

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# YAMNet (загружается один раз)
_YAMNET_MODEL = None

# ... (функции _load_yamnet, _get_sound_comment, _get_yamnet_class_names – без изменений)

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

# ---------- СИНТЕЗ РЕЧИ (Edge TTS, потокобезопасный) ----------
def _run_async(coro):
    """Запускает корутину в новом event loop в отдельном потоке."""
    result = {}
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result['value'] = loop.run_until_complete(coro)
        finally:
            loop.close()
    t = threading.Thread(target=_run)
    t.start()
    t.join()
    return result.get('value')

def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    """Синтезирует голос Алёны через Microsoft Edge TTS."""
    try:
        import edge_tts
        voice = "ru-RU-DariyaNeural" if lang == 'ru' else "en-US-AriaNeural"

        async def _synthesize():
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp_path = tmp.name
            await communicate.save(tmp_path)
            with open(tmp_path, 'rb') as f:
                audio_bytes = f.read()
            os.unlink(tmp_path)
            return audio_bytes

        return _run_async(_synthesize())
    except ImportError:
        print("⚠️ edge-tts не установлен. pip install edge-tts")
        return None
    except Exception as e:
        print(f"Ошибка синтеза речи (Edge TTS): {e}")
        return None

# ... (функция process_voice_message без изменений)
