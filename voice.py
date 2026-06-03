# voice.py — Модуль голоса и слуха Алёны (Edge TTS на Space, fallback gTTS)

import os
import re
import tempfile
import base64
import requests
from typing import Optional

# ---------- НАСТРОЙКИ ----------
CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
CF_API_TOKEN = os.getenv('CF_API_TOKEN')
WHISPER_MODEL = '@cf/openai/whisper'

# Твой Hugging Face Space (должен быть обновлён на Edge TTS)
HF_SPACE_URL = "https://max363048-alena-voice.hf.space"

# ---------- ОЧИСТКА ТЕКСТА ДЛЯ TTS (сохраняем пунктуацию!) ----------
def clean_text_for_tts(text: str) -> str:
    """
    Подготавливает текст для Edge TTS:
    - заменяет некоторые эмодзи на короткие слова
    - удаляет все остальные эмодзи
    - оставляет русские/английские буквы, цифры, пробелы и знаки препинания
    """
    if not text:
        return ""

    # Заменяем часто встречающиеся эмодзи на слова (чтобы синтезатор их озвучил)
    emoji_map = {
        "😊": "улыбаюсь",
        "💖": "сердечко",
        "✨": "",
        "😄": "смеюсь",
        "😘": "чмок",
        "🥰": "обнимаю",
        "🤗": "обнимаю",
        "😅": "смеюсь",
        "😂": "смеюсь",
        "😢": "грустно",
        "😭": "плачу",
        "😉": "подмигиваю",
        "😍": "влюблена",
    }
    for emoji, word in emoji_map.items():
        if word:
            text = text.replace(emoji, f" {word} ")
        else:
            text = text.replace(emoji, " ")

    # Удаляем все остальные эмодзи (все блоки Unicode)
    text = re.sub(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]', ' ', text)

    # Разрешённые символы: буквы (рус/англ), цифры, пробелы, основные знаки препинания
    text = re.sub(r'[^а-яА-Яa-zA-Z0-9\s\.\,\!\?\:\;\-\—\"\'\(\)]', ' ', text)

    # Сжимаем множественные пробелы
    text = re.sub(r'\s+', ' ', text).strip()

    # Ограничиваем длину (Edge TTS не любит слишком длинные строки)
    if len(text) > 1000:
        text = text[:997] + "..."

    return text


# ---------- РАСПОЗНАВАНИЕ РЕЧИ (Cloudflare Whisper) ----------
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


# ---------- СИНТЕЗ РЕЧИ (Space → MP3) ----------
def text_to_speech(text: str, lang: str = 'ru') -> Optional[bytes]:
    if not text:
        return None

    clean_text = clean_text_for_tts(text)
    if not clean_text:
        print("Текст после очистки пуст")
        return None

    # Пытаемся синтезировать через Space (Edge TTS)
    try:
        print(f"[TTS] Отправка в Space: {HF_SPACE_URL}/synthesize, текст: {clean_text[:100]}...")
        resp = requests.post(
            f"{HF_SPACE_URL}/synthesize",
            json={"text": clean_text},
            timeout=45  # Edge TTS может отвечать до 30 секунд
        )
        if resp.status_code == 200 and resp.content:
            print("[TTS] Успешно получен MP3 от Space")
            return resp.content
        else:
            print(f"[TTS] Ошибка Space: код {resp.status_code}, тело: {resp.text}")
    except Exception as e:
        print(f"[TTS] Ошибка подключения к Space: {e}")

    # Fallback на gTTS (если Space недоступен)
    try:
        print("[TTS] Использую gTTS как fallback")
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
        print(f"[TTS] Ошибка gTTS: {e}")
        return None


# ---------- ОСНОВНАЯ ОБРАБОТКА ГОЛОСОВОГО СООБЩЕНИЯ ----------
def process_voice_message(message, bot, lang: str, pet_name: str) -> bool:
    """
    Возвращает True, если голосовое обработано и ответ уже отправлен,
    и False, если нужно дальше обрабатывать распознанный текст как обычное сообщение.
    """
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)

        # Распознаём речь
        text = speech_to_text(downloaded, lang)
        if not text:
            bot.send_message(message.chat.id, "Прости, я не смогла разобрать твой голос... Может, напишешь? 😊")
            return True

        # Подменяем текст сообщения и отдаём управление основному обработчику
        message.text = text
        # Избегаем циклического импорта: импортируем handle_message только когда нужно
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
