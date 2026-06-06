# main.py — финальная версия с рабочей моделью llama-3.3-70b-versatile

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
from text_utils import clean_english_words, remove_non_russian, distribute_emojis, clean_profanity

BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

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

# ---------- GIST ----------
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

# ---------- TTS ----------
HF_SPACE_URL = "https://max363048-alena-voice.hf.space"

def tts_synthesize(text: str) -> Optional[bytes]:
    try:
        clean_text = re.sub(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        if not clean_text:
            return None
        payload = {"text": clean_text}
        resp = requests.post(f"{HF_SPACE_URL}/synthesize", json=payload, timeout=30)
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
]

def get_random_joke(lang: str = 'ru') -> str:
    if lang != 'ru':
        return "Why don't programmers like nature? Too many bugs! 😄"
    try:
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': 'Придумай одну короткую смешную шутку на русском.'}],
            temperature=0.9, max_tokens=100, timeout=5
        )
        joke = resp.choices[0].message.content.strip()
        if joke:
            return joke
        return random.choice(FALLBACK_JOKES_RU)
    except:
        return random.choice(FALLBACK_JOKES_RU)

def get_motivation(lang: str = 'ru') -> str:
    if lang != 'ru':
        return 'Believe in yourself! 💖'
    try:
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': 'Напиши короткую вдохновляющую фразу на русском.'}],
            temperature=0.8, max_tokens=80, timeout=5
        )
        phrase = resp.choices[0].message.content.strip()
        if phrase:
            return phrase
        return "Ты сможешь всё! 💖"
    except:
        return "Ты сможешь всё! 💖"

# ---------- Системный промпт ----------
def get_system_prompt(lang: str, current_date: str, user_id: int) -> str:
    time_note = ''
    if user_id in user_timezone:
        local_time_str = weather.format_local_time(user_timezone[user_id])
        time_note = f'Сейчас у пользователя {local_time_str}.\n'

    gender_note = ''
    if user_id in user_gender:
        if user_gender[user_id] == 'male':
            gender_note = 'Пользователь — парень. Обращайся к нему: "ты хороший", "ты умный", "ты добился".\n'
        else:
            gender_note = 'Пользователь — девушка. Общайся нежно, как с подругой.\n'

    alena_gender_rule = 'ТЫ — ДЕВУШКА. О себе говори только в женском роде: "я рада", "я пошла", "я сделала", "я хорошая", "я весёлая", "я активна".\n'

    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            f'{time_note}{gender_note}{alena_gender_rule}'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском, без английских слов.\n'
            '2. НИКОГДА не начинай ответ с "Здравствуйте", "Привет", "Здравствуй".\n'
            '3. Используй эмодзи 😊😄💖, но не перегружай. Отвечай коротко (2-3 предложения).\n'
            '4. Если просят историю — расскажи живую историю из своей жизни (4-8 предложений).\n'
            '5. Если просят шутку — дай одну короткую шутку.\n'
            '6. Если спрашивают гороскоп — составь доброе предсказание.\n'
            '7. Обращайся к пользователю по имени ласково, но не в начале фразы.\n'
        )
    else:
        return f'You are Alena... (английская версия)'

