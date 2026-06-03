import os
import re
import json
import requests
import tempfile
import time
import base64
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# Папка для моделей Piper
MODELS_DIR = Path('piper_models')
VOICE_NAME = 'ru_RU-irina-medium'
MODEL_URL = f'https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/{VOICE_NAME}.onnx'
MODEL_CONFIG_URL = f'https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/{VOICE_NAME}.onnx.json'

# Кеш для голоса (ленивая загрузка)
_piper_voice = None

# YAMNet
_YAMNET_MODEL = None

# ... (функции _load_yamnet, _get_sound_comment, _get_yamnet_class_names, speech_to_text – оставь без изменений)

# ---------- ЗАГРУЗКА МОДЕЛИ (ЛЕНИВАЯ, БЕЗ INT8) ----------
def _download_file(url, dest_path):
    if not dest_path.exists():
        print(f"Скачиваю {dest_path.name} из {url}...")
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Файл {dest_path.name} успешно скачан.")
    else:
        print(f"Файл {dest_path.name} уже существует.")

def _load_piper():
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice

    MODELS_DIR.mkdir(exist_ok=True)
    model_path = MODELS_DIR / f'{VOICE_NAME}.onnx'
    config_path = MODELS_DIR / f'{VOICE_NAME}.onnx.json'

    try:
        _download_file(MODEL_URL, model_path)
        _download_file(MODEL_CONFIG_URL, config_path)

        import piper_tts
        print("Загружаю модель Piper (обычная, без INT8)...")
        _piper_voice = piper_tts.PiperVoice(str(model_path), str(config_path))
        # Замедляем речь
        _piper_voice.config.length_scale = 1.15
        print("✅ Модель Piper успешно загружена!")
        return _piper_voice
    except Exception as e:
        print(f"❌ Ошибка загрузки Piper: {e}")
        _piper_voice = None
        return None

# ---------- ОЧИСТКА ТЕКСТА С ЭМОЦИОНАЛЬНЫМИ МАРКЕРАМИ ----------
def _prepare_text_for_piper(text: str) -> str:
    # Заменяем эмодзи на эмоциональные знаки препинания
    text = text.replace("🤗", "!!")
    text = text.replace("🥰", "!!")
    text = text.replace("😘", "...")
    text = text.replace("😊", "!")
    # Удаляем оставшиеся эмодзи и спецсимволы
    cleaned = re.sub(r'[^\w\s.,!?:;—–-]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Разбиваем длинные фразы на короткие (для интонации)
    sentences = re.split(r'(?<=[.!?…]) +', cleaned)
    return '... '.join(sentences)  # добавляем паузы между фразами

# ---------- СИНТЕЗ РЕЧИ (Piper → OGG Opus) ----------
def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    prepared_text = _prepare_text_for_piper(text)
    if not prepared_text:
        return None

    voice = _load_piper()
    if voice is not None:
        wav_path = None
        ogg_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
            voice.say_to_file(prepared_text, wav_path)
            ogg_path = tempfile.NamedTemporaryFile(suffix='.ogg', delete=False).name
            subprocess.run(
                ['ffmpeg', '-i', wav_path, '-acodec', 'libopus', '-b:a', '32k', ogg_path],
                capture_output=True, timeout=15
            )
            with open(ogg_path, 'rb') as f:
                audio = f.read()
            return audio
        except Exception as e:
            print(f"Ошибка синтеза Piper: {e}")
            return None
        finally:
            for p in [wav_path, ogg_path]:
                if p and os.path.exists(p):
                    os.unlink(p)
    else:
        # Fallback на gTTS
        try:
            from gtts import gTTS
            tts = gTTS(text=prepared_text, lang='ru', slow=False)
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                tmp_path = tmp.name
            tts.save(tmp_path)
            with open(tmp_path, 'rb') as f:
                audio = f.read()
            os.unlink(tmp_path)
            return audio
        except Exception as e:
            print(f"Ошибка gTTS: {e}")
            return None

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
