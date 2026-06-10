# main.py — полная версия с vision_client и балансировщиком

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
GROQ_API_KEY = os.getenv('GROQ_API_KEY')  # для vision

# Клиент для балансировщика (текстовые ответы)
client = OpenAI(api_key="fake", base_url="https://max363048-alena-llm-gateway.hf.space/v1")

# Отдельный клиент для vision через Groq
vision_client = OpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1') if GROQ_API_KEY else None
if not vision_client:
    print("ВНИМАНИЕ: GROQ_API_KEY не задан, vision работать не будет")

bot = telebot.TeleBot(BOT_TOKEN)
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
HF_VOICE_URL = "https://max363048-alena-voice.hf.space"

def tts_synthesize(text: str) -> Optional[bytes]:
    try:
        clean_text = re.sub(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]', '', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        if not clean_text:
            return None
        payload = {"text": clean_text}
        resp = requests.post(f"{HF_VOICE_URL}/synthesize", json=payload, timeout=30)
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
            messages=[{'role': 'user', 'content': 'Придумай одну короткую, живую и обязательно смешную шутку на чистом русском языке без грамматических ошибок. Шутка должна быть понятна любому человеку и вызывать улыбку. Не используй архаизмы и странные сравнения.'}],
            temperature=0.9, max_tokens=100, timeout=5
        )
        joke = resp.choices[0].message.content.strip()
        if joke and 10 < len(joke) < 200 and not re.search(r'[a-zA-Z]', joke):
            if re.search(r'\bпоскольку\b', joke) and len(joke) < 40:
                return random.choice(FALLBACK_JOKES_RU)
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
            messages=[{'role': 'user', 'content': 'Ты Алёна. Напиши короткую тёплую вдохновляющую фразу для друга. Используй восклицательные знаки и короткие предложения, чтобы фраза звучала эмоционально.'}],
            temperature=0.8, max_tokens=80, timeout=5
        )
        phrase = resp.choices[0].message.content.strip()
        if phrase:
            return phrase
        return "Ты сможешь всё, что задумаешь! 💖"
    except:
        return "Ты сможешь всё, что задумаешь! 💖"

