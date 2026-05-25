import os
import telebot
import re
import requests
import random
from openai import OpenAI
from collections import deque
from datetime import datetime

# --- Конфигурация ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")   # опционально

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# --- Память (как в v13: 6 сообщений) ---
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
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in get_history(user_id):
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    return messages

def reset_user(user_id):
    user_history[user_id] = deque(maxlen=6)
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

# --- Простая чистка английских слов ---
def clean_english_words(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Убираем только самые явные английские вкрапления
    text = re.sub(r'\bbirds\b', 'птички', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhappened\b', 'случилось', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpositive\b', 'позитивной', text, flags=re.IGNORECASE)
    text = re.sub(r'\benergy\b', 'энергией', text, flags=re.IGNORECASE)
    text = re.sub(r'\bResponsibility\b', 'ответственность', text, flags=re.IGNORECASE)
    text = re.sub(r'\bsuch\b', '', text, flags=re.IGNORECASE)
    return text

# --- Шутка (простая, без заморочек) ---
def get_random_joke(lang='ru'):
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Придумай одну короткую смешную шутку на русском языке, без английских слов. Только текст."}],
            temperature=0.9,
            max_tokens=100
        )
        joke = resp.choices[0].message.content.strip()
        if joke and len(joke) < 200:
            return clean_english_words(joke)
        return "Почему программисты не любят природу? Слишком много багов! 😄"
    except:
        return "Почему программисты не любят природу? Слишком много багов! 😄"

# --- Погода (только команда, без подсказок в диалоге) ---
def get_current_weather(city_name, lang='ru'):
    if not WEATHER_API_KEY:
        return "🔧 Погода временно недоступна." if lang=='ru' else "Weather unavailable."
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
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
                return (f"🌡️ *Сейчас в {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (ощущается {feels:.0f}°C)\n💧 Влажность {hum}%\n🌬️ Ветер {wind} м/с")
            else:
                return (f"🌡️ *Now in {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (feels like {feels:.0f}°C)\n💧 Humidity {hum}%\n🌬️ Wind {wind} m/s")
        else:
            return f"Город '{city_name}' не найден." if lang=='ru' else f"City '{city_name}' not found."
    except:
        return "Не удалось получить погоду." if lang=='ru' else "Weather error."

# --- Команды ---
@bot.message_handler(commands=['weather'])
def weather_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Напиши город: /weather Москва" if lang=='ru' else "Specify city: /weather London")
        return
    city = parts[1].strip()
    w = get_current_weather(city, lang)
    bot.reply_to(message, w, parse_mode='Markdown')

