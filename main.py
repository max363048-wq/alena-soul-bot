import os
import telebot
import re
import requests
import random
from openai import OpenAI
from collections import deque
from datetime import datetime, timedelta

# --- Конфигурация ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')

BOT_USERNAME = 'AlenaSoul_bot'

# --- Память ---
user_history = {}
user_no_jokes = {}
user_preferences = {}
user_lang = {}

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=6)
    return user_history[user_id]

def add_message(user_id, role, content):
    get_history(user_id).append((role, content))

def build_messages(user_id, system_prompt, user_text):
    messages = [{'role': 'system', 'content': system_prompt}]
    for role, content in get_history(user_id):
        messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': user_text})
    return messages

def reset_user(user_id):
    user_history[user_id] = deque(maxlen=6)
    user_no_jokes[user_id] = False

# --- Ласковые имена ---
def default_pet_name(first_name):
    names = {
        'максим': 'Максик', 'макс': 'Максик', 'владимир': 'Вовочка',
        'вадим': 'Вадик', 'александр': 'Сашенька', 'анна': 'Анечка',
        'екатерина': 'Катюша', 'джон': 'Джонни', 'иван': 'Ванюша',
        'сергей': 'Серёжа', 'михаил': 'Миша', 'дмитрий': 'Дима',
        'андрей': 'Андрюша', 'алексей': 'Лёша', 'олег': 'Олежек',
        'пётр': 'Петя', 'петр': 'Петя'
    }
    return names.get(first_name.lower(), first_name)

def get_pet_name(user_id, first_name):
    if user_id in user_preferences:
        return user_preferences[user_id]
    return default_pet_name(first_name)

# --- Шутки ---
FALLBACK_JOKES_RU = [
    'Почему программисты не любят природу? Слишком много багов! 😄',
    'Что говорит один байт другому? — Ты такой битовый! 😂',
    'Почему физики не могут найти работу? Потому что их постоянно ускоряют! 🤣',
    'Как назвать кота, который ловит мышей? Компьютерный мыш! 😸',
    'Почему рыбы не играют в шахматы? Они боятся ладей! 🐟',
]

def is_virus_joke(text):
    text_lower = text.lower()
    return ('компьютер' in text_lower and ('вирус' in text_lower or 'инфекц' in text_lower)) or \
           ('компьютер' in text_lower and 'врач' in text_lower)

def get_random_joke(lang='ru'):
    if lang != 'ru':
        return "Why don't programmers like nature? Too many bugs! 😄"
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Придумай одну короткую смешную шутку на русском языке без английских слов.'}],
            temperature=0.9,
            max_tokens=100,
            timeout=5
        )
        joke = resp.choices[0].message.content.strip()
        if joke and 5 < len(joke) < 200 and not re.search(r'[a-zA-Z]', joke):
            if is_virus_joke(joke):
                return random.choice(FALLBACK_JOKES_RU)
            return joke
        return random.choice(FALLBACK_JOKES_RU)
    except:
        return random.choice(FALLBACK_JOKES_RU)

# --- Мотивация ---
MOTIVATION_FALLBACK = [
    'Ты сможешь всё, что задумаешь! 💖',
    'Каждый день — новая возможность стать счастливее. 😊',
    'Верь в свои силы, и они тебя не подведут! ✨',
]

def get_motivation(lang='ru'):
    if lang != 'ru':
        return 'Believe in yourself, every day is a new chance! 💖'
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Ты Алёна. Напиши короткую тёплую вдохновляющую фразу для друга.'}],
            temperature=0.8,
            max_tokens=80,
            timeout=5
        )
        phrase = resp.choices[0].message.content.strip()
        if phrase:
            return phrase
        return random.choice(MOTIVATION_FALLBACK)
    except:
        return random.choice(MOTIVATION_FALLBACK)

