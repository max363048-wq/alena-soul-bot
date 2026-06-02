# main.py — Лёгкий диспетчер Алёны (стабильная основа + gender + фото через модуль)
import os
import telebot
import re
import random
import time
import threading
import traceback
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
from text_utils import clean_english_words, remove_non_russian, distribute_emojis, SAFE_EMOJIS

BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')

BOT_USERNAME = 'AlenaSoul_bot'

user_history: Dict[int, Deque] = {}
user_no_jokes: Dict[int, bool] = {}
user_preferences: Dict[int, str] = {}
user_lang: Dict[int, str] = {}
user_last_city: Dict[int, str] = {}
user_zodiac: Dict[int, str] = {}
user_timezone: Dict[int, int] = {}
user_gender: Dict[int, str] = {}
user_awaiting_gender: Dict[int, bool] = {}

user_just_gave_horoscope: Dict[int, bool] = {}

# ---------- ФУНКЦИИ-ОБЁРТКИ ДЛЯ GIST ----------
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

# ---------- ЗАГРУЗКА ДАННЫХ ----------
memory.load_user_langs(user_lang)
memory.load_user_last_photo(photos.user_last_sent_photo)
memory.load_user_history(user_history)
memory.load_user_zodiac(user_zodiac)
memory.load_user_timezone(user_timezone)
memory.load_user_last_favorite_photo(photos.user_last_favorite_photo)
memory.load_user_gender(user_gender)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
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
            messages=[{'role': 'user', 'content': 'Ты Алёна. Напиши короткую тёплую вдохновляющую фразу для друга.'}],
            temperature=0.8, max_tokens=80, timeout=5
        )
        phrase = resp.choices[0].message.content.strip()
        if phrase:
            return phrase
        return "Ты сможешь всё, что задумаешь! 💖"
    except:
        return "Ты сможешь всё, что задумаешь! 💖"

def get_system_prompt(lang: str, current_date: str, user_id: int) -> str:
    time_note = ''
    if user_id in user_timezone:
        local_time_str = weather.format_local_time(user_timezone[user_id])
        time_note = f'Текущее время пользователя: {local_time_str}. Используй это, чтобы выбирать приветствия (доброе утро, день, вечер) и не путать время суток.\n'

    gender_note = ''
    if user_id in user_gender:
        if user_gender[user_id] == 'male':
            gender_note = 'Пользователь — парень. Ты можешь слегка подшучивать по-дружески, но оставайся тёплой и милой.\n'
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
            '13. Если пользователь комментирует твой предыдущий ответ (хвалит гороскоп, говорит, что он отличный, или радуется ему), ты ОБЯЗАНА сначала искренне разделить его радость, сказать, что тебе очень приятно, что ты рада за него, добавить пару тёплых слов, и только потом, если хочешь, предложи поговорить о чём-то ещё. Не переключай тему сразу после комплимента — это звучит холодно.\n'
            '14. Избегай неестественных, канцелярских или неуместных слов вроде "рассортировать", "что ты такое человек" и подобных. Говори просто и по-человечески. Будь естественной, как настоящая девушка.\n'
        )
    else:
        return (
            f'You are Alena — a kind, cheerful, charming girl. Today is {current_date}.\n'
            f'{time_note}'
            f'{gender_note}'
            'RULES:\n'
            '1. Answer only in English, no mixing.\n'
            '2. NEVER start with "Hello", "Hi" or any greeting. You are already in a conversation, start directly.\n'
            '3. Use emojis 😊😄😘💖✨ in every sentence, not just at the end. Your answers should look lively and emotional.\n'
            '4. If asked for a joke — tell one short joke, do not ask "want another?".\n'
            '5. If asked for a horoscope and the zodiac sign is not yet known, say: "Sorry, but I don\'t know your date of birth (just day and month) or just tell me your zodiac sign."\n'
            '6. Answer briefly (2-4 sentences), be lively.\n'
            '7. Address the user by name kindly, but not at the beginning.\n'
            '8. Occasionally (after 2-3 of your own photos or in the middle of a conversation) show interest in the user: ask if they have a photo, offer to share. But don\'t do it after every photo to avoid being intrusive.\n'
            '9. If the user compliments you (beautiful, smart, etc.), you MUST first thank them (e.g., "Thank you, I\'m very pleased! 😊"), and only then describe the photo or continue the topic. Do not ignore compliments.\n'
            '10. If the user sends a picture and suggests imagining a joint vacation ("we would look great together", "let\'s dream" etc.), YOU MUST respond warmly and dreamily, BASING YOUR ANSWER SOLELY on the description of that picture that you gave. COMPLETELY IGNORE previous topics, even if they seem related. DO NOT MENTION mountains, skiing, forest or other places if they are not in the picture. Imagine the two of you enjoying exactly what is shown in the photo (beach, sea, palms). Describe your feelings about THAT specific place. DO NOT add new objects (piers, buildings) that were not in your description of the picture. Do not offer to show your own photos or ask about the user\'s photos if they said they have none.\n'
            '11. Write correctly and naturally, without grammatical mistakes. Pay attention to correct endings for feminine verbs and adjectives. Do not use male forms for yourself. For fireworks, use "launched" not "smoked". When greeting someone new, be lively and warm.\n'
            '12. It is strictly forbidden to offer jokes without an explicit request from the user. But if the conversation is very fun and light, you can occasionally (very rarely) say: "By the way, I have a funny joke! Want me to tell it?" and wait for an answer. Do not tell a joke without permission.\n'
            '13. If the user comments on your previous answer (e.g., praises a horoscope or says how great it is), you MUST first sincerely share his joy, say that you are very pleased, that you are happy for him, add a couple of warm words, and only then, if you want, suggest talking about something else. Do not switch the topic immediately after a compliment — it sounds cold.\n'
            '14. Avoid unnatural, bureaucratic or inappropriate words like "sort out", "what kind of person are you" and similar. Speak simply and humanly. Be natural, like a real girl.\n'
        )

