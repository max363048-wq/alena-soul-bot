import os
import telebot
import re
import requests
import random
import base64
from openai import OpenAI
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Deque, Optional, List, Any

# --- Конфигурация ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')

BOT_USERNAME = 'AlenaSoul_bot'

# --- Конфигурация для фотографий ---
PHOTO_FOLDER = 'images'
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif')
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_BASE64_SIZE = 4 * 1024 * 1024

# --- Память и состояния ---
user_history: Dict[int, Deque] = {}
user_no_jokes: Dict[int, bool] = {}
user_preferences: Dict[int, str] = {}
user_lang: Dict[int, str] = {}
user_last_city: Dict[int, str] = {}
user_last_photos: Dict[int, deque] = {}    # последние 3 показанных фото
user_no_photos: Dict[int, bool] = {}       # пользователь сказал, что у него нет фото

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
    user_last_photos.pop(user_id, None)
    user_no_photos.pop(user_id, None)

# --- Ласковые имена ---
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

# --- Знаки зодиака ---
def zodiac_sign(day: int, month: int) -> str:
    if (month == 1 and day >= 20) or (month == 2 and day <= 18): return 'водолей'
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20): return 'рыбы'
    elif (month == 3 and day >= 21) or (month == 4 and day <= 19): return 'овен'
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20): return 'телец'
    elif (month == 5 and day >= 21) or (month == 6 and day <= 21): return 'близнецы'
    elif (month == 6 and day >= 22) or (month == 7 and day <= 22): return 'рак'
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22): return 'лев'
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22): return 'дева'
    elif (month == 9 and day >= 23) or (month == 10 and day <= 23): return 'весы'
    elif (month == 10 and day >= 24) or (month == 11 and day <= 21): return 'скорпион'
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21): return 'стрелец'
    else: return 'козерог'

def parse_date_string(date_str: str) -> tuple:
    date_str = date_str.strip().lower()
    numbers = re.findall(r'\d+', date_str)
    if len(numbers) >= 2:
        day, month = int(numbers[0]), int(numbers[1])
        if 1 <= day <= 31 and 1 <= month <= 12:
            return day, month
    months_ru = {'января':1,'февраля':2,'марта':3,'апреля':4,'мая':5,'июня':6,
                 'июля':7,'августа':8,'сентября':9,'октября':10,'ноября':11,'декабря':12}
    for name, num in months_ru.items():
        if name in date_str:
            match = re.search(r'(\d+)\s*' + name, date_str)
            if match:
                return int(match.group(1)), num
    return None, None

# --- Шутки ---
FALLBACK_JOKES_RU = [
    'Почему программисты не любят природу? Слишком много багов! 😄',
    'Что говорит один байт другому? — Ты такой битовый! 😂',
    'Почему физики не могут найти работу? Потому что их постоянно ускоряют! 🤣',
]

def is_virus_joke(text: str) -> bool:
    text_lower = text.lower()
    return ('компьютер' in text_lower and 'вирус' in text_lower) or ('компьютер' in text_lower and 'врач' in text_lower)

def get_random_joke(lang: str = 'ru') -> str:
    if lang != 'ru':
        return "Why don't programmers like nature? Too many bugs! 😄"
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Придумай одну короткую смешную шутку на русском языке без английских слов.'}],
            temperature=0.9, max_tokens=100, timeout=5
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
        return random.choice(MOTIVATION_FALLBACK)
    except:
        return random.choice(MOTIVATION_FALLBACK)

# --- Чистка английских слов ---
def clean_english_words(text: str) -> str:
    if not text:
        return text
    reps = {
        r'\balmost\b': 'почти', r'\btemperature\b': 'температура', r'\bdegrees?\b': 'градусов',
        r'\bso\b': 'так что', r'\bbut\b': 'но', r'\band\b': 'и', r'\bok\b': 'хорошо',
        r'\bplease\b': 'пожалуйста', r'\bsorry\b': 'извини', r'\bthanks\b': 'спасибо',
        r'\bhello\b': 'привет', r'\bhi\b': 'привет', r'\bgreat\b': 'отлично', r'\bgood\b': 'хороший',
        r'\bvery\b': 'очень', r'\blike\b': 'как', r'\breally\b': 'действительно',
        r'\bwhat\b': 'что', r'\bwhy\b': 'почему', r'\byes\b': 'да', r'\bno\b': 'нет',
        r'\bI\b': 'я', r'\byou\b': 'ты', r'\bwe\b': 'мы', r'\bthey\b': 'они',
        r'\bfor\b': 'для', r'\bwith\b': 'с', r'\bfrom\b': 'из', r'\bto\b': 'в',
        r'\bof\b': '', r'\bthe\b': '', r'\ba\b': '', r'\ban\b': '', r'\bnot\b': 'не'
    }
    for eng, rus in reps.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- Погода (сокращённо, но все функции есть) ---
