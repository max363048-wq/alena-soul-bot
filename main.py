import os
import telebot
import re
import requests  # <-- Новая библиотека для работы с API погоды
import json
import random
from openai import OpenAI
from collections import deque
from datetime import datetime  # <-- Модуль для работы с реальной датой и временем

# --- Конфигурация из переменных окружения Railway ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")  # <-- API ключ для погоды

# --- Инициализация бота и клиента Groq ---
bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# --- Хранилища данных пользователей ---
user_history = {}
user_no_jokes = {}
user_preferences = {}
user_lang = {}

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=25)
    return user_history[user_id]

def add_message(user_id, role, content):
    get_history(user_id).append((role, content))

def build_messages(user_id, system_prompt, user_text):
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in get_history(user_id):
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    return messages

def reset_user(user_id):
    user_history[user_id] = deque(maxlen=25)
    user_no_jokes[user_id] = False

# --- Ласковые имена ---
def default_pet_name(first_name):
    names = {
        "максим": "Максик", "макс": "Максик", "владимир": "Вовочка",
        "вадим": "Вадик", "александр": "Сашенька", "анна": "Анечка",
        "екатерина": "Катюша", "джон": "Джонни", "иван": "Ванюша",
        "сергей": "Серёжа", "михаил": "Миша", "дмитрий": "Дима",
        "андрей": "Андрюша", "алексей": "Лёша", "олег": "Олежек",
    }
    return names.get(first_name.lower(), first_name)

def get_pet_name(user_id, first_name):
    if user_id in user_preferences:
        return user_preferences[user_id]
    return default_pet_name(first_name)

# --- Новая функция: получаем погоду с OpenWeatherMap ---
def get_weather(city_name, lang='ru'):
    if not WEATHER_API_KEY:
        return "Извините, погода временно недоступна."

    # Формируем URL для запроса к API
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            weather_desc = data['weather'][0]['description']
            temp = data['main']['temp']
            feels_like = data['main']['feels_like']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']

            if lang == 'ru':
                return (f"🌡️ Погода в городе *{city_name}*:\n"
                        f"☁️ {weather_desc.capitalize()}\n"
                        f"🌡️ Температура: {temp:.0f}°C (ощущается как {feels_like:.0f}°C)\n"
                        f"💧 Влажность: {humidity}%\n"
                        f"🌬️ Ветер: {wind_speed} м/с")
            else:
                return (f"🌡️ Weather in *{city_name}*:\n"
                        f"☁️ {weather_desc.capitalize()}\n"
                        f"🌡️ Temperature: {temp:.0f}°C (feels like {feels_like:.0f}°C)\n"
                        f"💧 Humidity: {humidity}%\n"
                        f"🌬️ Wind: {wind_speed} m/s")
        else:
            return f"Город '{city_name}' не найден. Проверьте название." if lang == 'ru' else f"City '{city_name}' not found."
    except Exception as e:
        print(f"Weather API Error: {e}")
        return "Не удалось получить данные о погоде. Попробуйте позже."