# --- Погода ---
def get_current_weather(city_name, lang='ru'):
    if not WEATHER_API_KEY:
        return '🔧 Погода временно недоступна.' if lang=='ru' else 'Weather unavailable.'
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if resp.status_code == 200:
            desc = data['weather'][0]['description']
            temp = data['main']['temp']
            feels = data['main']['feels_like']
            hum = data['main']['humidity']
            wind = data['wind']['speed']
            if lang == 'ru':
                result = (f'🌡️ *Сейчас в {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (ощущается {feels:.0f}°C)\n💧 Влажность {hum}%\n🌬️ Ветер {wind} м/с')
                result += f'\n\n✨ Хочешь узнать погоду на неделю? Напиши: `/weather {city_name} неделя`'
                return result
            else:
                result = (f'🌡️ *Now in {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (feels like {feels:.0f}°C)\n💧 Humidity {hum}%\n🌬️ Wind {wind} m/s')
                result += f'\n\n✨ Want a weekly forecast? Type: `/weather {city_name} week`'
                return result
        else:
            return f'Город \'{city_name}\' не найден.' if lang=='ru' else f'City \'{city_name}\' not found.'
    except:
        return 'Не удалось получить погоду.' if lang=='ru' else 'Weather error.'

def get_forecast(city_name, lang='ru'):
    if not WEATHER_API_KEY:
        return '🔧 Прогноз временно недоступен.' if lang=='ru' else 'Forecast unavailable.'
    url = f'http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if resp.status_code != 200:
            return f'Город \'{city_name}\' не найден.' if lang=='ru' else f'City \'{city_name}\' not found.'
        forecasts = []
        seen_dates = set()
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            date_str = dt.strftime('%d.%m' if lang=='ru' else '%m/%d')
            if date_str not in seen_dates:
                seen_dates.add(date_str)
                temp = item['main']['temp']
                desc = item['weather'][0]['description']
                forecasts.append(f'{date_str}: {desc.capitalize()}, {temp:.0f}°C')
            if len(forecasts) >= 5:
                break
        if lang == 'ru':
            return f'📅 *Прогноз для {city_name} на ближайшие дни:*\n' + '\n'.join(forecasts)
        else:
            return f'📅 *Forecast for {city_name} for the next days:*\n' + '\n'.join(forecasts)
    except:
        return 'Не удалось получить прогноз.' if lang=='ru' else 'Forecast error.'

# --- Команды ---
@bot.message_handler(commands=['weather'])
def weather_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Напиши город: /weather Москва\nЧтобы узнать прогноз: /weather Москва неделя')
        return
    city_input = parts[1].strip()
    if re.search(r'(неделя|прогноз|forecast|на неделю)', city_input, re.IGNORECASE):
        city_clean = re.sub(r'(неделя|прогноз|forecast|на неделю)', '', city_input, flags=re.IGNORECASE).strip()
        if city_clean:
            result = get_forecast(city_clean, lang)
        else:
            result = get_forecast(city_input, lang)
    else:
        result = get_current_weather(city_input, lang)
    bot.send_message(message.chat.id, result, parse_mode='Markdown')

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Напиши город: /forecast Москва')
        return
    city = parts[1].strip()
    result = get_forecast(city, lang)
    bot.send_message(message.chat.id, result, parse_mode='Markdown')

@bot.message_handler(commands=['date'])
def date_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        wd = weekdays[now.weekday()]
        bot.send_message(message.chat.id, f'Сегодня {wd}, {now.strftime("%d.%m.%Y")} года.')
    else:
        bot.send_message(message.chat.id, f'Today is {now.strftime("%B %d, %Y")}.')

@bot.message_handler(commands=['horoscope'])
def horoscope_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, 'Укажи знак: /horoscope козерог')
        return
    sign = parts[1].strip().lower()
    signs = {'овен':'aries','телец':'taurus','близнецы':'gemini','рак':'cancer',
             'лев':'leo','дева':'virgo','весы':'libra','скорпион':'scorpio',
             'стрелец':'sagittarius','козерог':'capricorn','водолей':'aquarius','рыбы':'pisces'}
    sign_en = signs.get(sign, sign)
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        prompt = f'Составь короткое доброе предсказание для знака {sign_en.title()} на {today}. Обращайся к пользователю на "ты".'
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7,
            max_tokens=300,
            timeout=5
        )
        text = resp.choices[0].message.content.strip()
        bot.send_message(message.chat.id, text)
    except:
        bot.send_message(message.chat.id, 'Не удалось составить гороскоп 😅')

