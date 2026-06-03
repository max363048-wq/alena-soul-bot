# voice.py — Модуль голоса и слуха Алёны (Edge TTS, эмодзи не озвучиваются)

import os
import re
import tempfile
import base64
import requests
from typing import Optional

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

HF_SPACE_URL = "https://max363048-alena-voice.hf.space"

def clean_text_for_tts(text: str) -> str:
    """Удаляет эмодзи, оставляет буквы, цифры и знаки препинания."""
    if not text:
        return ""
    # Удаляем все эмодзи
    text = re.sub(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]', '', text)
    # Оставляем только русские/английские буквы, цифры, пробелы и пунктуацию
    text = re.sub(r'[^а-яА-Яa-zA-Z0-9\s\.\,\!\?\:\;\-\—\"\'\(\)]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 1000:
        text = text[:997] + "..."
    return text

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
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
        if data.get('success'):
            return data['result'].get('text', '').strip()
        else:
            print(f"Ошибка Whisper: {data}")
            return None
    except Exception as e:
        print(f"Ошибка распознавания речи: {e}")
        return None

def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    if not text:
        return None
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return None

    # Пробуем Space (Edge TTS)
    try:
        resp = requests.post(
            f"{HF_SPACE_URL}/synthesize",
            json={"text": clean_text},
            timeout=45
        )
        if resp.status_code == 200 and resp.content:
            return resp.content
        else:
            print(f"Space error: {resp.status_code}")
    except Exception as e:
        print(f"Space connection error: {e}")

    # Fallback gTTS
    try:
        from gtts import gTTS
        tts = gTTS(text=clean_text, lang='ru', slow=False)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        tts.save(tmp_path)
        with open(tmp_path, 'rb') as f:
            audio = f.read()
        os.unlink(tmp_path)
        return audio
    except Exception as e:
        print(f"gTTS error: {e}")
        return None

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        text = speech_to_text(downloaded, lang)
        if not text:
            bot.send_message(message.chat.id, "Не разобрала голос... Напиши, пожалуйста 😊")
            return True
        message.text = text
        from main import handle_message
        handle_message(message)
        return True
    except Exception as e:
        print(f"Voice message error: {e}")
        bot.send_message(message.chat.id, "Ошибка с голосовым сообщением 😅")
        return True