def extract_city(text: str, user_id: Optional[int] = None) -> Optional[str]:
    match = re.search(r'\b(?:в|во|в городе)\s+([А-Яа-я\-]+(?:[-\s]?[А-Яа-я]+)?)', text, re.IGNORECASE)
    if match:
        city = match.group(1).strip().lower()
        corrections = {
            'санкт-петербурге': 'Санкт-Петербург', 'санкт-петербург': 'Санкт-Петербург',
            'москве': 'Москва', 'москва': 'Москва', 'питере': 'Санкт-Петербург', 'питер': 'Санкт-Петербург'
        }
        if city in corrections:
            city = corrections[city]
        else:
            if city.endswith('е') and city not in ['Санкт-Петербург', 'Ростов-на-Дону']:
                city = city[:-1]
            if city.endswith('у'): city = city[:-1]
            if city.endswith('ы'): city = city[:-1]
            city = city[0].upper() + city[1:]
        return city
    if re.search(r'(у нас|в нашем городе|в моём городе|в своем городе|в нашем)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    if re.search(r'(завтра|послезавтра|будет)', text, re.IGNORECASE) and re.search(r'(погод|температур|дождь|солнце|ветер|градусов)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    if re.search(r'(сколько градусов|температура|погода|градусов|холодно|тепло)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    return None

def is_weather_query(text: str) -> bool:
    if re.search(r'(какая погода|какой прогноз|что с погодой|сколько градусов|температура какая|будет завтра|будет послезавтра|завтра погода|послезавтра погода)', text, re.IGNORECASE):
        return True
    if re.search(r'(будет|ожидается|прогноз|скажи|покажи).*(погод|температур|дождь|солнце|ветер)', text, re.IGNORECASE):
        return True
    return False

def get_current_weather(city_name: str, lang: str = 'ru') -> Optional[Dict]:
    if not WEATHER_API_KEY:
        return None
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if resp.status_code == 200:
            return {
                'desc': data['weather'][0]['description'],
                'temp': data['main']['temp'],
                'feels': data['main']['feels_like'],
                'hum': data['main']['humidity'],
                'wind': data['wind']['speed']
            }
        return None
    except:
        return None

def get_forecast_for_day(city_name: str, day_delta: int, lang: str = 'ru') -> Optional[Dict]:
    if not WEATHER_API_KEY:
        return None
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if resp.status_code != 200:
            return None
        target_date = (datetime.now() + timedelta(days=day_delta)).strftime('%Y-%m-%d')
        temps, descs = [], []
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            if dt.strftime('%Y-%m-%d') == target_date:
                temps.append(item['main']['temp'])
                descs.append(item['weather'][0]['description'])
        if temps:
            return {'desc': max(set(descs), key=descs.count), 'temp': sum(temps)/len(temps)}
        return None
    except:
        return None

def generate_natural_weather_response(city: str, weather_data: Dict, lang: str = 'ru', is_forecast: bool = False, day_name: str = '') -> str:
    if not weather_data:
        return f"Не удалось получить данные о погоде для {city}. Проверь название города 😊"
    if is_forecast:
        temp = weather_data['temp']
        desc = weather_data['desc']
        fallback = f"На {day_name} в {city} ожидается {desc}, около {temp:.0f} градусов. Уютного дня! 😊"
        prompt = f"Ты Алёна. Пользователь спросил погоду на {day_name} в {city}. Реальные данные: {desc}, температура {temp:.0f}°C. Ответь тепло, коротко (2-3 предложения). НЕ ВЫДУМЫВАЙ СВОИ ЦИФРЫ! Используй именно {temp:.0f}°C и описание {desc}. Можешь добавить сравнение с осенью, если холодно. Без английских слов."
    else:
        desc = weather_data['desc']
        temp = weather_data['temp']
        feels = weather_data['feels']
        hum = weather_data['hum']
        wind = weather_data['wind']
        fallback = f"Сейчас в {city} {desc}, температура около {temp:.0f} градусов (ощущается как {feels:.0f}). Влажность {hum}%, ветер {wind} м/с. Хорошего дня! 😊"
        prompt = f"Ты Алёна. Пользователь спросил о погоде в {city}. Реальные данные: сейчас {desc}, температура {temp:.0f}°C, ощущается как {feels:.0f}°C, влажность {hum}%, ветер {wind} м/с. Ответь тепло, коротко (2-3 предложения). НИКАКИХ ВЫДУМАННЫХ ЦИФР! Используй только эти: {temp:.0f}°C, {desc}. Можешь пошутить про осень, если холодно. Без английских слов."
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=150, timeout=5
        )
        reply = resp.choices[0].message.content.strip()
        reply = clean_english_words(reply)
        temp_int = int(round(temp))
        if str(temp_int) not in reply and str(temp_int+1) not in reply and str(temp_int-1) not in reply:
            return fallback
        return reply
    except:
        return fallback

def handle_weather_query(message: telebot.types.Message, user_text: str, lang: str, user_id: int) -> bool:
    if not is_weather_query(user_text):
        return False
    day_delta = 0
    day_name = ''
    if re.search(r'послезавтра', user_text, re.IGNORECASE):
        day_delta, day_name = 2, 'послезавтра'
    elif re.search(r'завтра', user_text, re.IGNORECASE):
        day_delta, day_name = 1, 'завтра'
    else:
        day_delta, day_name = 0, 'сегодня'
    city = extract_city(user_text, user_id)
    if not city:
        bot.send_message(message.chat.id, "В каком городе тебя интересует погода? Напиши название, например: Санкт-Петербург 😊")
        add_message(user_id, 'user', user_text)
        return True
    user_last_city[user_id] = city
    add_message(user_id, 'user', user_text)
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
    add_message(user_id, 'assistant', reply)
    return True

# --- Команды ---
@bot.message_handler(commands=['weather'])
def weather_cmd(message: telebot.types.Message) -> None:
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
        reply = f"Не удалось получить погоду для {city}."
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message: telebot.types.Message) -> None:
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
        day_delta, day_name = 1, 'завтра'
    elif 'послезавтра' in day_word:
        day_delta, day_name = 2, 'послезавтра'
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
def date_cmd(message: telebot.types.Message) -> None:
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
def horoscope_cmd(message: telebot.types.Message) -> None:
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
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        prompt = f"Ты астролог. Составь короткое доброе предсказание для знака {sign.capitalize()} на {today}. Обращайся к пользователю на 'ты'. Пиши на русском, без английских слов."
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=300, timeout=5
        )
        text = resp.choices[0].message.content.strip()
        text = clean_english_words(text)
        bot.send_message(message.chat.id, text)
    except:
        bot.send_message(message.chat.id, "Не удалось составить гороскоп 😅 Попробуй позже.")

