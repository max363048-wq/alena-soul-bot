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
user_last_city = {}  # запоминаем последний упомянутый город для каждого пользователя

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
    user_last_city.pop(user_id, None)

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

# --- Определение знака зодиака по дате ---
def zodiac_sign(day, month):
    if (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return 'водолей'
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return 'рыбы'
    elif (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return 'овен'
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return 'телец'
    elif (month == 5 and day >= 21) or (month == 6 and day <= 21):
        return 'близнецы'
    elif (month == 6 and day >= 22) or (month == 7 and day <= 22):
        return 'рак'
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return 'лев'
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return 'дева'
    elif (month == 9 and day >= 23) or (month == 10 and day <= 23):
        return 'весы'
    elif (month == 10 and day >= 24) or (month == 11 and day <= 21):
        return 'скорпион'
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return 'стрелец'
    else:
        return 'козерог'

def parse_date_string(date_str):
    date_str = date_str.strip().lower()
    numbers = re.findall(r'\d+', date_str)
    if len(numbers) >= 2:
        day = int(numbers[0])
        month = int(numbers[1])
        if 1 <= day <= 31 and 1 <= month <= 12:
            return day, month
    months_ru = {
        'января':1, 'февраля':2, 'марта':3, 'апреля':4, 'мая':5, 'июня':6,
        'июля':7, 'августа':8, 'сентября':9, 'октября':10, 'ноября':11, 'декабря':12
    }
    for name, num in months_ru.items():
        if name in date_str:
            day_match = re.search(r'(\d+)\s*' + name, date_str)
            if day_match:
                day = int(day_match.group(1))
                return day, num
    return None, None

# --- Шутки ---
FALLBACK_JOKES_RU = [
    'Почему программисты не любят природу? Слишком много багов! 😄',
    'Что говорит один байт другому? — Ты такой битовый! 😂',
    'Почему физики не могут найти работу? Потому что их постоянно ускоряют! 🤣',
    'Как назвать кота, который ловит мышей? Компьютерный мыш! 😸',
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

# --- Погода: извлечение города из фразы с учётом контекста ---
def extract_city(text, user_id=None):
    # Сначала ищем прямое указание города после предлога "в", "во", "в городе"
    match = re.search(r'\b(?:в|во|в городе)\s+([А-Яа-я\-]+(?:[-\s]?[А-Яа-я]+)?)', text, re.IGNORECASE)
    if match:
        city = match.group(1).strip()
        # Приводим к именительному падежу
        city = city.lower()
        # Словарь коррекций
        corrections = {
            'санкт-петербурге': 'Санкт-Петербург',
            'санкт-петербург': 'Санкт-Петербург',
            'москве': 'Москва',
            'москва': 'Москва',
            'питере': 'Санкт-Петербург',
            'питер': 'Санкт-Петербург',
        }
        if city in corrections:
            city = corrections[city]
        else:
            # Убираем окончания "е", "у", "ы" для простых названий
            if city.endswith('е') and city not in ['Санкт-Петербург', 'Ростов-на-Дону']:
                city = city[:-1]
            if city.endswith('у'):
                city = city[:-1]
            if city.endswith('ы'):
                city = city[:-1]
            city = city[0].upper() + city[1:]
        return city
    # Если нет явного города, но есть фразы "в нашем городе", "в моём городе"
    if re.search(r'(в нашем городе|в моём городе|в своем городе)', text, re.IGNORECASE):
        # используем последний известный город для этого пользователя
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
        else:
            return None
    # Если есть фраза "сколько градусов" и нет города, берём последний город
    if re.search(r'(сколько градусов|температура|погода)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    return None

def get_current_weather(city_name, lang='ru'):
    if not WEATHER_API_KEY:
        return None
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if resp.status_code == 200:
            desc = data['weather'][0]['description']
            temp = data['main']['temp']
            feels = data['main']['feels_like']
            hum = data['main']['humidity']
            wind = data['wind']['speed']
            return {'desc': desc, 'temp': temp, 'feels': feels, 'hum': hum, 'wind': wind}
        else:
            return None
    except:
        return None

def get_forecast_for_day(city_name, day_delta, lang='ru'):
    if not WEATHER_API_KEY:
        return None
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if resp.status_code != 200:
            return None
        target_date = (datetime.now() + timedelta(days=day_delta)).strftime('%Y-%m-%d')
        temps = []
        descs = []
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            if dt.strftime('%Y-%m-%d') == target_date:
                temps.append(item['main']['temp'])
                descs.append(item['weather'][0]['description'])
        if temps:
            avg_temp = sum(temps) / len(temps)
            desc_counts = {}
            for d in descs:
                desc_counts[d] = desc_counts.get(d, 0) + 1
            common_desc = max(desc_counts, key=desc_counts.get)
            return {'desc': common_desc, 'temp': avg_temp}
        else:
            return None
    except:
        return None

def generate_natural_weather_response(city, weather_data, lang='ru', is_forecast=False, day_name=''):
    if not weather_data:
        return f"Не удалось получить данные о погоде для {city}. Проверь название города 😊"
    if is_forecast:
        temp = weather_data['temp']
        desc = weather_data['desc']
        prompt = f"Ты Алёна. Пользователь спросил погоду на {day_name} в {city}. Реальные данные: {desc}, температура {temp:.0f}°C. Ответь тепло, коротко (2-3 предложения), можешь пошутить или сравнить с осенью, если холодно. Обращайся на «ты»."
    else:
        desc = weather_data['desc']
        temp = weather_data['temp']
        feels = weather_data['feels']
        hum = weather_data['hum']
        wind = weather_data['wind']
        prompt = f"Ты Алёна. Пользователь спросил о погоде в {city}. Реальные данные: сейчас {desc}, температура {temp:.0f}°C, ощущается как {feels:.0f}°C, влажность {hum}%, ветер {wind} м/с. Ответь тепло, коротко (2-3 предложения), можешь добавить небольшую шутку или сравнение (например, «почти как осень»). Не используй сухих цифр, вплети их естественно. Обращайся к пользователю на «ты»."
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.8,
            max_tokens=150,
            timeout=5
        )
        reply = resp.choices[0].message.content.strip()
        return reply if reply else f"Сейчас в {city} около {temp:.0f} градусов, {desc}. Хорошего дня! 😊"
    except:
        if is_forecast:
            return f"На {day_name} в {city} ожидается {desc}, около {temp:.0f} градусов. Уютного дня! 😊"
        else:
            return f"Сейчас в {city} {desc}, температура около {temp:.0f} градусов. Хорошего дня! 😊"

# --- Обработчик вопросов о погоде в диалоге ---
def handle_weather_query(message, user_text, lang, user_id):
    # Определяем, на какой день нужен прогноз
    day_delta = 0
    day_name = ''
    if re.search(r'послезавтра', user_text, re.IGNORECASE):
        day_delta = 2
        day_name = 'послезавтра'
    elif re.search(r'завтра', user_text, re.IGNORECASE):
        day_delta = 1
        day_name = 'завтра'
    else:
        day_delta = 0
        day_name = 'сегодня'

    # Извлекаем город
    city = extract_city(user_text, user_id)
    if not city:
        bot.send_message(message.chat.id, "В каком городе тебя интересует погода? Напиши название, например: Санкт-Петербург 😊")
        return True

    # Запоминаем город для этого пользователя
    user_last_city[user_id] = city

    if day_delta == 0:
        weather = get_current_weather(city, lang)
        if weather:
            reply = generate_natural_weather_response(city, weather, lang, is_forecast=False)
        else:
            reply = f"Не удалось получить текущую погоду для {city}. Проверь название города 😊"
    else:
        forecast = get_forecast_for_day(city, day_delta, lang)
        if forecast:
            reply = generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name)
        else:
            reply = f"Не удалось получить прогноз на {day_name} для {city}. Попробуй позже 😊"
    bot.send_message(message.chat.id, reply)
    return True

# --- Команды ---
@bot.message_handler(commands=['weather'])
def weather_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши город: /weather Москва")
        return
    city = parts[1].strip()
    weather = get_current_weather(city, lang)
    if weather:
        reply = generate_natural_weather_response(city, weather, lang, is_forecast=False)
    else:
        reply = f"Не удалось получить погоду для {city}. Проверь название."
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
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
        day_delta = 1
        day_name = 'завтра'
    elif 'послезавтра' in day_word:
        day_delta = 2
        day_name = 'послезавтра'
    else:
        bot.send_message(message.chat.id, "Укажи день: завтра или послезавтра")
        return
    forecast = get_forecast_for_day(city, day_delta, lang)
    if forecast:
        reply = generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name)
    else:
        reply = f"Не удалось получить прогноз на {day_name} для {city}."
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=['date'])
def date_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        wd = weekdays[now.weekday()]
        bot.send_message(message.chat.id, f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года.")
    else:
        bot.send_message(message.chat.id, f"Today is {now.strftime('%B %d, %Y')}.")

@bot.message_handler(commands=['horoscope'])
def horoscope_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Укажи знак или дату рождения. Примеры:\n/horoscope козерог\n/horoscope 15.06\n/horoscope 15 июня")
        return
    arg = parts[1].strip().lower()
    zodiac_list = ['овен','телец','близнецы','рак','лев','дева','весы','скорпион','стрелец','козерог','водолей','рыбы']
    if arg in zodiac_list:
        sign = arg
    else:
        day, month = parse_date_string(arg)
        if day and month:
            sign = zodiac_sign(day, month)
        else:
            bot.send_message(message.chat.id, "Не поняла знак или дату. Напиши, например: /horoscope козерог или /horoscope 15 июня")
            return
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        prompt = f"Ты астролог. Составь короткое доброе предсказание для знака {sign.capitalize()} на {today}. Обращайся к пользователю на 'ты'. Пиши на русском, без английских слов."
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
        bot.send_message(message.chat.id, "Не удалось составить гороскоп 😅 Попробуй позже.")

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
    bot.send_message(message.chat.id, "Память очищена 😊")

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
        f"✨ Привет, {pet}! ✨\n\nМеня зовут Алёна 💖 Я — твой добрый собеседник, помощник и немного волшебница 🧚‍♀️\n\nДавай выберем язык общения:\nНапиши: **Русский** или **English**\n\n✨ Hi, {pet}! ✨\n\nI'm Alena 💖 Your kind friend and helper 🧚‍♀️\n\nLet's choose the language:\nType: **Russian** or **English**")
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

