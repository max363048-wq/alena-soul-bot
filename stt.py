# stt.py — Распознавание речи через Google Speech (без ключей, нужен ffmpeg)

import os
import tempfile
import subprocess
import speech_recognition as sr
from pydub import AudioSegment
from typing import Optional, Tuple, List

def convert_ogg_to_wav(ogg_bytes: bytes) -> Optional[bytes]:
    """Конвертирует OGG в WAV 16 kHz mono."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f_in:
            f_in.write(ogg_bytes)
            in_path = f_in.name
        out_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        cmd = ['ffmpeg', '-i', in_path, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', out_path, '-y']
        subprocess.run(cmd, check=True, capture_output=True)
        with open(out_path, 'rb') as f:
            wav_bytes = f.read()
        os.unlink(in_path)
        os.unlink(out_path)
        return wav_bytes
    except Exception as e:
        print(f"[STT] Ошибка конвертации: {e}")
        return None

def speech_to_text(audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
    print("[STT] Распознавание через Google Speech...")
    wav = convert_ogg_to_wav(audio_bytes)
    if not wav:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(wav)
            tmp_path = tmp.name
        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
        os.unlink(tmp_path)
        lang_code = 'ru-RU' if lang == 'ru' else 'en-US'
        text = recognizer.recognize_google(audio, language=lang_code)
        print(f"[STT] Распознано: {text}")
        return text.strip()
    except sr.UnknownValueError:
        print("[STT] Речь не распознана")
    except sr.RequestError as e:
        print(f"[STT] Ошибка сервиса: {e}")
    except Exception as e:
        print(f"[STT] Исключение: {e}")
    return None

def speech_to_text_with_sounds(audio_bytes: bytes, lang: str = 'ru') -> Tuple[Optional[str], List]:
    text = speech_to_text(audio_bytes, lang)
    return text, []
