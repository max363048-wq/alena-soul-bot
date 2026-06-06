# stt.py — Только распознавание речи (STT) для Алёны

import os
import base64
import requests
from typing import Optional

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Распознаёт речь через Cloudflare Whisper."""
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

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    """
    Обрабатывает голосовое сообщение: распознаёт, подменяет message.text и вызывает handle_message.
    Возвращает True, если сообщение обработано.
    """
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        text = speech_to_text(downloaded, lang)
        if not text:
            bot.send_message(message.chat.id, "Прости, я не смогла разобрать твой голос... Может, напишешь? 😊")
            return True
        # Подменяем текст и передаём управление основному обработчику
        message.text = text
        from main import handle_message
        handle_message(message)
        return True
    except Exception as e:
        print(f"Ошибка обработки голосового сообщения: {e}")
        try:
            bot.send_message(message.chat.id, "Что-то не так с голосовым сообщением... Попробуй ещё раз 😊")
        except:
            pass
        return True