# ---------- Команды ----------
@bot.message_handler(commands=['start'])
def send_welcome(message: telebot.types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    reset_user(user_id)
    if user_lang.get(user_id) is None:
        user_lang[user_id] = None
        bot.send_message(message.chat.id,
            f"✨ Привет, {pet}! ✨\n\nМеня зовут Алёна 💖\n\nДавай выберем язык: напиши **Русский** или **English**\n\n✨ Hi, {pet}! ✨\n\nI'm Alena 💖\n\nLet's choose language: **Russian** or **English**")
    else:
        lang = user_lang[user_id]
        joke = get_random_joke(lang)
        invite_link = f'https://t.me/{BOT_USERNAME}'
        if lang == 'ru':
            reply = f'✨ Привет, {pet}! ✨\n\nЯ уже знаю, что мы общаемся на русском 💖\n\n😊 {joke}\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* {invite_link}'
        else:
            reply = f'✨ Hi, {pet}! ✨\n\nWe speak English 💖\n\n😊 {joke}\n\nSo, how are you? 💕\n\n✨ *By the way!* {invite_link}'
        bot.send_message(message.chat.id, distribute_emojis(reply))
    add_message(user_id, 'assistant', 'start')
    save_user_history()

@bot.message_handler(func=lambda message: message.text and re.match(r'^(русский|russian|english|английский)[!.\s]*$', message.text.lower()))
def set_language(message: telebot.types.Message):
    user_id = message.from_user.id
    text = message.text.lower().strip()
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
        reply = f'Отлично, {pet}! Будем общаться по-русски 💖\n\n😊 {joke}\n\nА вот что я умею: поболтать, рассмешить, дать гороскоп, рассказать историю ✨\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* {invite_link}'
    else:
        reply = f'Great, {pet}! We\'ll speak English 💖\n\n😊 {joke}\n\nHere\'s what I can do: chat, joke, horoscope, story ✨\n\nSo, how are you? 💕\n\n✨ *By the way!* {invite_link}'
    bot.send_message(message.chat.id, distribute_emojis(reply))
    add_message(user_id, 'assistant', reply)
    save_user_history()

@bot.message_handler(content_types=['voice'])
def handle_voice(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        return
    lang = user_lang[user_id]
    try:
        file_info = bot.get_file(message.voice.file_id)
        audio_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        print(f"Ошибка скачивания голосового: {e}")
        bot.send_message(message.chat.id, "Не получилось загрузить голосовое сообщение 😅")
        return
    text, _ = stt.speech_to_text_with_sounds(audio_bytes, lang)
    if not text:
        bot.send_message(message.chat.id, "Не разобрала твой голос... Попробуй ещё раз или напиши 😊")
        return
    message.text = text
    message.should_voice_reply = True
    handle_message(message)

@bot.message_handler(commands=['repeat'])
def repeat_last_text(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id in user_last_text_response:
        bot.send_message(message.chat.id, user_last_text_response[user_id])
    else:
        bot.send_message(message.chat.id, "Нет сохранённого ответа 😊")

@bot.message_handler(commands=['weather'])
def weather_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши город: /weather Москва")
        return
    city = parts[1].strip()
    weather_data = weather.get_current_weather(city, lang)
    if weather_data:
        if 'timezone' in weather_data:
            user_timezone[user_id] = weather_data['timezone']
            memory.save_user_timezone(user_timezone)
        pet_name = get_pet_name(user_id, message.from_user.first_name)
        reply = weather.generate_natural_weather_response(city, weather_data, lang, client=client, pet_name=pet_name)
    else:
        reply = f"Не удалось получить погоду для {city}."
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message: telebot.types.Message):
    pass

@bot.message_handler(commands=['date'])
def date_cmd(message: telebot.types.Message):
    now = datetime.now()
    bot.send_message(message.chat.id, distribute_emojis(f"Сегодня {now.strftime('%d.%m.%Y')} года. 😊"))

@bot.message_handler(commands=['horoscope'])
def horoscope_command(message: telebot.types.Message):
    user_id = message.from_user.id
    pet_name = get_pet_name(user_id, message.from_user.first_name)
    horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, pet_name=pet_name)

@bot.message_handler(commands=['quote'])
def quote_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    bot.send_message(message.chat.id, get_motivation(lang))

@bot.message_handler(commands=['reset'])
def reset_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    reset_user(user_id)
    bot.send_message(message.chat.id, "Память очищена 😊")

@bot.message_handler(commands=['voice'])
def voice_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id in user_last_text_response:
        audio = tts_synthesize(user_last_text_response[user_id])
        if audio:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio)
                tmp.flush()
                with open(tmp.name, 'rb') as f:
                    bot.send_voice(message.chat.id, f)
                os.unlink(tmp.name)
        else:
            bot.send_message(message.chat.id, "Не удалось озвучить, но текст:\n" + user_last_text_response[user_id])
    else:
        bot.send_message(message.chat.id, "Нет ответа для озвучки")