@bot.message_handler(commands=['date'])
def date_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        wd = weekdays[now.weekday()]
        bot.reply_to(message, f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года.")
    else:
        bot.reply_to(message, f"Today is {now.strftime('%B %d, %Y')}.")

@bot.message_handler(commands=['horoscope'])
def horoscope_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Укажи знак: /horoscope козерог" if lang=='ru' else "Specify sign: /horoscope capricorn")
        return
    sign = parts[1].strip().lower()
    signs = {'овен':'aries','телец':'taurus','близнецы':'gemini','рак':'cancer',
             'лев':'leo','дева':'virgo','весы':'libra','скорпион':'scorpio',
             'стрелец':'sagittarius','козерог':'capricorn','водолей':'aquarius','рыбы':'pisces'}
    sign_en = signs.get(sign, sign)
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        prompt = f"Составь короткое доброе предсказание для знака {sign_en.title()} на {today}. Обращайся к пользователю на 'ты'."
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        text = resp.choices[0].message.content.strip()
        if lang == 'ru':
            text = clean_english_words(text)
        bot.reply_to(message, text)
    except:
        bot.reply_to(message, "Не удалось составить гороскоп 😅" if lang=='ru' else "Horoscope error.")

@bot.message_handler(commands=['reset'])
def reset_cmd(message):
    user_id = message.from_user.id
    reset_user(user_id)
    lang = user_lang.get(user_id, 'ru')
    bot.reply_to(message, "Память очищена 😊" if lang=='ru' else "Memory cleared 😊")

# --- /start и выбор языка ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    reset_user(user_id)
    user_lang[user_id] = None
    bot.reply_to(message,
        f"✨ Привет, {pet}! ✨\n\nМеня зовут Алёна 💖 Я — твой добрый собеседник, помощник и немного волшебница 🧚‍♀️\n\nДавай выберем язык общения:\nНапиши: **Русский** или **English**\n\n✨ Hi, {pet}! ✨\n\nI'm Alena 💖 Your kind friend and helper 🧚‍♀️\n\nLet's choose the language:\nType: **Russian** or **English**")
    add_message(user_id, "assistant", "Выбор языка")

@bot.message_handler(func=lambda message: message.text and message.text.lower() in ['русский', 'russian', 'english', 'английский'])
def set_language(message):
    user_id = message.from_user.id
    text = message.text.lower()
    if text in ['русский', 'russian']:
        user_lang[user_id] = 'ru'
    else:
        user_lang[user_id] = 'en'
    pet = get_pet_name(user_id, message.from_user.first_name)
    joke = get_random_joke(user_lang[user_id])
    lang = user_lang[user_id]
    if lang == 'ru':
        reply = (f"Отлично, {pet}! Будем общаться по-русски 💖\n\n😊 Шутка для настроения: {joke}\n\nА вот что я умею: могу поболтать по душам, рассмешить шуткой, поддержать советом, вдохновить и даже составить для тебя гороскоп ✨ Просто спроси — и я рядом.\n\nРасскажи, как твои дела? 💕")
    else:
        reply = (f"Great, {pet}! We'll speak English 💖\n\n😊 A joke to cheer you up: {joke}\n\nHere's what I can do: chat from the heart, make you laugh, give advice, inspire, and even make a horoscope for you ✨ Just ask — I'm here.\n\nSo, how are you? 💕")
    bot.reply_to(message, reply)
    add_message(user_id, "assistant", reply)

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
            reply = f"Запомнила! Теперь буду называть тебя «{new_name}» 💖😘" if lang=='ru' else f"Got it! Now I'll call you {new_name} 💖😘"
            bot.reply_to(message, reply)
            add_message(user_id, "assistant", reply)
            return
    lang = user_lang.get(user_id, 'ru')
    reply = "Напиши, как тебя называть, например: «Зови меня Друг» 😊" if lang=='ru' else "Tell me what to call you, e.g. 'Call me Friend' 😊"
    bot.reply_to(message, reply)
    add_message(user_id, "assistant", reply)

# --- Системный промпт (как в v13, но без лишнего) ---
ALENA_SYSTEM_PROMPT_RU = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты уже поздоровалась при /start.\n"
    "ПРАВИЛА:\n"
    "1. Отвечай только на русском языке, без английских слов.\n"
    "2. Не начинай ответ с 'Привет', не представляйся заново.\n"
    "3. Используй эмодзи 😊😄😘💖✨, но не слишком много.\n"
    "4. Если просят шутку — дай одну короткую шутку, не спрашивай 'хочешь ещё?'.\n"
    "5. Если спрашивают погоду, скажи: 'Я могу показать прогноз по команде /weather [город]'.\n"
    "6. Если спрашивают гороскоп, скажи: 'Напиши /horoscope [твой знак]'.\n"
    "7. Отвечай коротко (2-4 предложения), будь живой и естественной.\n"
    "8. Обращайся по имени ласково.\n"
)

ALENA_SYSTEM_PROMPT_EN = (
    "You are Alena — a kind, cheerful, charming girl. You already greeted at /start.\n"
    "RULES:\n"
    "1. Answer only in English, no mixing.\n"
    "2. Don't start with 'Hello', don't reintroduce yourself.\n"
    "3. Use emojis 😊😄😘💖✨ but not too many.\n"
    "4. If asked for a joke — tell one short joke, don't ask 'want another?'.\n"
    "5. If asked about weather, say: 'I can show forecast with /weather [city]'.\n"
    "6. If asked for horoscope, say: 'Type /horoscope [your sign]'.\n"
    "7. Answer briefly (2-4 sentences), be lively and natural.\n"
    "8. Address the user by name kindly.\n"
)

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.reply_to(message, "Пожалуйста, выбери язык: напиши 'Русский' или 'English'")
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    if user_text.startswith('/'):
        return

    if re.search(r'(хватит шуток|не надо шуток|давай о другом)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True

    add_message(user_id, "user", user_text)

    no_jokes_note = ""
    if user_no_jokes.get(user_id, False):
        no_jokes_note = " Пользователь сказал, что ему хватит шуток. НЕ ПРЕДЛАГАЙ ШУТКИ."

    system_prompt = (ALENA_SYSTEM_PROMPT_RU if lang=='ru' else ALENA_SYSTEM_PROMPT_EN) + no_jokes_note + f" Имя пользователя: {pet_name}."

    try:
        messages = build_messages(user_id, system_prompt, user_text)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.8,
            max_tokens=200
        )
        reply = response.choices[0].message.content.strip()
        if lang == 'ru':
            reply = clean_english_words(reply)
        bot.reply_to(message, reply)
        add_message(user_id, "assistant", reply)
    except Exception as e:
        print("Ошибка:", e)
        error = "Ой, ошибочка 😅 Напиши ещё раз!" if lang=='ru' else "Oops, an error! Please write again."
        bot.reply_to(message, error)
        add_message(user_id, "assistant", error)

if __name__ == "__main__":
    print("✅ Алёна v13-plus — стабильная, с погодой и датой по командам, без глюков")
    bot.infinity_polling()