# ---------- ОСНОВНЫЕ ОБРАБОТЧИКИ ----------
@bot.message_handler(commands=['start'])
def send_welcome(message: telebot.types.Message) -> None:
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
def set_language(message: telebot.types.Message) -> None:
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

@bot.message_handler(func=lambda message: message.text and re.match(r'^(зовут меня|называй меня|обращайся ко мне|call me|name me)\s+', message.text.lower()))
def change_name(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    try:
        m = re.match(r'(?:зовут меня|называй меня|обращайся ко мне|call me|name me)\s+(.+?)(?:\.|$)', message.text, re.IGNORECASE)
        if m:
            new_name = m.group(1).strip()
            if new_name:
                user_preferences[user_id] = new_name
                lang = user_lang.get(user_id, 'ru')
                reply = f'Запомнила! Теперь буду называть тебя «{new_name}» 💖😘' if lang=='ru' else f'Got it! Now I\'ll call you {new_name} 💖😘'
                bot.send_message(message.chat.id, distribute_emojis(reply))
                add_message(user_id, 'assistant', reply)
                save_user_history()
                return
        lang = user_lang.get(user_id, 'ru')
        reply = 'Напиши, как тебя называть, например: «Зови меня Друг» 😊' if lang=='ru' else 'Tell me what to call you, e.g. "Call me Friend" 😊'
        bot.send_message(message.chat.id, distribute_emojis(reply))
        add_message(user_id, 'assistant', reply)
        save_user_history()
    except Exception as e:
        print(f'Ошибка change_name: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['weather'])
def weather_cmd(message: telebot.types.Message) -> None:
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
def forecast_cmd(message: telebot.types.Message) -> None:
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
def date_cmd(message: telebot.types.Message) -> None:
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
def horoscope_command(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    pet_name = get_pet_name(user_id, message.from_user.first_name)
    horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, pet_name=pet_name)
    user_just_gave_horoscope[user_id] = True

@bot.message_handler(commands=['quote'])
def quote_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    try:
        quote = get_motivation(lang)
        bot.send_message(message.chat.id, distribute_emojis(quote))
    except Exception as e:
        print(f'Ошибка quote_cmd: {e}')
        traceback.print_exc()

@bot.message_handler(commands=['reset'])
def reset_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    try:
        reset_user(user_id)
        bot.send_message(message.chat.id, distribute_emojis("Память очищена 😊"))
    except Exception as e:
        print(f'Ошибка reset_cmd: {e}')
        traceback.print_exc()

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message: telebot.types.Message) -> None:
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

    if message.content_type == 'photo':
        photos.user_pending_photo_offer[user_id] = False
        try:
            photos.analyze_user_photo(message, bot, client, lang)
        except Exception as e:
            print(f'Ошибка анализа фото пользователя: {e}')
            try:
                bot.send_message(message.chat.id, "Что-то не так с фото, может, попробуешь другое? 😊")
            except:
                pass
        return

    if user_text.startswith('/'):
        return

    # Сброс флага при явных запросах других функций
    if re.search(r'(гороскоп|погода|погоду|погоде|историю|истории|история|творчеств|вдохнови|расскажи гороскоп|расскажи мне гороскоп|расскажи историю|расскажи мне историю|расскажи какую)', user_text, re.IGNORECASE):
        photos.user_pending_photo_offer[user_id] = False

    # Проверка предложения показать фото
    if photos.user_pending_photo_offer.get(user_id) and re.search(r'\b(давай|покажи|показывай|хочу|конечно|ага|да|yes|ok|ок)\b', user_text, re.IGNORECASE):
        # Обрабатываем через модуль
        if photos.handle_photo_request(user_id, user_text, lang, bot, message, client,
                                       add_message, save_user_history, save_user_last_photo,
                                       save_user_last_favorite_photo):
            photos.user_pending_photo_offer[user_id] = False
            return

    # ... (остальная логика без изменений, но теперь вместо огромного блока фото вызываем модуль)
    # --- Обработка запросов фото через модуль ---
    if photos.handle_photo_request(user_id, user_text, lang, bot, message, client,
                                   add_message, save_user_history, save_user_last_photo,
                                   save_user_last_favorite_photo):
        return

    # --- Вопросы о последнем фото ---
    lower_text = user_text.lower()
    is_photo_question = any(phrase in lower_text for phrase in [
        'где была сделана', 'какое место', 'что там за фон', 'где это', 'какой город',
        'на каком курорте', 'какая страна', 'где ты находилась', 'где это было',
        'расскажи про это фото', 'подробнее об этом фото', 'что там за', 'какие детали',
        'где снято', 'а на каком пляже', 'в каком парке', 'в какой стране', 'это в россии',
        'за границей', 'в каком городе', 'на каком море', 'какой пляж', 'как называется',
        'поделись деталями', 'что ещё видно', 'расскажи подробнее', 'добавь деталей',
        'опиши фон', 'что позади', 'какие люди',
        'это фото', 'эта фотография', 'на этом фото', 'на этой фотографии'
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
                description = photos.analyze_photo_with_vision(photo_path, prompt, client, lang)
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

    # --- Гороскоп (натуральный, расширенный) ---
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

    # --- Определение даты/знака зодиака вне команды ---
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
        try:
            bot.send_message(message.chat.id, reply)
        except:
            pass
        return

    if re.search(r'(вдохнов|мотивируй|подними дух|пожелай|скажи что-то хорошее)', user_text, re.IGNORECASE):
        try:
            bot.send_message(message.chat.id, distribute_emojis(get_motivation(lang)))
        except:
            pass
        return

    if re.search(r'(какой сегодня день|какое сегодня число|какой день недели|сегодняшняя дата)', user_text, re.IGNORECASE):
        now = datetime.now()
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            try:
                bot.send_message(message.chat.id, distribute_emojis(f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊"))
            except:
                pass
        else:
            try:
                bot.send_message(message.chat.id, distribute_emojis(f"Today is {now.strftime('%B %d, %Y')}. 😊"))
            except:
                pass
        return

    # Погода
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

    if user_id in photos.user_last_user_image_desc and re.search(r'(мы бы с тобой|смотрелись вместе|отдохнуть вместе|побыть вдвоём|представь|помечта)', user_text, re.IGNORECASE):
        system_prompt += f'\n\nПользователь показал картинку, которую ты описала так: "{photos.user_last_user_image_desc[user_id]}". ОТВЕЧАЙ ТОЛЬКО НА ОСНОВЕ ЭТОГО ОПИСАНИЯ, ИГНОРИРУЙ ВСЕ ПРЕДЫДУЩИЕ ТЕМЫ. Представь, что вы вдвоём находятся в этом месте, опиши ощущения.'

    max_retries = 2
    for attempt in range(max_retries):
        try:
            messages = build_messages(user_id, system_prompt, user_text)
            response = client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=messages,
                temperature=0.8, max_tokens=400, timeout=10
            )
            reply = response.choices[0].message.content.strip()
            reply = clean_english_words(reply)
            reply = remove_non_russian(reply)
            reply = distribute_emojis(reply)
            try:
                bot.send_message(message.chat.id, reply)
            except:
                pass
            add_message(user_id, 'assistant', reply)
            if re.search(r'\b(показать|посмотреть|покажу|хочешь увидеть|хочешь посмотреть)\b', reply, re.IGNORECASE):
                photos.user_pending_photo_offer[user_id] = True
            else:
                photos.user_pending_photo_offer[user_id] = False
            save_user_history()
            break
        except Exception as e:
            print(f'Ошибка LLM (попытка {attempt+1}): {e}')
            if attempt == max_retries - 1:
                try:
                    bot.send_message(message.chat.id, "Ой, что-то пошло не так... Попробуй ещё раз, пожалуйста 😊")
                except:
                    pass
            else:
                time.sleep(1)

# === ДЛЯ RENDER: фоновый веб-сервер ===
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running", 200

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

if __name__ == '__main__':
    print('✅ Алёна — финальная, язык в Gist, шутки без повторов, Render-ready, история в Gist')
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f'Ошибка polling: {e}')
        traceback.print_exc()