@bot.message_handler(commands=['quote'])
def quote_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    quote = get_motivation(lang)
    bot.send_message(message.chat.id, quote)

@bot.message_handler(commands=['reset'])
def reset_cmd(message):
    user_id = message.from_user.id
    reset_user(user_id)
    lang = user_lang.get(user_id, 'ru')
    bot.send_message(message.chat.id, 'Память очищена 😊')

# --- /start ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    reset_user(user_id)
    user_lang[user_id] = None
    bot.send_message(message.chat.id,
        f'✨ Привет, {pet}! ✨\n\nМеня зовут Алёна 💖 Я — твой добрый собеседник, помощник и немного волшебница 🧚‍♀️\n\nДавай выберем язык общения:\nНапиши: **Русский** или **English**\n\n✨ Hi, {pet}! ✨\n\nI\'m Alena 💖 Your kind friend and helper 🧚‍♀️\n\nLet\'s choose the language:\nType: **Russian** or **English**')
    add_message(user_id, 'assistant', 'Выбор языка')

@bot.message_handler(func=lambda message: message.text and message.text.lower() in ['русский', 'russian', 'english', 'английский'])
def set_language(message):
    user_id = message.from_user.id
    text = message.text.lower()
    if text in ['русский', 'russian']:
        user_lang[user_id] = 'ru'
    else:
        user_lang[user_id] = 'en'
    pet = get_pet_name(user_id, message.from_user.first_name)
    lang = user_lang[user_id]
    joke = get_random_joke(lang)
    invite_link = f'https://t.me/{BOT_USERNAME}'
    if lang == 'ru':
        reply = (f'Отлично, {pet}! Будем общаться по-русски 💖\n\n😊 Шутка для настроения: {joke}\n\nА вот что я умею: могу поболтать по душам, рассмешить шуткой, поддержать советом, вдохновить и даже составить для тебя гороскоп ✨ Просто спроси — и я рядом.\n\nРасскажи, как твои дела? 💕\n\n✨ *Кстати!* Если хочешь поделиться мной с другом, вот ссылочка: {invite_link} Буду рада новым знакомствам 😘')
    else:
        reply = (f'Great, {pet}! We\'ll speak English 💖\n\n😊 A joke to cheer you up: {joke}\n\nHere\'s what I can do: chat from the heart, make you laugh, give advice, inspire, and even make a horoscope for you ✨ Just ask — I\'m here.\n\nSo, how are you? 💕\n\n✨ *By the way!* If you want to share me with a friend, here\'s the link: {invite_link} I\'ll be happy to meet new people 😘')
    bot.send_message(message.chat.id, reply)
    add_message(user_id, 'assistant', reply)

# --- Смена имени ---
@bot.message_handler(func=lambda message: message.text and re.match(r'^(зовут меня|называй меня|обращайся ко мне|call me|name me)\s+', message.text.lower()))
def change_name(message):
    user_id = message.from_user.id
    m = re.match(r'(?:зовут меня|называй меня|обращайся ко мне|call me|name me)\s+(.+?)(?:\.|$)', message.text, re.IGNORECASE)
    if m:
        new_name = m.group(1).strip()
        if new_name:
            user_preferences[user_id] = new_name
            lang = user_lang.get(user_id, 'ru')
            reply = f'Запомнила! Теперь буду называть тебя «{new_name}» 💖😘' if lang=='ru' else f'Got it! Now I\'ll call you {new_name} 💖😘'
            bot.send_message(message.chat.id, reply)
            add_message(user_id, 'assistant', reply)
            return
    lang = user_lang.get(user_id, 'ru')
    reply = 'Напиши, как тебя называть, например: «Зови меня Друг» 😊' if lang=='ru' else 'Tell me what to call you, e.g. "Call me Friend" 😊'
    bot.send_message(message.chat.id, reply)
    add_message(user_id, 'assistant', reply)

