# voice.py — Модуль голоса и слуха Алёны (gTTS, стабильный)

import os
import re
import json
import requests
import tempfile
import time
import base64
from typing import Optional, Tuple, List

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# YAMNet
_YAMNET_MODEL = None

# ... (функции _load_yamnet, _get_sound_comment, _get_yamnet_class_names, speech_to_text – оставь как в предыдущей gTTS-версии, без Silero/Piper)

# ---------- ОЧИСТКА ТЕКСТА ОТ ЭМОДЗИ ----------
def _clean_text_for_tts(text: str) -> str:
    cleaned = re.sub(r'[^\w\s.,!?:;—–-]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

# ---------- СИНТЕЗ РЕЧИ (gTTS) ----------
def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    text = _clean_text_for_tts(text)
    if not text:
        return None

    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        tts.save(tmp_path)
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()
        os.unlink(tmp_path)
        return audio_bytes
    except Exception as e:
        print(f"Ошибка синтеза речи (gTTS): {e}")
        return None

# ... (process_voice_message – без изменений)

# ---------- ОСНОВНАЯ ОБРАБОТКА ГОЛОСОВОГО СООБЩЕНИЯ ----------
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        audio_bytes = downloaded

        text = speech_to_text(audio_bytes, lang)
        if not text:
            bot.send_message(message.chat.id, "Прости, я не смогла разобрать твой голос... Может, напишешь? 😊")
            return True

        sound_comment = _get_sound_comment(audio_bytes)
        from main import handle_message
        message.text = text
        return False
    except Exception as e:
        print(f"Ошибка обработки голосового сообщения: {e}")
        try:
            bot.send_message(message.chat.id, "Что-то не так с голосовым сообщением... Попробуй ещё раз 😊")
        except:
            pass
        return True
