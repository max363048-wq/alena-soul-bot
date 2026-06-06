# stt.py — Распознавание речи через Cloudflare Whisper (прямая отправка OGG)

import os
import base64
import requests
import tempfile
import subprocess
from typing import Optional, List, Tuple

print("[STT] Загрузка модуля...")

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# Проверка ffmpeg (только для Google fallback, не критично)
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

FFMPEG_OK = check_ffmpeg()
print(f"[FFmpeg] Доступен: {FFMPEG_OK}")

# Google Speech (опционально)
try:
    import speech_recognition as sr
    from pydub import AudioSegment
    GOOGLE_AVAILABLE = True
    print("[STT] Google Speech доступен")
except ImportError:
    GOOGLE_AVAILABLE = False
    print("[STT] Google Speech не установлен")

SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

def convert_ogg_to_wav(ogg_bytes: bytes) -> Optional[bytes]:
    """Конвертирует OGG в WAV (только если нужен Google)."""
    if not FFMPEG_OK:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f_in:
            f_in.write(ogg_bytes)
            in_path = f_in.name
        out_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        subprocess.run([
            'ffmpeg', '-i', in_path,
            '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
            out_path, '-y'
        ], check=True, capture_output=True)
        with open(out_path, 'rb') as f:
            wav_bytes = f.read()
        os.unlink(in_path)
        os.unlink(out_path)
        return wav_bytes
    except Exception as e:
        print(f"[convert] Ошибка: {e}")
        return None

def speech_to_text_cloudflare(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Отправляет OGG напрямую в Cloudflare Whisper."""
    print("[Cloudflare] Отправка OGG напрямую...")
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
        print(f"[Cloudflare] Статус: {resp.status_code}")
        if data.get('success'):
            text = data['result'].get('text', '').strip()
            print(f"[Cloudflare] Распознано: {text}")
            return text
        else:
            print(f"[Cloudflare] Ошибка: {data}")
            return None
    except Exception as e:
        print(f"[Cloudflare] Исключение: {e}")
        return None

def speech_to_text_google(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Fallback через Google Speech (требует WAV)."""
    if not GOOGLE_AVAILABLE or not FFMPEG_OK:
        print("[Google] Недоступен (нет библиотек или ffmpeg)")
        return None
    print("[Google] Попытка распознавания (конвертация в WAV)...")
    wav_bytes = convert_ogg_to_wav(audio_bytes)
    if not wav_bytes:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
        os.unlink(tmp_path)
        lang_code = 'ru-RU' if lang == 'ru' else 'en-US'
        text = recognizer.recognize_google(audio, language=lang_code)
        print(f"[Google] Распознано: {text}")
        return text.strip()
    except Exception as e:
        print(f"[Google] Ошибка: {e}")
        return None

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    """Сначала Cloudflare, при ошибке Google."""
    print("[STT] Запуск распознавания...")
    text = speech_to_text_cloudflare(audio_bytes, lang)
    if text:
        return text
    if GOOGLE_AVAILABLE:
        print("[STT] Cloudflare не сработал, пробуем Google...")
        text = speech_to_text_google(audio_bytes, lang)
        if text:
            return text
    print("[STT] Распознавание не удалось")
    return None

def classify_sounds_remote(audio_bytes: bytes) -> List[Tuple[str, float]]:
    try:
        files = {'audio': ('voice.ogg', audio_bytes, 'audio/ogg')}
        resp = requests.post(f"{SOUND_SPACE_URL}/classify", files=files, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [(item['label'], item['score']) for item in data.get('sounds', [])]
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

def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    return True

print("[STT] Модуль загружен.")
