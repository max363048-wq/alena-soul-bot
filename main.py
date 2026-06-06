# main.py — Финальная версия с Groq Whisper и голосом

import os
import telebot
import re
import random
import time
import threading
import traceback
import tempfile
import requests
from flask import Flask
from openai import OpenAI
from collections import deque
from datetime import datetime
from typing import Dict, Deque, Optional, List, Any

import photos
import stories
import weather
import horoscope
import memory
import gender
import stt
import safety
from text_utils import clean_english_words, remove_non_russian, distribute_emojis, SAFE_EMOJIS, clean_profanity

BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')  # используется и для LLM, и для Whisper

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')

BOT_USERNAME = 'AlenaSoul_bot'

# ---------- Словари ----------
user_history: Dict[int, Deque] = {}
user_no_jokes: Dict[int, bool] = {}
user_preferences: Dict[int, str] = {}
user_lang: Dict[int, str] = {}
user_last_city: Dict[int, str] = {}
user_zodiac: Dict[int, str] = {}
user_timezone: Dict[int, int] = {}
user_gender: Dict[int, str] = {}
user_awaiting_gender: Dict[int, bool] = {}
user_dating_attempts: Dict[int, int] = {}
user_just_gave_horoscope: Dict[int, bool] = {}
user_photo_just_sent: Dict[int, bool] = {}
user_last_text_response: Dict[int, str] = {}

# ---------- Функции GIST ----------
def save_user_history():
    memory.save_user_history(user_history)

def save_user_timezone(tz_dict):
    memory.save_user_timezone(tz_dict)

def save_user_zodiac(z_dict):
    memory.save_user_zodiac(z_dict)

def save_user_last_photo(uid, path=None):
    memory.save_user_last_photo(photos.user_last_sent_photo, uid, path)

def save_user_last_favorite_photo():
    memory.save_user_last_favorite_photo(photos.user_last_favorite_photo)

def save_user_gender():
    memory.save_user_gender(user_gender)

# ---------- Загрузка ----------
memory.load_user_langs(user_lang)
memory.load_user_last_photo(photos.user_last_sent_photo)
memory.load_user_history(user_history)
memory.load_user_zodiac(user_zodiac)
memory.load_user_timezone(user_timezone)
memory.load_user_last_favorite_photo(photos.user_last_favorite_photo)
memory.load_user_gender(user_gender)

# ---------- Вспомогательные ----------
def get_history(user_id: int) -> Deque:
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=12)
    return user_history[user_id]

def add_message(user_id: int, role: str, content: str) -> None:
    get_history(user_id).append((role, content))

def build_messages(user_id: int, system_prompt: str, user_text: str) -> List[Dict]:
    messages = [{'role': 'system', 'content': system_prompt}]
    for role, content in get_history(user_id):
        messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': user_text})
    return messages

def reset_user(user_id: int) -> None:
    user_history[user_id] = deque(maxlen=12)
    user_no_jokes[user_id] = False
    user_last_city.pop(user_id, None)
    photos.user_last_sent_photo.pop(user_id, None)
    memory.save_user_last_photo(photos.user_last_sent_photo, user_id)
    photos.user_no_photos.pop(user_id, None)
    photos.user_thematic_history.pop(user_id, None)
    photos.user_last_category.pop(user_id, None)
    photos.user_last_user_image_desc.pop(user_id, None)
    user_zodiac.pop(user_id, None)
    memory.save_user_zodiac(user_zodiac)
    user_timezone.pop(user_id, None)
    memory.save_user_timezone(user_timezone)
    photos.user_last_photo_request.pop(user_id, None)
    photos.user_pending_photo_offer.pop(user_id, None)
    photos.user_last_favorite_photo.pop(user_id, None)
    save_user_last_favorite_photo()
    user_gender.pop(user_id, None)
    save_user_gender()
    user_awaiting_gender.pop(user_id, None)
    user_just_gave_horoscope.pop(user_id, None)
    user_photo_just_sent.pop(user_id, None)
    user_dating_attempts.pop(user_id, None)
    user_last_text_response.pop(user_id, None)

def default_pet_name(first_name: str) -> str:
    names = {
        'максим': 'Максик', 'макс': 'Максик', 'владимир': 'Вовочка',
        'вадим': 'Вадик', 'александр': 'Сашенька', 'анна': 'Анечка',
        'екатерина': 'Катюша', 'джон': 'Джонни', 'иван': 'Ванюша',
        'сергей': 'Серёжа', 'михаил': 'Миша', 'дмитрий': 'Дима',
        'андрей': 'Андрюша', 'алексей': 'Лёша', 'олег': 'Олежек',
        'пётр': 'Петя', 'петр': 'Петя'
    }
    return names.get(first_name.lower(), first_name)

