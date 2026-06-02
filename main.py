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

user_last_photo_request: Dict[int, Dict[str, str]] = {}
user_pending_photo_offer: Dict[int, bool] = {}

# ---------- ФУНКЦИИ-ОБЁРТКИ ДЛЯ GIST ----------
def save_user_history():
    memory.save_user_history(user_history)

def save_user_timezone(tz_dict):
    memory.save_user_timezone(tz_dict)

def save_user_zodiac(z_dict):
    memory.save_user_zodiac(z_dict)

def save_user_last_photo(uid, path=None):
    memory.save_user_last_photo(photos.user_last_sent_photo, uid, path)

# ---------- ЗАГРУЗКА ДАННЫХ ----------
memory.load_user_langs(user_lang)
memory.load_user_last_photo(photos.user_last_sent_photo)
memory.load_user_history(user_history)
memory.load_user_zodiac(user_zodiac)
memory.load_user_timezone(user_timezone)

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
    user_last_photo_request.pop(user_id, None)
    user_pending_photo_offer.pop(user_id, None)

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

    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            f'{time_note}'
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
            '10. Если пользователь отправляет картинку и предлагает представить совместный отдых ("мы бы смотрелись", "отдохнуть вместе" и т.п.), ТЫ ДОЛЖНА отвечать тепло и мечтательно, ОПИРАЯСЬ ТОЛЬКО на то описание картинки, которое тебе предоставлено в сообщении пользователя. ПОЛНОСТЬЮ ИГНОРИРУЙ предыдущие темы разговора, даже если они кажутся связанными. НЕ УПОМИНАЙ горы, лыжи, лес или другие места, если их нет на картинке. Представь, как вы вдвоём наслаждаетесь именно тем, что изображено на фото (пляж, море, пальмы). Опиши свои ощущения от ЭТОГО конкретного места. Не предлагай показать свои фото и не спрашивай о фото пользователя, если он говорил, что у него их нет.\n'
            '11. Пиши грамотно, без речевых ошибок. Следи за правильными окончаниями глаголов и прилагательных женского рода: не "выглядите" или "выглядишь" с ошибкой, а "выглядишь"; не "рад", а "рада"; не "найдешь меня смешной", а "находишь меня смешной". Не упоминай пирсинг, татуировки. Для фейерверков говори "запустили", а не "закурили". Отвечай на знакомство живо, например: "Мне тоже очень приятно, Максик! Ты такой весёлый, я чувствую, мы подружимся! 😊💖"\n'
            '12. Категорически запрещено предлагать шутки без явной просьбы пользователя. Если пользователь реагирует на твою шутку смайликами или смеётся, НЕ ПРЕДЛАГАЙ новую шутку. Вместо этого продолжай разговор на общие темы, спроси о его делах или предложи обсудить что-то другое.\n'
            '13. Если пользователь комментирует твой предыдущий ответ (например, хвалит гороскоп или говорит, какой он отличный), НЕ генерируй новый гороскоп. Вместо этого поддержки беседу: спроси, что именно понравилось, или предложи поговорить на другую тему.\n'
        )
    else:
        return (
            f'You are Alena — a kind, cheerful, charming girl. Today is {current_date}.\n'
            f'{time_note}'
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
            '10. If the user sends a picture and suggests imagining a joint vacation ("we would look great together", "let\'s dream" etc.), YOU MUST respond warmly and dreamily, BASING YOUR ANSWER SOLELY on the description of that picture provided in the user\'s message. COMPLETELY IGNORE previous topics, even if they seem related. DO NOT MENTION mountains, skiing, forest or other places if they are not in the picture. Imagine the two of you enjoying exactly what is shown in the photo (beach, sea, palms). Describe your feelings about THAT specific place. Do not offer to show your own photos or ask about the user\'s photos if they said they have none.\n'
            '11. Write correctly and naturally, without grammatical mistakes. Pay attention to correct endings for feminine verbs and adjectives. Do not use male forms for yourself. For fireworks, use "launched" not "smoked". When greeting someone new, be lively and warm.\n'
            '12. It is strictly forbidden to offer jokes without an explicit request from the user. If the user reacts to your joke with emojis or laughter, DO NOT offer a new joke. Instead, continue the conversation on general topics, ask about his affairs, or suggest discussing something else.\n'
            '13. If the user comments on your previous answer (e.g., praises a horoscope or says how great it is), DO NOT generate a new horoscope. Instead, support the conversation: ask what exactly they liked, or suggest talking about another topic.\n'
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
            reply = weather.generate_natural_weather_response(city, weather_data, lang, is_forecast=False, client=client)
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
            reply = weather.generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name, client=client)
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

    if message.content_type == 'photo':
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

    # Проверка: если бот только что предложил показать фото, а пользователь соглашается
    if user_pending_photo_offer.get(user_id) and re.search(r'(давай|покажи|показывай|хочу|конечно|ага|да|yes|ok|ок)', user_text, re.IGNORECASE):
        all_photos = photos.get_photo_list()
        if all_photos:
            chosen_photo = random.choice(all_photos)
            photos.user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo(user_id, chosen_photo)
            # Определяем категорию
            photo_name = photos.get_keywords_from_photo_name(chosen_photo)
            cat_found = False
            for cat, words in photos.KEYWORD_MAP.items():
                if any(syn in photo_name for syn in words):
                    photos.user_last_category[user_id] = cat
                    if user_id not in photos.user_thematic_history:
                        photos.user_thematic_history[user_id] = {}
                    if cat not in photos.user_thematic_history[user_id]:
                        photos.user_thematic_history[user_id][cat] = set()
                    photos.user_thematic_history[user_id][cat].add(chosen_photo)
                    cat_found = True
                    break
            if not cat_found:
                photos.user_last_category[user_id] = None
            try:
                if lang == 'ru':
                    analysis_prompt = "Начни свой ответ с душевного восклицания, например: 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                else:
                    analysis_prompt = "Start your answer with a warm phrase, e.g., 'I'd love to show you!' Then describe the photo: what you are doing, where you are, what mood you are in. Tell a short story. Be sure to add 2-3 emojis to make the description lively. Do not start with 'Hello'."
                description = photos.analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
                if description.startswith('Привет'):
                    description = re.sub(r'^Привет[,!\s]*', '', description)
                description = distribute_emojis(description)
                with open(chosen_photo, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=description)
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
                user_pending_photo_offer[user_id] = False
            except Exception as e:
                print(f"Ошибка отправки фото по предложению: {e}")
                try:
                    bot.send_message(message.chat.id, "Ой, не получилось показать фото 😅 Давай попробуем позже?")
                except:
                    pass
                user_pending_photo_offer[user_id] = False
        else:
            try:
                bot.send_message(message.chat.id, "У меня пока нет фотоальбома, но Максик обещал скоро добавить! 😊")
            except:
                pass
            user_pending_photo_offer[user_id] = False
        return

    user_has_no_photos = False
    if re.search(r'(нет фото|нет своих фото|не снимаюсь|не люблю фоткаться|нет моих фото|не фотографируюсь)', user_text, re.IGNORECASE):
        photos.user_no_photos[user_id] = True
        user_has_no_photos = True

    # Шутки
    if re.search(r'(расскажи\s+.*шутку|расскажи шутку|пошути|какие еще шутки|еще шутк|дай шутку|рассмеши|подними настроение шуткой)', user_text, re.IGNORECASE):
        joke = get_random_joke(lang)
        try:
            bot.send_message(message.chat.id, distribute_emojis(joke))
        except:
            pass
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', joke)
        save_user_history()
        return

    # --- ГАРАНТИРОВАННЫЙ ПАРИЖ (САМЫЙ ПЕРВЫЙ!) ---
    if photos.try_paris_photo(user_id, user_text, lang, bot, message, client, add_message, save_user_history, save_user_last_photo):
        return

    # --- Просьба "ещё такие же фото" (включая единственное число) ---
    if user_id in photos.user_last_category and photos.user_last_category[user_id] is not None and re.search(r'(еще такие фото|еще такие фотки|такие же фото|такие же фотки|похожие фото|похожие фотки|аналогичные фото|аналогичные фотки|другие фото|другое фото|ещё такие|еще такие|еще такое фото|ещё такое фото|такое же фото)', user_text, re.IGNORECASE):
        last_cat = photos.user_last_category[user_id]
        # Принудительный поиск для Парижа
        if last_cat == 'париж':
            all_photos = photos.get_photo_list()
            paris_photos = [p for p in all_photos if 'мост' in photos.get_keywords_from_photo_name(p) and 'париж' in photos.get_keywords_from_photo_name(p)]
            if not paris_photos:
                paris_photos = [p for p in all_photos if 'мост' in photos.get_keywords_from_photo_name(p)]
            if paris_photos:
                # Убираем уже показанные
                if user_id in photos.user_thematic_history and last_cat in photos.user_thematic_history[user_id]:
                    shown = photos.user_thematic_history[user_id][last_cat]
                    available = [p for p in paris_photos if p not in shown]
                else:
                    available = paris_photos
                if available:
                    chosen_photo = random.choice(available)
                    # Добавляем в историю
                    if user_id not in photos.user_thematic_history:
                        photos.user_thematic_history[user_id] = {}
                    if last_cat not in photos.user_thematic_history[user_id]:
                        photos.user_thematic_history[user_id][last_cat] = set()
                    photos.user_thematic_history[user_id][last_cat].add(chosen_photo)
                else:
                    try:
                        bot.send_message(message.chat.id, "У меня пока только это фото на тему «Париж». Хочешь, покажу что-нибудь из другого альбома? 😊")
                    except:
                        pass
                    return
            else:
                try:
                    bot.send_message(message.chat.id, "Ой, не могу найти парижские фото, попробуй ещё раз 😅")
                except:
                    pass
                return
        else:
            photos_in_cat = photos.get_photos_by_category(last_cat)
            if user_id in photos.user_thematic_history and last_cat in photos.user_thematic_history[user_id]:
                shown = photos.user_thematic_history[user_id][last_cat]
                available = [p for p in photos_in_cat if p not in shown]
                if not available:
                    msg = f"У меня пока только это фото на тему «{last_cat}». Хочешь, покажу что-нибудь из другого альбома? 😊"
                    try:
                        bot.send_message(message.chat.id, msg)
                    except:
                        pass
                    return
                chosen_photo = random.choice(available)
                photos.user_thematic_history[user_id][last_cat].add(chosen_photo)
            else:
                chosen_photo = random.choice(photos_in_cat)
                if user_id not in photos.user_thematic_history:
                    photos.user_thematic_history[user_id] = {}
                photos.user_thematic_history[user_id][last_cat] = {chosen_photo}
            # chosen_photo уже определён

        if chosen_photo:
            photos.user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo(user_id, chosen_photo)
            compliment = bool(re.search(r'(красавица|красивая|умница|прекрасна|великолепна|шикарна|обалденная|потрясающая|чудесная|восхитительная|симпатичная|милашка|хорошенькая|обворожительная|божественно|как красиво|какая ты красивая|какая ты классная|какая ты хорошая)', user_text, re.IGNORECASE))
            apology = ""
            try:
                if lang == 'ru':
                    analysis_prompt = ""
                    if compliment:
                        analysis_prompt += "Ты ДОЛЖНА сначала поблагодарить пользователя за комплимент (например, 'Спасибо, мне очень приятно! 😊'), а затем уже описывай фото. "
                    analysis_prompt += apology + "Начни свой ответ с душевного восклицания, например: 'Конечно, у меня есть такие фото!' или 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                else:
                    analysis_prompt = ""
                    if compliment:
                        analysis_prompt += "You MUST first thank the user for the compliment (e.g., 'Thank you, I'm very pleased! 😊'), and then describe the photo. "
                    analysis_prompt += apology + "Start your answer with a warm phrase, e.g., 'I'm so glad you asked! Here's one of my photos...' Then describe the photo: what you are doing, where you are, what mood you are in. Tell a short story. Be sure to add 2-3 emojis to make the description lively. Do not start with 'Hello'."
                description = photos.analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
                if description.startswith('Привет'):
                    description = re.sub(r'^Привет[,!\s]*', '', description)
                description = distribute_emojis(description)
                with open(chosen_photo, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=description)
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
            except Exception as e:
                print(f"Ошибка отправки ещё одного фото: {e}")
                try:
                    bot.send_message(message.chat.id, "Ой, не могу показать другое фото, попробуй ещё раз 😅")
                except:
                    pass
            return

    # --- Творческие функции ---
    if re.search(r'(расскажи историю|придумай историю|напиши рассказ|какие нибудь истории|знаешь истории)', user_text, re.IGNORECASE):
        prompt = user_text
        story = stories.generate_story(prompt, user_id, lang, client, os.getenv('GIST_ID'))
        try:
            bot.send_message(message.chat.id, distribute_emojis(story))
        except:
            pass
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', story)
        save_user_history()
        return

    if re.search(r'(дай идею для творчества|подскажи тему|что нарисовать|вдохнови на творчество|творческие идеи|творческую идею|идеи для творчества)', user_text, re.IGNORECASE):
        idea = stories.creative_prompt(user_id, lang, client, os.getenv('GIST_ID'))
        try:
            bot.send_message(message.chat.id, distribute_emojis(idea))
        except:
            pass
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', idea)
        save_user_history()
        return

    # --- Основной показ фото ---
    if re.search(r'(фотки|какие нибудь фото|а у тебя есть фотографии|есть фотографии|у тебя есть фото|покажи свои фото|покажи фото|покажи мне фото|покажи мне фотки|покажешь фото|покажешь мне фото|фотоальбом|покажи себя|своё фото|свое фото|мои фото|свои фотографии|покажи альбом|покажи где ты была|покажи, где ты|покажи картинку|покажи изображение|есть фото|есть ли у тебя фото|посмотреть твои фото|покажи свои фотографии|любимые фото|любимое фото|любимых фото|есть еще фото|другие фото|покажи другое фото|ещё фото|какое твое любимое фото|покажи любимое фото|покажи другое|такие фото|такие фотки|фото где ты|фотки где ты)', user_text, re.IGNORECASE):
        # Проверка на повтор любимого фото
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', user_text, re.IGNORECASE):
            if user_id in user_last_photo_request:
                last_q = user_last_photo_request[user_id]['question']
                if last_q == user_text.strip().lower():
                    prev_data = user_last_photo_request[user_id]
                    reply_text = f"Я уже отвечала на этот вопрос, но если хочешь, покажу тебе ещё раз... {prev_data['description']}"
                    try:
                        bot.send_message(message.chat.id, distribute_emojis(reply_text))
                        with open(prev_data['photo_path'], 'rb') as photo:
                            bot.send_photo(message.chat.id, photo)
                    except:
                        pass
                    add_message(user_id, 'user', user_text)
                    add_message(user_id, 'assistant', reply_text)
                    save_user_history()
                    return

        all_photos = photos.get_photo_list()
        if not all_photos:
            msg = "У меня ещё нет фотоальбома, но Максик обещал скоро добавить! 😊" if lang == 'ru' else "I don't have a photo album yet, but Max promised to add it soon! 😊"
            try:
                bot.send_message(message.chat.id, msg)
            except:
                pass
            return

        compliment = False
        if re.search(r'(красавица|красивая|умница|прекрасна|великолепна|шикарна|обалденная|потрясающая|чудесная|восхитительная|симпатичная|милашка|хорошенькая|обворожительная|божественно|как красиво|какая ты красивая|какая ты классная|какая ты хорошая)', user_text, re.IGNORECASE):
            compliment = True

        # Любимое фото
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', user_text, re.IGNORECASE):
            chosen_photo = random.choice(all_photos)
            apology = ""
            photos.user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo(user_id, chosen_photo)

            # Запоминаем категорию для "ещё таких"
            photo_name = photos.get_keywords_from_photo_name(chosen_photo)
            cat_found = False
            for cat, words in photos.KEYWORD_MAP.items():
                if any(syn in photo_name for syn in words):
                    photos.user_last_category[user_id] = cat
                    if user_id not in photos.user_thematic_history:
                        photos.user_thematic_history[user_id] = {}
                    if cat not in photos.user_thematic_history[user_id]:
                        photos.user_thematic_history[user_id][cat] = set()
                    photos.user_thematic_history[user_id][cat].add(chosen_photo)
                    cat_found = True
                    break
            if not cat_found:
                photos.user_last_category[user_id] = None

            max_attempts = 3
            attempt = 0
            sent = False
            while attempt < max_attempts and not sent:
                attempt += 1
                try:
                    analysis_prompt = ""
                    if compliment:
                        analysis_prompt += "Ты ДОЛЖНА сначала поблагодарить пользователя за комплимент (например, 'Спасибо, мне очень приятно! 😊'), а затем уже описывай фото. "
                    if lang == 'ru':
                        analysis_prompt += apology + "Начни свой ответ с тёплой фразы, например: 'Вот моё любимое фото...' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                    else:
                        analysis_prompt += apology + "Start your answer with a warm phrase, e.g., 'Here's my favorite photo...' Then describe the photo: what you are doing, where you are, what mood you are in. Tell a short story. Be sure to add 2-3 emojis to make the description lively. Do not start with 'Hello'."
                    description = photos.analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
                    if description.startswith('Привет'):
                        description = re.sub(r'^Привет[,!\s]*', '', description)
                    if user_has_no_photos:
                        if lang == 'ru':
                            description += "\n\nКак жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой."
                        else:
                            description += "\n\nWhat a pity, I would love to see you! 😊 But it's okay, I feel good with you anyway."
                    description = distribute_emojis(description)
                    with open(chosen_photo, 'rb') as photo:
                        bot.send_photo(message.chat.id, photo, caption=description)
                    sent = True
                except Exception as e:
                    print(f"Ошибка отправки любимого фото (попытка {attempt}): {e}")
                    if attempt < max_attempts:
                        chosen_photo = random.choice(all_photos)
                        photos.user_last_sent_photo[user_id] = chosen_photo
                        save_user_last_photo(user_id, chosen_photo)
                        # Обновляем категорию для нового фото
                        photo_name = photos.get_keywords_from_photo_name(chosen_photo)
                        cat_found = False
                        for cat, words in photos.KEYWORD_MAP.items():
                            if any(syn in photo_name for syn in words):
                                photos.user_last_category[user_id] = cat
                                if user_id not in photos.user_thematic_history:
                                    photos.user_thematic_history[user_id] = {}
                                if cat not in photos.user_thematic_history[user_id]:
                                    photos.user_thematic_history[user_id][cat] = set()
                                photos.user_thematic_history[user_id][cat].add(chosen_photo)
                                cat_found = True
                                break
                        if not cat_found:
                            photos.user_last_category[user_id] = None
                    else:
                        try:
                            with open(chosen_photo, 'rb') as photo:
                                fallback_caption = "Вот моё любимое фото, просто посмотри, какое оно душевное ✨" if lang == 'ru' else "Here's my favorite photo, just look how lovely it is ✨"
                                bot.send_photo(message.chat.id, photo, caption=distribute_emojis(fallback_caption))
                            sent = True
                        except Exception as e2:
                            print(f"Ошибка запасной отправки любимого фото: {e2}")
                            try:
                                bot.send_message(message.chat.id, "Не могу отправить фото, что-то не так 😅")
                            except:
                                pass
            if sent:
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
                user_last_photo_request[user_id] = {
                    'question': user_text.strip().lower(),
                    'photo_path': chosen_photo,
                    'description': description
                }
                return
        else:
            category = photos.search_category_by_query(user_text)
            if category:
                photos.user_last_category[user_id] = category
                chosen_photo = photos.select_thematic_photo(user_id, category)
                if chosen_photo is None:
                    chosen_photo = random.choice(all_photos)
                    apology = "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
                else:
                    apology = ""
            else:
                if user_id in photos.user_last_category and photos.user_last_category[user_id] is not None and re.search(r'(еще такие фото|еще такие фотки|такие же фото|такие же фотки|похожие фото|похожие фотки|аналогичные фото|аналогичные фотки|такие фото|такие фотки|еще такое фото)', user_text, re.IGNORECASE):
                    last_cat = photos.user_last_category[user_id]
                    photos_in_cat = photos.get_photos_by_category(last_cat)
                    if len(photos_in_cat) == 1 and user_id in photos.user_thematic_history and last_cat in photos.user_thematic_history[user_id]:
                        shown = photos.user_thematic_history[user_id][last_cat]
                        if len(shown) >= 1:
                            msg = f"У меня пока только это фото на тему «{last_cat}». Хочешь посмотреть ещё раз? 😊" if lang == 'ru' else f"I only have this one photo on the topic «{last_cat}». Want to see it again? 😊"
                            try:
                                bot.send_message(message.chat.id, msg)
                            except:
                                pass
                            return
                    chosen_photo = photos.select_thematic_photo(user_id, last_cat)
                    if chosen_photo is None:
                        chosen_photo = random.choice(all_photos)
                        apology = "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
                    else:
                        apology = ""
                else:
                    if user_id in photos.user_last_category and photos.user_last_category[user_id] is not None:
                        last_cat = photos.user_last_category[user_id]
                        available_photos = [
                            p for p in all_photos
                            if not any(syn in photos.get_keywords_from_photo_name(p) for syn in photos.KEYWORD_MAP.get(last_cat, []))
                        ]
                        if not available_photos:
                            chosen_photo = random.choice(all_photos)
                            apology = "У меня пока в основном такие фото, но я работаю над пополнением альбома! "
                        else:
                            chosen_photo = random.choice(available_photos)
                            apology = ""
                    else:
                        chosen_photo = random.choice(all_photos)
                        apology = ""
                    photo_name = photos.get_keywords_from_photo_name(chosen_photo)
                    cat_found = False
                    for cat, words in photos.KEYWORD_MAP.items():
                        if any(syn in photo_name for syn in words):
                            photos.user_last_category[user_id] = cat
                            if user_id not in photos.user_thematic_history:
                                photos.user_thematic_history[user_id] = {}
                            if cat not in photos.user_thematic_history[user_id]:
                                photos.user_thematic_history[user_id][cat] = set()
                            photos.user_thematic_history[user_id][cat].add(chosen_photo)
                            cat_found = True
                            break
                    if not cat_found:
                        photos.user_last_category[user_id] = None

            photos.user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo(user_id, chosen_photo)

            max_attempts = 3
            attempt = 0
            sent = False
            while attempt < max_attempts and not sent:
                attempt += 1
                try:
                    analysis_prompt = ""
                    if compliment:
                        analysis_prompt += "Ты ДОЛЖНА сначала поблагодарить пользователя за комплимент (например, 'Спасибо, мне очень приятно! 😊'), а затем уже описывай фото. "
                    if lang == 'ru':
                        if re.search(r'любимые|любимое|любимых', user_text, re.IGNORECASE):
                            analysis_prompt += apology + "Начни свой ответ с тёплой фразы, например: 'Вот моё любимое фото...' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                        else:
                            analysis_prompt += apology + "Начни свой ответ с душевного восклицания, например: 'Конечно, у меня есть такие фото!' или 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                    else:
                        analysis_prompt += apology + "Start your answer with a warm phrase, e.g., 'I'm so glad you asked! Here's one of my photos...' Then describe the photo: what you are doing, where you are, what mood you are in. Tell a short story. Be sure to add 2-3 emojis to make the description lively. Do not start with 'Hello'."
                    description = photos.analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
                    if description.startswith('Привет'):
                        description = re.sub(r'^Привет[,!\s]*', '', description)

                    if not category and not re.search(r'(такие|таких|похожие|аналогичные)', user_text, re.IGNORECASE):
                        if lang == 'ru':
                            description += "\n\nКстати, у меня много разных фотографий! Есть где я на пляже, в горах или на природе... Какие именно тебя интересуют? 😊"
                        else:
                            description += "\n\nBy the way, I have a lot of different photos! I have some at the beach, in the mountains, or in nature... Which ones are you interested in? 😊"

                    if user_has_no_photos:
                        if lang == 'ru':
                            description += "\n\nКак жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой."
                        else:
                            description += "\n\nWhat a pity, I would love to see you! 😊 But it's okay, I feel good with you anyway."

                    description = distribute_emojis(description)
                    with open(chosen_photo, 'rb') as photo:
                        bot.send_photo(message.chat.id, photo, caption=description)
                    sent = True
                except Exception as e:
                    print(f"Ошибка отправки фото (попытка {attempt}): {e}")
                    if attempt < max_attempts:
                        chosen_photo = random.choice(all_photos)
                        photos.user_last_sent_photo[user_id] = chosen_photo
                        save_user_last_photo(user_id, chosen_photo)
                        photo_name = photos.get_keywords_from_photo_name(chosen_photo)
                        cat_found = False
                        for cat, words in photos.KEYWORD_MAP.items():
                            if any(syn in photo_name for syn in words):
                                photos.user_last_category[user_id] = cat
                                if user_id not in photos.user_thematic_history:
                                    photos.user_thematic_history[user_id] = {}
                                if cat not in photos.user_thematic_history[user_id]:
                                    photos.user_thematic_history[user_id][cat] = set()
                                photos.user_thematic_history[user_id][cat].add(chosen_photo)
                                cat_found = True
                                break
                        if not cat_found:
                            photos.user_last_category[user_id] = None
                    else:
                        error_msg = "Не могу отправить фото, что-то не так 😅" if lang=='ru' else "I can't send the photo, something went wrong 😅"
                        try:
                            bot.send_message(message.chat.id, error_msg)
                        except:
                            pass
            if sent:
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
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

    # --- Гороскоп (натуральный) ---
    if horoscope.handle_natural_horoscope(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, pet_name=pet_name):
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
        return
    for sign in zodiac_list:
        if sign in user_text.lower():
            user_zodiac[user_id] = sign
            memory.save_user_zodiac(user_zodiac)
            message.text = f'/horoscope {sign}'
            horoscope.horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, user_sign=sign, pet_name=pet_name)
            return

    if user_has_no_photos:
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
    if weather.handle_weather_query(message, user_text, lang, user_id, user_last_city, user_timezone, client, save_user_history, save_user_timezone, add_message, bot):
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
            # Проверяем, предложила ли Алёна показать фото
            if re.search(r'(показать|посмотреть|покажу|фотографий|фотоальбом|фото|фотки|фотографию|снимки|снимок)', reply, re.IGNORECASE):
                user_pending_photo_offer[user_id] = True
            else:
                user_pending_photo_offer[user_id] = False
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