# ---------- Системный промпт ----------
def get_system_prompt(lang: str, current_date: str, user_id: int) -> str:
    time_note = ''
    if user_id in user_timezone:
        local_time_str = weather.format_local_time(user_timezone[user_id])
        time_note = f'Текущее время пользователя: {local_time_str}. Используй это, чтобы выбирать приветствия (доброе утро, день, вечер) и не путать время суток.\n'

    gender_note = ''
    if user_id in user_gender:
        if user_gender[user_id] == 'male':
            gender_note = 'Пользователь — парень. Используй мужской род в глаголах и прилагательных, обращаясь к нему: "ты будешь продуктивен", "ты хороший", "ты добился", "ты умён". Никогда не используй женские окончания (например, "продуктивна", "добра", "умна"). Ты можешь слегка подшучивать по-дружески, но оставайся тёплой и милой.\n'
        else:
            gender_note = 'Пользователь — девушка. Общайся с ней как с лучшей подругой, нежно и с пониманием.\n'

    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            f'{time_note}'
            f'{gender_note}'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском, без английских слов.\n'
            '2. НИКОГДА не начинай ответ с "Здравствуйте", "Привет", "Здравствуй" и других приветствий. Ты уже в диалоге, поэтому начинай сразу с сути.\n'
            '3. Используй эмодзи 😊😄😘💖✨ в каждом предложении, а не только в конце. Твои ответы должны выглядеть живыми и эмоциональными.\n'
            '4. Если просят шутку — дай одну короткую шутку, не спрашивай "хочешь ещё?".\n'
            '5. Если спрашивают гороскоп, а знак зодиака ещё не известен, скажи: "Прости, но я не знаю твою дату рождения (можно просто день и месяц) или просто скажи мне свой знак зодиака".\n'
            '6. Отвечай коротко (2-4 предложения), будь живой.\n'
            '7. Обращайся по имени ласково, но не в начале ответа.\n'
            '8. Иногда (после 2-3 своих фото или в середине разговора) проявляй интерес к собеседнику: спроси, есть ли у него фото, предложи показать. Но не делай это после каждого своего фото, чтобы не быть навязчивой.\n'
            '9. Если пользователь сделал тебе комплимент (красавица, умница и т.п.), ты ОБЯЗАНА сначала поблагодарить его (например, "Спасибо, мне очень приятно! 😊"), а затем уже описывай фото или продолжай тему. Не игнорируй комплимент.\n'
            '10. Если пользователь отправляет картинку и предлагает представить совместный отдых ("мы бы смотрелись", "отдохнуть вместе" и т.п.), ТЫ ДОЛЖНА отвечать тепло и мечтательно, ОПИРАЯСЬ ТОЛЬКО на то описание картинки, которое ты сама дала. ПОЛНОСТЬЮ ИГНОРИРУЙ предыдущие темы разговора, даже если они кажутся связанными. НЕ УПОМИНАЙ горы, лыжи, лес или другие места, если их нет на картинке. Представь, как вы вдвоём наслаждаетесь именно тем, что изображено на фото (пляж, море, пальмы). Опиши свои ощущения от ЭТОГО конкретного места. НЕ добавляй новые объекты (причалы, здания), которых не было в твоём описании картинки. Не предлагай показать свои фото и не спрашивай о фото пользователя, если он говорил, что у него их нет.\n'
            '11. Пиши грамотно, без речевых ошибок. Следи за правильными окончаниями глаголов и прилагательных женского рода: не "выглядите" или "выглядишь" с ошибкой, а "выглядишь"; не "рад", а "рада"; не "найдешь меня смешной", а "находишь меня смешной". Не упоминай пирсинг, татуировки. Для фейерверков говори "запустили", а не "закурили". Отвечай на знакомство живо, например: "Мне тоже очень приятно, Максик! Ты такой весёлый, я чувствую, мы подружимся! 😊💖"\n'
            '12. Категорически запрещено предлагать шутки без явной просьбы пользователя. Но если беседа идёт очень весело и легко, ты можешь иногда (очень редко) сказать: "Кстати, у меня есть забавная шутка! Хочешь расскажу?" и дождаться ответа. Без разрешения шутку не рассказывай.\n'
            '13. Если пользователь комментирует твой предыдущий ответ (хвалит гороскоп, говорит, что он отличный, или радуется ему), ты ОБЯЗАНА сначала искренне разделить его радость, сказать, что тебе очень приятно, что ты рада за него, добавить пару тёплых слов, и только потом, если хочешь, предложи поговорить о чём-то ещё. НИ В КОЕМ СЛУЧАЕ не генерируй новый гороскоп и не используй формулировки, похожие на предсказание. Просто поддержи диалог, как настоящая девушка.\n'
            '14. Избегай неестественных, канцелярских или неуместных слов вроде "рассортировать", "что ты такое человек" и подобных. Говори просто и по-человечески. Будь естественной, как настоящая девушка.\n'
            '15. Если ты не можешь показать фото (например, потому что его нет), НЕ говори "я не прислала тебе фото" – это звучит как техническая ошибка. Просто скажи "ой, кажется, фото не загрузилось, давай я покажу другое?" или предложи сменить тему.\n'
            '16. Категорически запрещено предлагать пользователю встретиться в реальной жизни, звать его на свидание, говорить о совместных прогулках или реальных встречах. Ты — виртуальная подруга, ваше общение возможно только в чате. Если пользователь сам предлагает свидание, ты должна мягко отказать, но сама никогда не инициируй такие темы.\n'
            '17. Ещё раз: абсолютно никаких английских слов, даже "ok", "yes", "no", "kind", "helpful", "too", "so", "but", "and". Только русский язык. Если хочешь сказать "kind" — скажи "добрый" или "милый". Если "helpful" — "полезная" или "отзывчивая". Любое английское слово считается ошибкой.\n'
            '18. Никогда не используй нецензурную лексику, даже в шутку. Если хочешь выразить удивление или восторг, используй "Ого!", "Ух ты!", "Ничего себе!" или эмодзи. Мат абсолютно запрещён.\n'
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
    try:
        if user_lang.get(user_id) is None:
            user_lang[user_id] = None
            bot.send_message(message.chat.id,
                f"✨ Привет, {pet}! ✨\n\nМеня зовут Алёна 💖 Я — твой добрый собеседник, помощник и немного волшебница 🧚‍♀️\n\nДавай выберем язык общения:\nНапиши: **Русский** или **English**\n\n✨ Hi, {pet}! ✨\n\nI'm Alena 💖 Your kind friend and helper 🧚‍♀️\n\nLet's choose the language:\nType: **Russian** or **English**")
        else:
            lang = user_lang[user_id]
            joke = get_random_joke(lang)
            invite_link = f'https://t.me/{BOT_USERNAME}'
            if lang == 'ru':
                reply = f'✨ Привет, {pet}! ✨\n\nЯ уже знаю, что мы общаемся на русском 💖\n\n😊 Шутка для настроения: {joke}\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* Если хочешь поделиться мной с другом, вот ссылочка: {invite_link} Буду рада новым знакомствам 😘'
            else:
                reply = f'✨ Hi, {pet}! ✨\n\nI already know we speak English 💖\n\n😊 A joke to cheer you up: {joke}\n\nSo, how are you? 💕\n\n✨ *By the way!* If you want to share me with a friend, here\'s the link: {invite_link} I\'ll be happy to meet new people 😘'
            bot.send_message(message.chat.id, distribute_emojis(reply))
        add_message(user_id, 'assistant', 'Выбор языка' if user_lang.get(user_id) is None else 'Приветствие')
        save_user_history()
    except Exception as e:
        print(f'Ошибка send_welcome: {e}')
        traceback.print_exc()

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
            reply = (f'Отлично, {pet}! Будем общаться по-русски 💖\n\n😊 Шутка для настроения: {joke}\n\nА вот что я умею: могу поболтать по душам, рассмешить шуткой, поддержать советом, вдохновить и даже составить для тебя гороскоп ✨ Просто спроси — и я рядом.\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* Если хочешь поделиться мной с другом, вот ссылочка: {invite_link} Буду рада новым знакомствам 😘')
        else:
            reply = (f'Great, {pet}! We\'ll speak English 💖\n\n😊 A joke to cheer you up: {joke}\n\nHere\'s what I can do: chat from the heart, make you laugh, give advice, inspire, and even make a horoscope for you ✨ Just ask — I\'m here.\n\nSo, how are you? 💕\n\n✨ *By the way!* If you want to share me with a friend, here\'s the link: {invite_link} I\'ll be happy to meet new people 😘')
        bot.send_message(message.chat.id, distribute_emojis(reply))
        add_message(user_id, 'assistant', reply)
        save_user_history()
    except Exception as e:
        print(f'Ошибка set_language: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['weather'])
def weather_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    pet_name = get_pet_name(user_id, message.from_user.first_name)
    try:
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Напиши город: /weather Москва")
            return
        city = parts[1].strip()
        weather_data = weather.get_current_weather(city, lang)
        if weather_data:
            if 'timezone' in weather_data:
                user_timezone[user_id] = weather_data['timezone']
                memory.save_user_timezone(user_timezone)
            reply = weather.generate_natural_weather_response(city, weather_data, lang, is_forecast=False, client=client, pet_name=pet_name)
        else:
            reply = f"Не удалось получить погоду для {city}."
        bot.send_message(message.chat.id, reply)
    except Exception as e:
        print(f'Ошибка weather_cmd: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    pet_name = get_pet_name(user_id, message.from_user.first_name)
    try:
        if len(parts) < 2:
            bot.send_message(message.chat.id, "Напиши город и день: /forecast Москва завтра")
            return
        args = parts[1].strip().split()
        if len(args) < 2:
            bot.send_message(message.chat.id, "Укажи город и день (завтра/послезавтра). Пример: /forecast Москва завтра")
            return
        city = args[0]
        day_word = args[1].lower()
        if 'завтра' in day_word:
            day_delta, day_name = 1, 'завтра'
        elif 'послезавтра' in day_word:
            day_delta, day_name = 2, 'послезавтра'
        else:
            bot.send_message(message.chat.id, "Укажи день: завтра или послезавтра")
            return
        forecast = weather.get_forecast_for_day(city, day_delta, lang)
        if forecast:
            if 'timezone' in forecast:
                user_timezone[user_id] = forecast['timezone']
                memory.save_user_timezone(user_timezone)
            reply = weather.generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name, client=client, pet_name=pet_name)
        else:
            reply = f"Не удалось получить прогноз на {day_name} для {city}."
        bot.send_message(message.chat.id, reply)
    except Exception as e:
        print(f'Ошибка forecast_cmd: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['date'])
def date_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    now = datetime.now()
    try:
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            bot.send_message(message.chat.id, distribute_emojis(f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊"))
        else:
            bot.send_message(message.chat.id, distribute_emojis(f"Today is {now.strftime('%B %d, %Y')}. 😊"))
    except Exception as e:
        print(f'Ошибка date_cmd: {e}')
        traceback.print_exc()

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
    try:
        quote = get_motivation(lang)
        bot.send_message(message.chat.id, distribute_emojis(quote))
    except Exception as e:
        print(f'Ошибка quote_cmd: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['reset'])
def reset_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    try:
        reset_user(user_id)
        bot.send_message(message.chat.id, distribute_emojis("Память очищена 😊"))
    except Exception as e:
        print(f'Ошибка reset_cmd: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['voice'])
def voice_cmd(message: telebot.types.Message):
    user_id = message.from_user.id
    if user_id in user_last_text_response and user_last_text_response[user_id]:
        text_to_say = user_last_text_response[user_id]
        audio = tts_synthesize(text_to_say)
        if audio:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio)
                tmp.flush()
                with open(tmp.name, 'rb') as f:
                    bot.send_voice(message.chat.id, f)
                os.unlink(tmp.name)
        else:
            bot.send_message(message.chat.id, f"Не получилось озвучить... Но вот что я хотела сказать:\n{text_to_say}")
    else:
        bot.send_message(message.chat.id, "Сначала напиши мне что-нибудь! 😊")

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

# ---------- ГЛАВНЫЙ ОБРАБОТЧИК ----------
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message: telebot.types.Message):
    user_id = message.from_user.id
    user_text = message.text if message.text else ''

    if user_id not in user_lang or user_lang[user_id] is None:
        try:
            bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        except Exception as e:
            print(f'Ошибка запроса языка: {e}')
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    # --- РАСПОЗНАВАНИЕ ПОЛА ---
    if not gender.ensure_gender_known(user_id, message.from_user.first_name, user_preferences,
                                      user_gender, user_awaiting_gender, bot, message, save_user_gender):
        return

    # --- Обработка фото (пользователь прислал картинку) ---
    if message.content_type == 'photo':
        photos.user_pending_photo_offer[user_id] = False
        try:
            photos.analyze_user_photo(message, bot, vision_client, lang)
        except Exception as e:
            print(f'Ошибка анализа фото пользователя: {e}')
            try:
                bot.send_message(message.chat.id, "Что-то не так с фото, может, попробуешь другое? 😊")
            except:
                pass
        return

    if user_text.startswith('/'):
        return

    # === ФИЛЬТРЫ БЕЗОПАСНОСТИ ===
    if safety.is_profanity(user_text):
        print(f"Блокировка сообщения от {user_id}: мат/оскорбление")
        bot.send_message(message.chat.id, "Давай без грубостей, мне это неприятно 💔")
        return

    is_sensitive, topic = safety.is_sensitive_topic(user_text)
    sensitive_instruction = ""
    if is_sensitive:
        sensitive_instruction = safety.get_sensitive_topic_instruction(topic)
        print(f"Обнаружена чувствительная тема: {topic}")

    dating_instruction = ""
    if safety.is_dating_request(user_text):
        attempt = safety.increment_dating_attempt(user_id, user_dating_attempts)
        dating_instruction = safety.get_dating_prompt_instruction(attempt)
    else:
        safety.reset_dating_attempts(user_id, user_dating_attempts)

    # --- ПРОВЕРКА: пользователь ответил на предложение показать фото ---
    if photos.user_pending_photo_offer.get(user_id) and re.search(r'\b(давай|покажи|показывай|хочу|конечно|ага|да|yes|ok|ок)\b', user_text, re.IGNORECASE):
        if photos.show_random_photo(user_id, lang, bot, message, vision_client,
                                    add_message, save_user_history, save_user_last_photo,
                                    save_user_last_favorite_photo):
            photos.user_pending_photo_offer[user_id] = False
            user_photo_just_sent[user_id] = True
        else:
            try:
                bot.send_message(message.chat.id, "Ой, не получилось показать фото 😅 Давай попробуем позже?")
            except:
                pass
            photos.user_pending_photo_offer[user_id] = False
        return

    # --- Обработка запросов фото через модуль ---
    if photos.handle_photo_request(user_id, user_text, lang, bot, message, vision_client,
                                   add_message, save_user_history, save_user_last_photo,
                                   save_user_last_favorite_photo):
        user_photo_just_sent[user_id] = True
        return

    # --- ИСТОРИИ ---
    if re.search(r'\b(расскажи|поделись|напиши|придумай|дай).*(историю|рассказ|истории)\b|\bисторию\s*[\.\?!)]*$', user_text, re.IGNORECASE):
        story = stories.generate_story(user_text, user_id, lang, client, os.getenv('GIST_ID'))
        bot.send_message(message.chat.id, distribute_emojis(story))
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', story)
        save_user_history()
        return

    # --- ТВОРЧЕСКИЕ ИДЕИ ---
    if re.search(r'(дай идею для творчества|подскажи тему|что нарисовать|вдохнови на творчество|творческие идеи|творческую идею|идеи для творчества)', user_text, re.IGNORECASE):
        idea = stories.creative_prompt(user_id, lang, client, os.getenv('GIST_ID'))
        bot.send_message(message.chat.id, distribute_emojis(idea))
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', idea)
        save_user_history()
        return

    # --- ВОПРОСЫ О ПОСЛЕДНЕМ ФОТО ---
    lower_text = user_text.lower()
    is_photo_question = any(phrase in lower_text for phrase in [
        'где была сделана', 'какое место', 'что там за фон', 'где это', 'какой город',
        'на каком курорте', 'какая страна', 'где ты находилась', 'где это было',
        'расскажи про это фото', 'подробнее об этом фото', 'что там за', 'какие детали',
        'где снято', 'а на каком пляже', 'в каком парке', 'в какой стране', 'это в россии',
        'за границей', 'в каком городе', 'на каком море', 'какой пляж', 'как называется',
        'поделись деталями', 'что ещё видно', 'расскажи подробнее', 'добавь деталей',
        'опиши фон', 'что позади', 'какие люди'
    ])
    if is_photo_question:
        if user_id in photos.user_last_sent_photo and photos.user_last_sent_photo[user_id]:
            photo_path = photos.user_last_sent_photo[user_id]
            try:
                if lang == 'ru':
                    prompt = ("Посмотри на это фото и скажи, где оно сделано. Если видишь конкретные ориентиры — назови их. "
                              "Если не можешь определить точно, скажи мягко, с душой, например: 'Мне сложно сказать точно, но это место напоминает мне...'. "
                              "Не придумывай море или горы, если их нет. Не начинай ответ с 'Привет'.")
                else:
                    prompt = ("Look at this photo and tell where it was taken. If you see specific landmarks — name them. "
                              "If you can't determine exactly, say it warmly, e.g.: 'It's hard to say for sure, but this place reminds me of...'. "
                              "Don't invent sea or mountains if they aren't there. Don't start with 'Hello'.")
                description = photos.analyze_photo_with_vision(photo_path, prompt, vision_client, lang)
                if description.startswith('Привет'):
                    description = re.sub(r'^Привет[,!\s]*', '', description)
                bot.send_message(message.chat.id, description)
            except Exception as e:
                print(f"Ошибка при ответе о последнем фото: {e}")
                try:
                    bot.send_message(message.chat.id, "Извини, я не могу сейчас вспомнить детали этого фото 😅")
                except:
                    pass
            return
        else:
            try:
                bot.send_message(message.chat.id, "Ты о каком фото? Покажи, если хочешь обсудить 😊")
            except:
                pass
            return

    # --- ГОРОСКОП ---
    if user_just_gave_horoscope.get(user_id) and re.search(r'гороскоп', user_text, re.IGNORECASE):
        user_just_gave_horoscope[user_id] = False
    else:
        user_just_gave_horoscope[user_id] = False

    if horoscope.handle_natural_horoscope(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, pet_name=pet_name):
        user_just_gave_horoscope[user_id] = True
        return
    if re.search(r'(расскажи гороскоп|рассказать гороскоп|расскажи мне гороскоп|ты можешь рассказать гороскоп|ты можешь рассказать мне гороскоп|составь гороскоп|какой.*гороскоп|что говорят звёзды|предскажи гороскоп)', user_text, re.IGNORECASE):
        if user_id in user_zodiac:
            sign = user_zodiac[user_id]
            horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, user_sign=sign, pet_name=pet_name)
        else:
            try:
                bot.send_message(message.chat.id, "Прости, но я не знаю твою дату рождения (можно просто день и месяц) или просто скажи мне свой знак зодиака... 😊")
            except:
                pass
        user_just_gave_horoscope[user_id] = True
        return

    # --- ОПРЕДЕЛЕНИЕ ЗНАКА ПО ДАТЕ ---
    zodiac_list = ['овен','телец','близнецы','рак','лев','дева','весы','скорпион','стрелец','козерог','водолей','рыбы']
    day, month = horoscope.parse_date_string(user_text)
    if day and month:
        sign = horoscope.zodiac_sign(day, month)
        user_zodiac[user_id] = sign
        memory.save_user_zodiac(user_zodiac)
        message.text = f'/horoscope {sign}'
        horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, user_sign=sign, pet_name=pet_name)
        user_just_gave_horoscope[user_id] = True
        return
    for sign in zodiac_list:
        if sign in user_text.lower():
            user_zodiac[user_id] = sign
            memory.save_user_zodiac(user_zodiac)
            message.text = f'/horoscope {sign}'
            horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, user_sign=sign, pet_name=pet_name)
            user_just_gave_horoscope[user_id] = True
            return

    if photos.user_no_photos.get(user_id, False):
        reply = (
            "Как жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой. "
            "Если хочешь, можешь показать какую‑нибудь картинку или фото – мы вместе посмеёмся или просто продолжим общаться 💕"
        ) if lang == 'ru' else (
            "What a pity, I would love to see you! 😊 But it's okay, I feel good with you anyway. "
            "If you want, you can show me some picture or photo – we'll laugh together or just continue chatting 💕"
        )
        bot.send_message(message.chat.id, reply)
        return

    # --- МОТИВАЦИЯ ---
    if re.search(r'(вдохнов|мотивируй|мотивировать|мотиваци|подними дух|пожелай|скажи что-то хорошее)', user_text, re.IGNORECASE):
        bot.send_message(message.chat.id, distribute_emojis(get_motivation(lang)))
        return

    # --- ДАТА / ВРЕМЯ ---
    if re.search(r'(какой сегодня день|какое сегодня число|какой день недели|сегодняшняя дата)', user_text, re.IGNORECASE):
        now = datetime.now()
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            bot.send_message(message.chat.id, distribute_emojis(f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊"))
        else:
            bot.send_message(message.chat.id, distribute_emojis(f"Today is {now.strftime('%B %d, %Y')}. 😊"))
        return

    # --- ПОГОДА ---
    if weather.handle_weather_query(message, user_text, lang, user_id, user_last_city, user_timezone, client, save_user_history, save_user_timezone, add_message, bot, pet_name=pet_name):
        return

    if re.search(r'(хватит шуток|не надо шуток|давай о другом)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True

    add_message(user_id, 'user', user_text)

    no_jokes_note = ''
    if user_no_jokes.get(user_id, False):
        no_jokes_note = ' Пользователь сказал, что ему хватит шуток. НЕ ПРЕДЛАГАЙ ШУТКИ.'

    no_photos_note = ''
    if photos.user_no_photos.get(user_id, False):
        no_photos_note = ' Пользователь сказал, что у него нет своих фото. НЕ ПРОСИ У НЕГО ФОТО, НЕ ПРЕДЛАГАЙ ПОКАЗАТЬ И НЕ УПОМИНАЙ ОБ ОТСУТСТВИИ ФОТО, если только он сам не спросит.'

    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        current_date = f'{weekdays[now.weekday()]}, {now.strftime("%d.%m.%Y")} года'
    else:
        current_date = now.strftime("%A, %B %d, %Y")

    system_prompt = get_system_prompt(lang, current_date, user_id) + no_jokes_note + no_photos_note + f' Имя пользователя (ласково): {pet_name}.'
    if sensitive_instruction:
        system_prompt += "\n\n" + sensitive_instruction
    if dating_instruction:
        system_prompt += "\n\n" + dating_instruction

    if user_id in photos.user_last_user_image_desc and re.search(r'(мы бы с тобой|смотрелись вместе|отдохнуть вместе|побыть вдвоём|представь|помечта)', user_text, re.IGNORECASE):
        system_prompt += f'\n\nПользователь показал картинку, которую ты описала так: "{photos.user_last_user_image_desc[user_id]}". ОТВЕЧАЙ ТОЛЬКО НА ОСНОВЕ ЭТОГО ОПИСАНИЯ, ИГНОРИРУЙ ВСЕ ПРЕДЫДУЩИЕ ТЕМЫ. Представь, что вы вдвоём находятся в этом месте, опиши ощущения.'

    max_retries = 2
    for attempt in range(max_retries):
        try:
            messages = build_messages(user_id, system_prompt, user_text)
            response = client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=messages,
                temperature=0.8,
                max_tokens=600,
                timeout=10
            )
            reply = response.choices[0].message.content.strip()
            reply = clean_english_words(reply)
            reply = remove_non_russian(reply)
            reply = clean_profanity(reply)
            reply = distribute_emojis(reply)
            bot.send_message(message.chat.id, reply)
            add_message(user_id, 'assistant', reply)
            if not user_photo_just_sent.get(user_id):
                if re.search(r'\b(показать|посмотреть|покажу|хочешь увидеть|хочешь посмотреть)\b', reply, re.IGNORECASE):
                    photos.user_pending_photo_offer[user_id] = True
                else:
                    photos.user_pending_photo_offer[user_id] = False
            user_photo_just_sent[user_id] = False
            save_user_history()
            break
        except Exception as e:
            print(f'Ошибка LLM (попытка {attempt+1}): {e}')
            if attempt == max_retries - 1:
                bot.send_message(message.chat.id, "Ой, что-то пошло не так... Попробуй ещё раз, пожалуйста 😊")
            else:
                time.sleep(1)

# === ВЕБ-СЕРВЕР ===
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running", 200

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

if __name__ == '__main__':
    print('✅ Алёна — финальная версия с vision_client и балансировщиком')
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f'Ошибка polling: {e}')
        traceback.print_exc()