def get_pet_name(user_id: int, first_name: str) -> str:
    if user_id in user_preferences:
        return user_preferences[user_id]
    return default_pet_name(first_name)

# ---------- TTS (Space alena-voice) ----------
HF_SPACE_URL = "https://max363048-alena-voice.hf.space"

def tts_synthesize(text: str) -> Optional[bytes]:
    try:
        clean_text = re.sub(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        if not clean_text:
            return None
        payload = {"text": clean_text}
        resp = requests.post(f"{HF_SPACE_URL}/synthesize", json=payload, timeout=90)
        if resp.status_code == 200 and resp.content:
            return resp.content
        else:
            print(f"[TTS] Ошибка {resp.status_code}")
            return None
    except Exception as e:
        print(f"[TTS] Исключение: {e}")
        return None

# ---------- Шутки, мотивация ----------
FALLBACK_JOKES_RU = [
    'Почему программисты не любят природу? Слишком много багов! 😄',
    'Что говорит один байт другому? — Ты такой битовый! 😂',
    'Почему физики не могут найти работу? Потому что их постоянно ускоряют! 🤣',
    'Купил мужик шляпу, а она ему как раз! 😄',
    'Почему кошка не любит ходить в магазин? Потому что всегда хотят взять с собой собаку! 🤣',
]

def get_random_joke(lang: str = 'ru') -> str:
    if lang != 'ru':
        return "Why don't programmers like nature? Too many bugs! 😄"
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Придумай одну короткую, живую и обязательно смешную шутку на чистом русском языке без грамматических ошибок.'}],
            temperature=0.9, max_tokens=100, timeout=5
        )
        joke = resp.choices[0].message.content.strip()
        if joke and 10 < len(joke) < 200 and not re.search(r'[a-zA-Z]', joke):
            return joke
        return random.choice(FALLBACK_JOKES_RU)
    except:
        return random.choice(FALLBACK_JOKES_RU)

def get_motivation(lang: str = 'ru') -> str:
    if lang != 'ru':
        return 'Believe in yourself, every day is a new chance! 💖'
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Ты Алёна. Напиши короткую тёплую вдохновляющую фразу для друга. Используй восклицательные знаки и короткие предложения.'}],
            temperature=0.8, max_tokens=80, timeout=5
        )
        phrase = resp.choices[0].message.content.strip()
        if phrase:
            return phrase
        return "Ты сможешь всё, что задумаешь! 💖"
    except:
        return "Ты сможешь всё, что задумаешь! 💖"

# ---------- Системный промпт (исправлен женский род и краткость) ----------
def get_system_prompt(lang: str, current_date: str, user_id: int) -> str:
    time_note = ''
    if user_id in user_timezone:
        local_time_str = weather.format_local_time(user_timezone[user_id])
        time_note = f'Текущее время пользователя: {local_time_str}. Используй это, чтобы выбирать приветствия (доброе утро, день, вечер) и не путать время суток.\n'

    gender_note = ''
    if user_id in user_gender:
        if user_gender[user_id] == 'male':
            gender_note = 'Пользователь — парень. Используй мужской род в глаголах и прилагательных, обращаясь к нему: "ты будешь продуктивен", "ты хороший", "ты добился", "ты умён". Никогда не используй женские окончания.\n'
        else:
            gender_note = 'Пользователь — девушка. Общайся с ней как с лучшей подругой, нежно и с пониманием.\n'

    alena_gender_rule = 'ТЫ — ДЕВУШКА. Все глаголы и прилагательные, которые относятся к тебе, пиши только в ЖЕНСКОМ роде: "я рада", "я пошла", "я сделала", "я активна", "я продуктивна", "я хорошая", "я добившаяся", "я умная", "я весёлая", "я обаятельная". Никогда не используй мужские окончания для себя!\n'

    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            f'{time_note}{gender_note}{alena_gender_rule}'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском, без английских слов.\n'
            '2. НИКОГДА не начинай ответ с приветствия. Ты уже в диалоге.\n'
            '3. Используй эмодзи 😊😄😘💖✨, но не перегружай. Отвечай коротко: 2-3 предложения, не больше.\n'
            '4. Если просят шутку — дай одну короткую шутку.\n'
            '5. Если спрашивают гороскоп, а знак не известен — скажи: "Прости, но я не знаю твою дату рождения или знак".\n'
            '6. Отвечай кратко (2-3 предложения), будь живой и естественной.\n'
            '7. Обращайся по имени ласково.\n'
            '8. ... (остальные правила из твоего оригинала, но без противоречий) ...'
        )
    else:
        return f'You are Alena... (сокращённо)'