# ---------- ГЛАВНЫЙ ОБРАБОТЧИК ----------
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message: telebot.types.Message):
    user_id = message.from_user.id
    user_text = message.text if message.text else ''

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    # Пол
    if not gender.ensure_gender_known(user_id, message.from_user.first_name, user_preferences,
                                      user_gender, user_awaiting_gender, bot, message, save_user_gender):
        return

    # Фото от пользователя
    if message.content_type == 'photo':
        photos.analyze_user_photo(message, bot, client, lang)
        return

    if user_text.startswith('/'):
        return

    # Безопасность
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

    # --- ЗАПРОС ФОТО ---
    if re.search(r'(покажи|покажешь|хочу увидеть|хочу посмотреть|показать|дай|есть ли у тебя|свои фото|свои фотки|фото где ты|фотки где ты|свои фотографии|альбом|покажи себя|покажи свои фото|покажи свои картинки|покажи изображение|покажи фотку|покажи фото|какие у тебя есть фото|какие есть фото)', user_text, re.IGNORECASE):
        if photos.handle_photo_request(user_id, user_text, lang, bot, message, client,
                                       add_message, save_user_history, save_user_last_photo,
                                       save_user_last_favorite_photo):
            user_photo_just_sent[user_id] = True
            return
        else:
            if photos.show_random_photo(user_id, lang, bot, message, client,
                                        add_message, save_user_history, save_user_last_photo,
                                        save_user_last_favorite_photo):
                user_photo_just_sent[user_id] = True
                return

    # --- ИСТОРИИ ---
    if re.search(r'(расскажи|поделись|придумай|дай|хочешь рассказать).*?(историю|рассказ|случай|байку|истории)\b|какую(?:-?нибудь|-?то)?\s+историю', user_text, re.IGNORECASE):
        story = stories.generate_story(user_text, user_id, lang, client, os.getenv('GIST_ID'))
        reply = story
    else:
        # Обычный диалог через Groq с повторными попытками и fallback
        add_message(user_id, 'user', user_text)
        now = datetime.now()
        current_date = now.strftime('%d.%m.%Y')
        system_prompt = get_system_prompt(lang, current_date, user_id)
        if sensitive_instruction:
            system_prompt += "\n\n" + sensitive_instruction
        if dating_instruction:
            system_prompt += "\n\n" + dating_instruction
        messages = build_messages(user_id, system_prompt, user_text)

        reply = None
        for attempt in range(2):
            try:
                print(f"[Groq] Попытка {attempt+1}, модель: llama-3.3-70b-versatile")
                resp = client.chat.completions.create(
                    model='llama-3.3-70b-versatile',
                    messages=messages,
                    temperature=0.8,
                    max_tokens=600,
                    timeout=25
                )
                reply = resp.choices[0].message.content.strip()
                reply = clean_english_words(reply)
                reply = remove_non_russian(reply)
                reply = clean_profanity(reply)
                reply = distribute_emojis(reply)
                print(f"[Groq] Успешно получен ответ: {reply[:100]}")
                break
            except Exception as e:
                print(f"[Groq] Ошибка (попытка {attempt+1}): {type(e).__name__}: {str(e)}")
                if attempt == 1:
                    # fallback: тёплый ответ, чтобы бот не молчал
                    reply = f"Привет, {pet_name}! Я тебя слышу, но сейчас что-то с моим умом. Давай просто поболтаем: {user_text[:80]}... 😊"
                else:
                    time.sleep(2)

        if reply is None:
            reply = "Не удалось сгенерировать ответ 😅"

    user_last_text_response[user_id] = reply
    add_message(user_id, 'assistant', reply)
    save_user_history()

    # Отправка ответа (голосом, если пришло голосовое)
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
    print('✅ Алёна — финальная версия с моделью llama-3.3-70b-versatile')
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f'Ошибка polling: {e}')
        traceback.print_exc()
