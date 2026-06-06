# stt.py — Распознавание речи с диагностикой (Cloudflare + Google Fallback)

import os
import base64
import requests
import tempfile
import subprocess
from typing import Optional, List, Tuple

print("[STT] Модуль загружается...")

CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# Проверка ffmpeg
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("[FFmpeg] OK")
            return True
        else:
            print("[FFmpeg] НЕ ДОСТУПЕН")
            return False
    except FileNotFoundError:
        print("[FFmpeg] НЕ НАЙДЕН")
        return False

FFMPEG_OK = check_ffmpeg()

# Google Speech
try:
    import speech_recognition as sr
    from pydub import AudioSegment
    GOOGLE_SPEECH_AVAILABLE = True
    print("[STT] Google Speech Recognition доступен")
except ImportError as e:
    GOOGLE_SPEECH_AVAILABLE = False
    print(f"[STT] Google Speech не установлен: {e}")

SOUND_SPACE_URL = "https://max363048-alena-sound.hf.space"

def convert_ogg_to_wav(ogg_bytes: bytes) -> Optional[bytes]:
    if not FFMPEG_OK:
        print("[convert] ffmpeg не найден, конвертация невозможна")
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f_in:
            f_in.write(ogg_bytes)
            in_path = f_in.name
        out_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        cmd = ['ffmpeg', '-i', in_path, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', out_path, '-y']
        print(f"[convert] Команда: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, capture_output=True)
        with open(out_path, 'rb') as f:
            wav_bytes = f.read()
        os.unlink(in_path)
        os.unlink(out_path)
        print(f"[convert] Успешно, размер WAV: {len(wav_bytes)} байт")
        return wav_bytes
    except Exception as e:
        print(f"[convert] Ошибка: {e}")
        return None

def speech_to_text_cloudflare(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    print("[Cloudflare] Попытка распознавания...")
    wav_bytes = convert_ogg_to_wav(audio_bytes)
    if not wav_bytes:
        print("[Cloudflare] Не удалось конвертировать аудио")
        return None
    try:
        audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')
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
    if not GOOGLE_SPEECH_AVAILABLE:
        print("[Google] Библиотека не доступна")
        return None
    print("[Google] Попытка распознавания...")
    wav_bytes = convert_ogg_to_wav(audio_bytes)
    if not wav_bytes:
        print("[Google] Не удалось конвертировать аудио")
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
    except sr.UnknownValueError:
        print("[Google] Не удалось распознать речь")
        return None
    except sr.RequestError as e:
        print(f"[Google] Ошибка сервиса: {e}")
        return None
    except Exception as e:
        print(f"[Google] Исключение: {e}")
        return None

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    print("[STT] Запуск распознавания...")
    text = speech_to_text_cloudflare(audio_bytes, lang)
    if text:
        return text
    if GOOGLE_SPEECH_AVAILABLE:
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
            sounds = data.get('sounds', [])
            return [(item['label'], item['score']) for item in sounds]
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
