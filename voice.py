# voice.py — Модуль голоса и слуха Алёны (синтез через Microsoft Edge TTS)

import os
import re
import json
import requests
import tempfile
import time
import base64
import asyncio
from typing import Optional, Tuple, List

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# YAMNet (загружается один раз)
_YAMNET_MODEL = None

# ... (функции _load_yamnet, _get_sound_comment, _get_yamnet_class_names, speech_to_text – без изменений, как в прошлой версии)

# ---------- СИНТЕЗ РЕЧИ (Microsoft Edge TTS) ----------
def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    """Синтезирует голос Алёны через Microsoft Edge TTS (бесплатно, без API-ключей)."""
    try:
        import edge_tts
        # Выбираем голос: русский женский – ru-RU-SvetlanaNeural, английский – en-US-JennyNeural
        voice = "ru-RU-SvetlanaNeural" if lang == 'ru' else "en-US-JennyNeural"
        communicate = edge_tts.Communicate(text, voice)
        # Сохраняем аудио во временный файл
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        asyncio.run(communicate.save(tmp_path))
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()
        os.unlink(tmp_path)
        return audio_bytes
    except ImportError:
        print("⚠️ edge-tts не установлен. pip install edge-tts")
        return None
    except Exception as e:
        print(f"Ошибка синтеза речи (Edge TTS): {e}")
        return None

# ... (функция process_voice_message без изменений)