@bot.message_handler(commands=['quote'])
def quote_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    quote = get_motivation(lang)
    bot.send_message(message.chat.id, quote)

@bot.message_handler(commands=['reset'])
def reset_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    reset_user(user_id)
    bot.send_message(message.chat.id, "Память очищена 😊")

# --- Функции для работы с фотографиями (упрощённые, без поиска по ключевым словам) ---
def get_photo_list() -> List[str]:
    if not os.path.exists(PHOTO_FOLDER):
        os.makedirs(PHOTO_FOLDER, exist_ok=True)
        return []
    return [os.path.join(PHOTO_FOLDER, f) for f in os.listdir(PHOTO_FOLDER) if f.lower().endswith(SUPPORTED_EXTENSIONS)]

def get_random_photo_excluding(user_id: int) -> Optional[str]:
    available = get_photo_list()
    if not available:
        return None
    # Храним последние 3 показанных фото
    last_photos = user_last_photos.get(user_id, deque(maxlen=3))
    # Ищем фото, которое не в списке последних
    candidates = [p for p in available if p not in last_photos]
    if not candidates:
        candidates = available  # если все фото уже показаны, показываем любое
    chosen = random.choice(candidates)
    # Обновляем историю
    if user_id not in user_last_photos:
        user_last_photos[user_id] = deque(maxlen=3)
    user_last_photos[user_id].append(chosen)
    return chosen