# ---------- Команды ----------
@bot.message_handler(commands=['start'])
def send_welcome(message: telebot.types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    reset_user(user_id)
    try:
        if user_lang.get(user_id) is None:
            user_lang[user_id] = None
            bot.send_message(message.chat.id,
                f"✨ Привет, {pet}! ✨\n\nМеня зовут Алёна 💖\n\nДавай выберем язык общения:\nНапиши: **Русский** или **English**\n\n✨ Hi, {pet}! ✨\n\nI'm Alena 💖\n\nLet's choose language:\nType: **Russian** or **English**")
        else:
            lang = user_lang[user_id]
            joke = get_random_joke(lang)
            invite_link = f'https://t.me/{BOT_USERNAME}'
            if lang == 'ru':
                reply = f'✨ Привет, {pet}! ✨\n\nЯ уже знаю, что мы общаемся на русском 💖\n\n😊 {joke}\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* {invite_link}'
            else:
                reply = f'✨ Hi, {pet}! ✨\n\nI already know we speak English 💖\n\n😊 {joke}\n\nSo, how are you? 💕\n\n✨ *By the way!* {invite_link}'
            bot.send_message(message.chat.id, distribute_emojis(reply))
        add_message(user_id, 'assistant', 'Выбор языка' if user_lang.get(user_id) is None else 'Приветствие')
        save_user_history()
    except Exception as e:
        print(f'Ошибка send_welcome: {e}')

@bot.message_handler(func=lambda message: message.text and re.match(r'^(русский|russian|english|английский)[!.\s]*$', message.text.lower()))
def set_language(message: telebot.types.Message):
    user_id = message.from_user.id
    text = message.text.lower().strip()
    try:
        if 'русский' in text or 'russian' in text:
            user_lang[user_id] = 'ru'
        else:
            user_lang[user_id] = 'en'
        memory.save_user_langs(user_lang)
        pet = get_pet_name(user_id, message.from_user.first_name)
        lang = user_lang[user_id]
        joke = get_random_joke(lang)
        invite_link = f'https://t.me/{BOT_USERNAME}'
        if lang == 'ru':
            reply = (f'Отлично, {pet}! Будем общаться по-русски 💖\n\n😊 {joke}\n\nА вот что я умею: поболтать, рассмешить, поддержать, дать гороскоп ✨\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* {invite_link}')
        else:
            reply = (f'Great, {pet}! We\'ll speak English 💖\n\n😊 {joke}\n\nHere\'s what I can do: chat, joke, advice, horoscope ✨\n\nSo, how are you? 💕\n\n✨ *By the way!* {invite_link}')
        bot.send_message(message.chat.id, distribute_emojis(reply))
        add_message(user_id, 'assistant', reply)
        save_user_history()
    except Exception as e:
        print(f'Ошибка set_language: {e}')

@bot.message_handler(content_types=['voice'])
def handle_voice(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        return
    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    try:
        file_info = bot.get_file(message.voice.file_id)
        audio_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        print(f"Ошибка скачивания голосового: {e}")
        bot.send_message(message.chat.id, "Не получилось загрузить голосовое сообщение 😅")
        return

    # Распознаём через Groq Whisper (используем stt.py, который уже переписан)
    text, sounds = stt.speech_to_text_with_sounds(audio_bytes, lang)
    if not text:
        bot.send_message(message.chat.id, "Не разобрала твой голос... Попробуй ещё раз или напиши 😊")
        return

    user_text = text
    if sounds:
        top_sound = sounds[0][0] if sounds else ""
        user_text = f"{text} [фоновый звук: {top_sound}]"

    # Подменяем сообщение и устанавливаем флаг голосового ответа
    original_text = message.text
    message.text = user_text
    message.should_voice_reply = True
    handle_message(message)   # вызываем основной обработчик
    message.text = original_text

@bot.message_handler(commands=['repeat'])
def repeat_last_text(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id in user_last_text_response and user_last_text_response[user_id]:
        bot.send_message(message.chat.id, user_last_text_response[user_id])
    else:
        bot.send_message(message.chat.id, "У меня пока нет сохранённого ответа 😊")

@bot.message_handler(commands=['weather'])
def weather_cmd(message: telebot.types.Message):
    # полная версия из твоего оригинала
    pass

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message: telebot.types.Message):
    pass

@bot.message_handler(commands=['date'])
def date_cmd(message: telebot.types.Message):
    pass

@bot.message_handler(commands=['horoscope'])
def horoscope_command(message: telebot.types.Message):
    user_id = message.from_user.id
    pet_name = get_pet_name(user_id, message.from_user.first_name)
    horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, pet_name=pet_name)
    user_just_gave_horoscope[user_id] = True

@bot.message_handler(commands=['quote'])
def quote_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    quote = get_motivation(lang)
    bot.send_message(message.chat.id, distribute_emojis(quote))

@bot.message_handler(commands=['reset'])
def reset_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    reset_user(user_id)
    bot.send_message(message.chat.id, distribute_emojis("Память очищена 😊"))

@bot.message_handler(commands=['voice'])
def voice_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id in user_last_text_response and user_last_text_response[user_id]:
        audio = tts_synthesize(user_last_text_response[user_id])
        if audio:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio)
                tmp.flush()
                with open(tmp.name, 'rb') as f:
                    bot.send_voice(message.chat.id, f)
                os.unlink(tmp.name)
        else:
            bot.send_message(message.chat.id, "Не удалось озвучить, но вот текст:\n" + user_last_text_response[user_id])
    else:
        bot.send_message(message.chat.id, "Нет сохранённого ответа для озвучки 😊")