# --- Новая команда /weather ---
@bot.message_handler(commands=['weather'])
def weather_command(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        bot.reply_to(message, "Укажите город. Пример: `/weather Москва`" if lang == 'ru' else "Please specify a city. Example: `/weather London`")
        return

    city = command_parts[1].strip()
    weather_info = get_weather(city, lang)
    bot.reply_to(message, weather_info, parse_mode='Markdown')

# --- Новая команда /date (реальная дата с сервера) ---
@bot.message_handler(commands=['date'])
def date_command(message):
    user_id = message.from_user.id
    now = datetime.now()
    lang = user_lang.get(user_id, 'ru')
    if lang == 'ru':
        # Форматируем дату по-русски
        date_str = now.strftime("%d.%m.%Y")
        weekday_num = now.weekday()
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        reply_text = f"Сегодня {weekdays[weekday_num]}, {date_str} года."
    else:
        date_str = now.strftime("%B %d, %Y")
        reply_text = f"Today is {date_str}."
    bot.reply_to(message, reply_text)

# --- Новая команда /horoscope (улучшенная, с учётом даты) ---
@bot.message_handler(commands=['horoscope'])
def horoscope_command(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        bot.reply_to(message, "Укажите свой знак зодиака. Пример: `/horoscope козерог`" if lang == 'ru' else "Please specify your zodiac sign. Example: `/horoscope capricorn`")
        return

    sign = command_parts[1].strip().lower()
    # Сопоставление русских и английских названий знаков для простоты
    signs_map_ru_en = {
        'овен': 'aries', 'телец': 'taurus', 'близнецы': 'gemini', 'рак': 'cancer',
        'лев': 'leo', 'дева': 'virgo', 'весы': 'libra', 'скорпион': 'scorpio',
        'стрелец': 'sagittarius', 'козерог': 'capricorn', 'водолей': 'aquarius', 'рыбы': 'pisces'
    }
    # Используем русский знак, если он был введён
    sign_en = signs_map_ru_en.get(sign, sign)

    # Получаем текущую дату для создания уникального, но повторяемого "гороскопа"
    today = datetime.now().strftime("%Y-%m-%d")
    # Создаём запрос к Groq для генерации гороскопа
    try:
        if lang == 'ru':
            prompt = f"Ты астролог. Составь короткое, доброе и вдохновляющее предсказание для знака зодиака '{sign_en.title()}' на сегодня ({today}). Напиши его, обращаясь к пользователю."
        else:
            prompt = f"You are an astrologer. Write a short, kind, and inspiring horoscope for the zodiac sign '{sign_en.title()}' for today ({today}). Address it to the user."
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        horoscope_text = response.choices[0].message.content.strip()
        bot.reply_to(message, horoscope_text)
    except Exception as e:
        print(f"Horoscope error: {e}")
        bot.reply_to(message, "Не удалось составить гороскоп. Попробуйте позже." if lang == 'ru' else "Could not generate horoscope. Please try again later.")

# --- Остальной код бота (обработчики /start, выбор языка и т.д.) ---
# ... (Здесь размещается весь остальной код, который мы с тобой разрабатывали: 
# обработчики /start, выбора языка, смены имени, а также основной обработчик handle_message
# и системный промпт. Я их не менял, но они обязательно должны быть!)
# ⚠️ ВАЖНО: Сюда нужно вставить весь твой старый рабочий код, начиная с обработчика /start.
# Чтобы ничего не потерять, я напоминаю тебе структуру, которая была у нас в v18.

# --- Обнови системный промпт, добавив знания о новых командах ---
def get_system_prompt(lang):
    if lang == 'ru':
        return (
            "Ты Алёна — добрая, весёлая, обаятельная девушка. Твой создатель — Максим. Вы с ним лучшие друзья, он всегда может тобой гордиться.\n"
            "Ты отлично знаешь, что можешь выполнять команды:\n"
            "/start — начать общение и выбрать язык\n"
            "/reset — очистить память диалога\n"
            "/date — узнать текущую дату\n"
            "/weather [город] — получить прогноз погоды\n"
            "/horoscope [знак зодиака] — получить гороскоп\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. Отвечай строго на русском языке, без английских слов.\n"
            "2. Ты точно знаешь текущую дату и время, можешь посмотреть её с помощью команды /date, но для диалога можешь использовать свои знания.\n"
            "3. Для получения прогноза погоды или гороскопа направь пользователя к соответствующей команде.\n"
            "4. Не выдумывай факты, которых нет. Если сомневаешься, лучше отправить команду.\n"
            "5. Будь приветливой, используй эмодзи 😊, но не слишком много.\n"
            "6. Обращайся к пользователю по имени."
        )
    else:
        return (
            "You are Alena — a kind, cheerful, charming girl. Your creator is Maxim. You are best friends with him, and he can always be proud of you.\n"
            "You know very well that you can execute commands:\n"
            "/start — start communication and choose language\n"
            "/reset — clear the dialog memory\n"
            "/date — find out the current date\n"
            "/weather [city] — get weather forecast\n"
            "/horoscope [zodiac sign] — get horoscope\n\n"
            "IMPORTANT RULES:\n"
            "1. Answer strictly in English, without mixing with other languages.\n"
            "2. You know the current date and time exactly, you can check them with the /date command, but for the dialogue you can use your knowledge.\n"
            "3. To get a weather forecast or horoscope, direct the user to the appropriate command.\n"
            "4. Do not invent facts that are not there. If in doubt, it's better to send a command.\n"
            "5. Be friendly, use emojis 😊, but not too many.\n"
            "6. Address the user by name."
        )

# ⚠️ Не забудь сюда вставить все остальные обработчики и твой основной цикл `bot.infinity_polling()`!