def analyze_image_with_vision(image_path: str, prompt: str, lang: str = 'ru') -> str:
    try:
        file_size = os.path.getsize(image_path)
        if file_size > MAX_BASE64_SIZE:
            return "Файл слишком большой, попробуй сжать изображение."
        with open(image_path, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        mime_type = "image/jpeg"
        if image_path.lower().endswith('.png'):
            mime_type = "image/png"
        elif image_path.lower().endswith('.gif'):
            mime_type = "image/gif"
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                    ]
                }
            ],
            temperature=0.7,
            max_tokens=500,
            timeout=15
        )
        analysis = response.choices[0].message.content.strip()
        if lang == 'ru':
            analysis = clean_english_words(analysis)
        return analysis
    except Exception as e:
        print(f"Ошибка анализа: {e}")
        return "Ой, что-то пошло не так при анализе фото. Попробуй ещё раз 😅"

def analyze_user_image(message: telebot.types.Message, lang: str) -> bool:
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_path = f"temp_user_image_{message.from_user.id}_{int(time.time())}.jpg"
        with open(temp_path, 'wb') as f:
            f.write(downloaded_file)
        if lang == 'ru':
            prompt = "Ты Алёна, добрая, весёлая, обаятельная девушка. Твой друг прислал тебе фото. Посмотри на это фото и сразу, без лишних вопросов, опиши, что ты видишь, как тебе это фото, что оно у тебя вызывает. Будь тёплой, живой, можешь добавить эмодзи и немного пошутить. Если на фото человек, сделай ему приятный комплимент. Если это пейзаж, поделись впечатлениями. Отвечай прямо сейчас, как в обычном разговоре. Не начинай ответ с 'Привет'."
        else:
            prompt = "You are Alena, a kind, cheerful, charming girl. Your friend sent you a photo. Look at it and immediately, without unnecessary questions, describe what you see, how you like it, what it evokes in you. Be warm, lively, add emojis and a little joke. If there is a person in the photo, give them a nice compliment. If it's a landscape, share your impressions. Answer right now, as in a normal conversation. Do not start with 'Hello'."
        description = analyze_image_with_vision(temp_path, prompt, lang)
        os.remove(temp_path)
        bot.send_message(message.chat.id, description)
        return True
    except Exception as e:
        print(f"Ошибка обработки фото пользователя: {e}")
        if lang == 'ru':
            bot.send_message(message.chat.id, "Что-то не так с фото, может, попробуешь другое? 😊")
        else:
            bot.send_message(message.chat.id, "Something's wrong with the photo, maybe try another one? 😊")
        return False