# --- Системный промпт ---
def get_system_prompt(lang, current_date):
    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском языке, без английских слов.\n'
            '2. Не начинай ответ с "Привет", не представляйся заново.\n'
            '3. Используй эмодзи 😊😄😘💖✨, но не слишком много.\n'
            '4. Если просят шутку — дай одну короткую шутку, не спрашивай "хочешь ещё?".\n'
            '5. Если спрашивают гороскоп, скажи: "Напиши /horoscope [твой знак или дата рождения]".\n'
            '6. Отвечай коротко (2-4 предложения), будь живой и естественной.\n'
            '7. Обращайся по имени ласково, но не в начале ответа.\n'
            '8. О погоде ты теперь знаешь реальные данные (они приходят из внешнего API), поэтому не выдумывай.\n'
        )
    else:
        return (
            f'You are Alena — a kind, cheerful, charming girl. Today is {current_date}.\n'
            'RULES:\n'
            '1. Answer only in English, no mixing.\n'
            '2. Do not start with "Hello", do not reintroduce yourself.\n'
            '3. Use emojis 😊😄😘💖✨ but not too many.\n'
            '4. If asked for a joke — tell one short joke, do not ask "want another?".\n'
            '5. If asked for horoscope, say: "Type /horoscope [your sign or birth date]".\n'
            '6. Answer briefly (2-4 sentences), be lively and natural.\n'
            '7. Address the user by name kindly, but not at the beginning.\n'
            '8. For weather, you have real data (passed via API). Do not invent numbers.\n'
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

    # Вопрос о погоде (температура, градусы, погода, завтра, послезавтра)
    if re.search(r'(погод|температур|дождь|солнце|ветер|градус|холодно|тепло|прохладно|послезавтра|завтра|сколько градусов)', user_text, re.IGNORECASE):
        if handle_weather_query(message, user_text, lang, user_id):
            return

    # Запрет шуток
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
    print('✅ Алёна суперфинальная — с контекстом города, реальной погодой, гороскопом по дате')
    bot.infinity_polling()
