import os
import base64
import requests
from typing import Optional

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'  # более стабильная базовая модель

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    try:
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        url = f'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{WHISPER_MODEL}'
        headers = {
            'Authorization': f'Bearer {CF_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {'audio': audio_base64, 'language': lang}
        print(f"[STT] Отправка запроса в Cloudflare...")
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"[STT] Статус: {resp.status_code}")
        data = resp.json()
        if data.get('success'):
            text = data['result'].get('text', '').strip()
            print(f"[STT] Текст: {text}")
            return text
        else:
            print(f"[STT] Ошибка CF: {data}")
            return None
    except Exception as e:
        print(f"[STT] Исключение: {e}")
        return None

def speech_to_text_with_sounds(audio_bytes, lang='ru'):
    text = speech_to_text(audio_bytes, lang)
    return text, []

def process_voice_message(message, bot, lang, pet_name):
    return True