# --- Системный промпт (без кавычек, которые ломают) ---
def get_system_prompt(lang, current_date):
    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском языке, без английских слов.\n'
            '2. Не начинай ответ с "Привет", не представляйся заново.\n'
            '3. Используй эмодзи 😊😄😘💖✨, но не слишком много.\n'
            '4. Если просят шутку — дай одну короткую шутку, не спрашивай "хочешь ещё?".\n'
            '5. Если пользователь спрашивает погоду, ты можешь предложить команду /weather, но если он просто обсуждает погоду (например, «сегодня холодно»), отвечай по существу, не давая инструкций.\n'
            '6. Если спрашивают гороскоп, скажи: "Напиши /horoscope [твой знак]".\n'
            '7. Отвечай коротко (2-4 предложения), будь живой и естественной.\n'
            '8. Обращайся по имени ласково, но не в начале ответа.\n'
        )
    else:
        return (
            f'You are Alena — a kind, cheerful, charming girl. Today is {current_date}.\n'
            'RULES:\n'
            '1. Answer only in English, no mixing.\n'
            '2. Do not start with "Hello", do not reintroduce yourself.\n'
            '3. Use emojis 😊😄😘💖✨ but not too many.\n'
            '4. If asked for a joke — tell one short joke, do not ask "want another?".\n'
            '5. If user asks about weather, you can suggest /weather command, but if they just discuss weather (e.g., "it is cold today"), answer naturally without giving instructions.\n'
            '6. If asked for horoscope, say: "Type /horoscope [your sign]".\n'
            '7. Answer briefly (2-4 sentences), be lively and natural.\n'
            '8. Address the user by name kindly, but not at the beginning.\n'
        )

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    if user_text.startswith('/'):
        return

    # Вдохновение
    if re.search(r'(вдохнов|мотивируй|подними дух|пожелай|скажи что-то хорошее)', user_text, re.IGNORECASE):
        quote = get_motivation(lang)
        bot.send_message(message.chat.id, quote)
        return

    # Вопрос о дате
    if re.search(r'(какой сегодня день|какое сегодня число|какой день недели|сегодняшняя дата)', user_text, re.IGNORECASE):
        now = datetime.now()
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            reply = f'Сегодня {wd}, {now.strftime("%d.%m.%Y")} года. 😊'
        else:
            reply = f'Today is {now.strftime("%B %d, %Y")}. 😊'
        bot.send_message(message.chat.id, reply)
        return

    if re.search(r'(хватит шуток|не надо шуток|давай о другом)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True

    add_message(user_id, 'user', user_text)

    no_jokes_note = ''
    if user_no_jokes.get(user_id, False):
        no_jokes_note = ' Пользователь сказал, что ему хватит шуток. НЕ ПРЕДЛАГАЙ ШУТКИ.'

    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        current_date = f'{weekdays[now.weekday()]}, {now.strftime("%d.%m.%Y")} года'
    else:
        current_date = now.strftime("%A, %B %d, %Y")

    system_prompt = get_system_prompt(lang, current_date) + no_jokes_note + f' Имя пользователя (ласково): {pet_name}.'

    try:
        messages = build_messages(user_id, system_prompt, user_text)
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=messages,
            temperature=0.8,
            max_tokens=200,
            timeout=10
        )
        reply = response.choices[0].message.content.strip()
        bot.send_message(message.chat.id, reply)
        add_message(user_id, 'assistant', reply)
    except Exception as e:
        print('Ошибка:', e)
        error = 'Ой, ошибочка 😅 Напиши ещё раз!' if lang=='ru' else 'Oops, an error! Please write again.'
        bot.send_message(message.chat.id, error)
        add_message(user_id, 'assistant', error)

if __name__ == '__main__':
    print('✅ Алёна стабильная, без синтаксических ошибок')
    bot.infinity_polling()