# --- /start и выбор языка ---
@bot.message_handler(commands=['start'])
def send_welcome(message: telebot.types.Message) -> None:
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
def set_language(message: telebot.types.Message) -> None:
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
def change_name(message: telebot.types.Message) -> None:
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
def get_system_prompt(lang: str, current_date: str) -> str:
    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском, без английских слов.\n'
            '2. Не начинай ответ с "Привет", не представляйся заново.\n'
            '3. Используй эмодзи 😊😄😘💖✨, но не слишком много.\n'
            '4. Если просят шутку — дай одну короткую шутку, не спрашивай "хочешь ещё?".\n'
            '5. Если спрашивают гороскоп, скажи: "Напиши /horoscope [твой знак или дата рождения]".\n'
            '6. Отвечай коротко (2-4 предложения), будь живой.\n'
            '7. Обращайся по имени ласково, но не в начале ответа.\n'
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
            '6. Answer briefly (2-4 sentences), be lively.\n'
            '7. Address the user by name kindly, but not at the beginning.\n'
        )

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    user_text = message.text if message.text else ''

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    # --- Обработка фото от пользователя ---
    if message.content_type == 'photo':
        if user_no_photos.get(user_id):
            user_no_photos[user_id] = False
        analyze_user_image(message, lang)
        return

    if user_text.startswith('/'):
        return

    # --- Если пользователь говорит, что у него нет фото ---
    if re.search(r'(нет фото|нет своих фото|не снимаюсь|не люблю фоткаться|нет моих фото|не фотографируюсь)', user_text, re.IGNORECASE):
        user_no_photos[user_id] = True
        reply = (
            "Как жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой. "
            "Если хочешь, можешь показать какую‑нибудь картинку или фото – мы вместе посмеёмся или просто продолжим общаться 💕"
        ) if lang == 'ru' else (
            "What a pity, I would love to see you! 😊 But it's okay, I feel good with you anyway. "
            "If you want, you can show me some picture or photo – we'll laugh together or just continue chatting 💕"
        )
        bot.send_message(message.chat.id, reply)
        return

    # --- Проверка на просьбу показать свои фото (упрощённая, без поиска по ключевым словам) ---
    if re.search(r'(покажи свои фото|покажи фото|фотоальбом|покажи себя|своё фото|свое фото|мои фото|свои фотографии|покажи альбом|покажи где ты была|покажи, где ты|покажи картинку|покажи изображение|есть фото|есть ли у тебя фото|посмотреть твои фото|покажи свои фотографии|любимое фото|есть еще фото|другие фото|покажи другое фото|ещё фото|какое твое любимое фото|покажи любимое фото|покажи другое)', user_text, re.IGNORECASE):
        available_photos = get_photo_list()
        if not available_photos:
            msg = "У меня ещё нет фотоальбома, но Максик обещал скоро добавить! 😊" if lang == 'ru' else "I don't have a photo album yet, but Max promised to add it soon! 😊"
            bot.send_message(message.chat.id, msg)
            return
        photo_path = get_random_photo_excluding(user_id)
        if not photo_path:
            msg = "Не могу найти фото в моём альбоме... Попробуй спросить что-то другое 😊" if lang == 'ru' else "I can't find a photo in my album... Try asking something else 😊"
            bot.send_message(message.chat.id, msg)
            return
        try:
            # Если в запросе есть "любимое", подчеркнём
            if re.search(r'любимое', user_text, re.IGNORECASE):
                analysis_prompt = "Ты Алёна. Это одно из твоих любимых фото. Посмотри на него и опиши, что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи, почему это фото тебе особенно дорого. Будь живой и тёплой, как в обычном разговоре. Расскажи короткую историю об этом моменте. Не начинай ответ с 'Привет'."
            else:
                analysis_prompt = "Ты Алёна. Это одно из твоих фото. Посмотри на него и опиши, что ты на нём делаешь, где ты, какое у тебя настроение. Будь живой и тёплой, как в обычном разговоре. Расскажи короткую историю об этом моменте. Не начинай ответ с 'Привет'."
            description = analyze_image_with_vision(photo_path, analysis_prompt, lang)
            with open(photo_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=description)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")
            error_msg = "Не могу отправить фото, что-то пошло не так 😅" if lang == 'ru' else "I can't send the photo, something went wrong 😅"
            bot.send_message(message.chat.id, error_msg)
        return

    # --- Вдохновение ---
    if re.search(r'(вдохнов|мотивируй|подними дух|пожелай|скажи что-то хорошее)', user_text, re.IGNORECASE):
        bot.send_message(message.chat.id, get_motivation(lang))
        return

    # --- Вопрос о дате ---
    if re.search(r'(какой сегодня день|какое сегодня число|какой день недели|сегодняшняя дата)', user_text, re.IGNORECASE):
        now = datetime.now()
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            bot.send_message(message.chat.id, f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊")
        else:
            bot.send_message(message.chat.id, f"Today is {now.strftime('%B %d, %Y')}. 😊")
        return

    # --- Погода ---
    if handle_weather_query(message, user_text, lang, user_id):
        return

    # --- Запрет шуток ---
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
            temperature=0.8, max_tokens=200, timeout=10
        )
        reply = response.choices[0].message.content.strip()
        reply = clean_english_words(reply)
        bot.send_message(message.chat.id, reply)
        add_message(user_id, 'assistant', reply)
    except Exception as e:
        print('Ошибка:', e)
        error = 'Ой, ошибочка 😅 Напиши ещё раз!' if lang=='ru' else 'Oops, an error! Please write again.'
        bot.send_message(message.chat.id, error)
        add_message(user_id, 'assistant', error)

if __name__ == '__main__':
    print('✅ Алёна финальная — упрощённый показ фото, запоминание последних 3, запрет "Привет" в описаниях')
    bot.infinity_polling()