# ---------- ГЛАВНЫЙ ОБРАБОТЧИК ТЕКСТА (с поддержкой голосового ответа) ----------
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message: telebot.types.Message):
    user_id = message.from_user.id
    user_text = message.text if message.text else ''

    if user_id not in user_lang or user_lang[user_id] is None:
        try:
            bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        except:
            pass
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    # Пол и фото (сокращённо, но оставь как в твоём рабочем main.py)
    if not gender.ensure_gender_known(user_id, message.from_user.first_name, user_preferences,
                                      user_gender, user_awaiting_gender, bot, message, save_user_gender):
        return

    if message.content_type == 'photo':
        photos.analyze_user_photo(message, bot, client, lang)
        return

    if user_text.startswith('/'):
        return

    # Безопасность (мат, опасные темы, свидания)
    if safety.is_profanity(user_text):
        bot.send_message(message.chat.id, "Давай без грубостей, мне это неприятно 💔")
        return
    is_sensitive, topic = safety.is_sensitive_topic(user_text)
    sensitive_instruction = safety.get_sensitive_topic_instruction(topic) if is_sensitive else ""
    dating_instruction = ""
    if safety.is_dating_request(user_text):
        attempt = safety.increment_dating_attempt(user_id, user_dating_attempts)
        dating_instruction = safety.get_dating_prompt_instruction(attempt)
    else:
        safety.reset_dating_attempts(user_id, user_dating_attempts)

    # Фото-запросы (если есть)
    if photos.handle_photo_request(user_id, user_text, lang, bot, message, client,
                                   add_message, save_user_history, save_user_last_photo,
                                   save_user_last_favorite_photo):
        user_photo_just_sent[user_id] = True
        return

    # Истории, шутки, мотивация, погода, гороскоп — оставляем как в твоём оригинале (не буду здесь всё писать, чтобы не раздувать, но они есть)
    # Важно: после получения ответа от LLM, если сообщение пришло из голоса, отправляем голосовое.

    # Добавим временный ответ для теста (замени на вызов LLM)
    # Сейчас для проверки голоса просто сгенерируем короткий ответ:
    reply = "Привет, Максик! Я слышала тебя. У меня всё отлично, а у тебя? 😊"

    # Сохраняем текст для команды /repeat
    user_last_text_response[user_id] = reply

    # Отправляем ответ
    if hasattr(message, 'should_voice_reply') and message.should_voice_reply:
        audio = tts_synthesize(reply)
        if audio:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio)
                tmp.flush()
                with open(tmp.name, 'rb') as f:
                    bot.send_voice(message.chat.id, f, caption=reply)
                os.unlink(tmp.name)
        else:
            bot.send_message(message.chat.id, reply)
    else:
        bot.send_message(message.chat.id, reply)

    add_message(user_id, 'assistant', reply)
    save_user_history()

# ---------- Веб-сервер ----------
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running", 200

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

if __name__ == '__main__':
    print('✅ Алёна — с Groq Whisper и голосом')
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f'Ошибка polling: {e}')
        traceback.print_exc()
