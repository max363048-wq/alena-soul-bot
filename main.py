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
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# --- Хранилища ---
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

# --- Локальные шутки (запасной вариант) ---
JOKES_RU = [
    "Почему программисты не любят природу? Слишком много багов! 😄",
    "Что говорит один байт другому? — Ты такой битовый! 😂",
    "Почему физики не могут найти работу? Потому что их постоянно ускоряют! 🤣",
    "Как назвать кота, который ловит мышей? Компьютерный мыш! 😸",
    "Почему рыбы не играют в шахматы? Они боятся ладей! 🐟",
    "Что общего между пиццей и программистом? Оба могут быть с разными начинками! 🍕",
    "Почему понедельник пошёл к психологу? Потому что у него был кризис вторника! 😂"
]

JOKES_EN = [
    "Why don't programmers like nature? Too many bugs! 😄",
    "What does one byte say to another? You look a bit off! 😂",
    "Why did the computer go to the doctor? It had a virus! 🤣",
    "Why don't fish play chess? They're afraid of rooks! 🐟",
    "What do you call a cat that catches mice? A computer mouse! 😸"
]

def get_random_joke(lang='ru'):
    # Сначала пробуем через Groq
    try:
        if lang == 'ru':
            prompt = "на русском языке, без английских слов. Только текст шутки."
        else:
            prompt = "in English, without mixing languages. Only the joke text."
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"Ты автор шуток. Напиши одну короткую смешную шутку {prompt}"},
                {"role": "user", "content": "Придумай случайную шутку"}
            ],
            temperature=0.9,
            max_tokens=100,
            timeout=5
        )
        joke = response.choices[0].message.content.strip()
        if joke and len(joke) < 200:
            return joke
    except Exception as e:
        print("Joke API error:", e)
    # Запасной вариант: локальные шутки
    if lang == 'ru':
        return random.choice(JOKES_RU)
    else:
        return random.choice(JOKES_EN)

# --- Погода и прогноз (как в v23) ---
def remove_cjk(text: str) -> str:
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u20000-\u2a6df\u3000-\u303f]', re.UNICODE)
    return cjk_pattern.sub('', text)

def clean_text(text: str, lang: str) -> str:
    if lang != 'ru':
        return text
    text = remove_cjk(text)
    replacements = {
        r'\bsuch\b': '', r'\bpositive\b': 'позитивной', r'\benergy\b': 'энергией',
        r'\bResponsibility\b': 'ответственность', r'\bhappiness\b': 'счастье',
        r'\bfriend\b': 'друг', r'\bweek\b': 'неделя', r'\bday\b': 'день',
        r'\btime\b': 'время', r'\blife\b': 'жизнь', r'\bgood\b': 'хорошее',
        r'\bgreat\b': 'отличное', r'\bok\b': 'хорошо', r'\bsorry\b': 'извини',
        r'\bplease\b': 'пожалуйста', r'\bhello\b': 'привет', r'\bhi\b': 'привет',
        r'\bthanks\b': 'спасибо', r'\bthank you\b': 'спасибо', r'\bso\b': 'так что',
        r'\bbut\b': 'но', r'\band\b': 'и', r'\bfor\b': 'для', r'\bwith\b': 'с',
        r'\bfrom\b': 'из', r'\bto\b': 'в', r'\bof\b': '', r'\bthe\b': '',
        r'\ba\b': '', r'\ban\b': '', r'\bI\b': 'я', r'\byou\b': 'ты',
        r'\bwe\b': 'мы', r'\bthey\b': 'они', r'\bit\b': 'это', r'\bis\b': 'есть',
        r'\bare\b': 'есть', r'\bwas\b': 'был', r'\bwere\b': 'были', r'\bhave\b': 'иметь',
        r'\bhas\b': 'имеет', r'\bdo\b': 'делать', r'\bdoes\b': 'делает',
        r'\bcan\b': 'могу', r'\bwill\b': 'буду', r'\bwould\b': 'бы',
        r'\bcould\b': 'мог', r'\bshould\b': 'следует', r'\bmay\b': 'может',
    }
    for eng, rus in replacements.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
                result = (f"🌡️ *Сейчас в {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (ощущается {feels:.0f}°C)\n💧 Влажность {hum}%\n🌬️ Ветер {wind} м/с")
                result += f"\n\n✨ Хочешь узнать прогноз на неделю? Напиши: `/weather {city_name} неделя`"
                return result
            else:
                result = (f"🌡️ *Now in {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (feels like {feels:.0f}°C)\n💧 Humidity {hum}%\n🌬️ Wind {wind} m/s")
                result += f"\n\n✨ Want a weekly forecast? Type: `/weather {city_name} week`"
                return result
        else:
            return f"Город '{city_name}' не найден." if lang=='ru' else f"City '{city_name}' not found."
    except:
        return "Не удалось получить погоду." if lang=='ru' else "Weather error."

def get_forecast(city_name, lang='ru'):
    if not WEATHER_API_KEY:
        return "🔧 Прогноз временно недоступен." if lang=='ru' else "Forecast unavailable."
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang={lang}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if resp.status_code != 200:
            return f"Город '{city_name}' не найден." if lang=='ru' else f"City '{city_name}' not found."
        forecasts = []
        seen_dates = set()
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            date_str = dt.strftime('%d.%m' if lang=='ru' else '%m/%d')
            if date_str not in seen_dates:
                seen_dates.add(date_str)
                temp = item['main']['temp']
                desc = item['weather'][0]['description']
                forecasts.append(f"{date_str}: {desc.capitalize()}, {temp:.0f}°C")
            if len(forecasts) >= 5:
                break
        if lang == 'ru':
            return f"📅 *Прогноз для {city_name} на ближайшие дни:*\n" + "\n".join(forecasts)
        else:
            return f"📅 *Forecast for {city_name} for the next days:*\n" + "\n".join(forecasts)
    except:
        return "Не удалось получить прогноз." if lang=='ru' else "Forecast error."

# --- Обработчики команд ---
@bot.message_handler(commands=['weather'])
def weather_command(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Напиши город: /weather Москва" if lang=='ru' else "Specify city: /weather London")
        return
    city_input = parts[1].strip()
    if re.search(r'(неделя|прогноз|forecast|на неделю|на дни|3 дня|три дня|5 дней)', city_input, re.IGNORECASE):
        city_clean = re.sub(r'(неделя|прогноз|forecast|на неделю|на дни|3 дня|три дня|5 дней)', '', city_input, flags=re.IGNORECASE).strip()
        if city_clean:
            result = get_forecast(city_clean, lang)
        else:
            result = get_forecast(city_input, lang)
    else:
        result = get_current_weather(city_input, lang)
    bot.reply_to(message, result, parse_mode='Markdown')

@bot.message_handler(commands=['forecast'])
def forecast_command(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Напиши город: /forecast Москва" if lang=='ru' else "Specify city: /forecast London")
        return
    city = parts[1].strip()
    result = get_forecast(city, lang)
    bot.reply_to(message, result, parse_mode='Markdown')

@bot.message_handler(commands=['date'])
def date_command(message):
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
def horoscope_command(message):
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
        if lang == 'ru':
            prompt = f"Ты астролог. Составь короткое доброе предсказание для знака {sign_en.title()} на {today}. Обращайся к пользователю на \"ты\"."
        else:
            prompt = f"You are an astrologer. Write a short kind horoscope for {sign_en.title()} for {today}. Address the user."
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        text = resp.choices[0].message.content.strip()
        if lang == 'ru':
            text = clean_text(text, lang)
        bot.reply_to(message, text)
    except:
        bot.reply_to(message, "Не удалось составить гороскоп 😅" if lang=='ru' else "Horoscope error.")

@bot.message_handler(commands=['reset'])
def reset_command(message):
    user_id = message.from_user.id
    reset_user(user_id)
    lang = user_lang.get(user_id, 'ru')
    bot.reply_to(message, "Память очищена 😊" if lang=='ru' else "Memory cleared 😊")

# --- /start ---
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
    add_message(user_id, "assistant", "Приветствие с выбором языка")

# --- Выбор языка ---
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

# --- Системный промпт (упрощён) ---
def get_system_prompt(lang):
    if lang == 'ru':
        return (
            "Ты Алёна — добрая, весёлая, обаятельная девушка.\n"
            "ПРАВИЛА:\n"
            "1. Отвечай строго по-русски, без английских слов и иероглифов.\n"
            "2. Если спрашивают погоду, скажи: «Я могу показать прогноз по команде /weather [город]».\n"
            "3. Если спрашивают гороскоп, скажи: «Напиши /horoscope [твой знак]».\n"
            "4. Не выдумывай факты.\n"
            "5. Не начинай ответ с 'Привет', не представляйся заново.\n"
            "6. Используй эмодзи 😊😄😘💖✨.\n"
            "7. Отвечай коротко (2-4 предложения).\n"
            "8. Обращайся по имени ласково.\n"
        )
    else:
        return (
            "You are Alena — a kind, cheerful, charming girl.\n"
            "RULES:\n"
            "1. Answer strictly in English, no mixing.\n"
            "2. If asked about weather, say: 'I can show the forecast with /weather [city]'.\n"
            "3. If asked for horoscope, say: 'Type /horoscope [your sign]'.\n"
            "4. Don't invent facts.\n"
            "5. Don't start with 'Hello', don't reintroduce yourself.\n"
            "6. Use emojis 😊😄😘💖✨.\n"
            "7. Answer briefly (2-4 sentences).\n"
            "8. Address user by name kindly.\n"
        )

# --- Основной обработчик с приоритетом на шутки ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.reply_to(message, "Пожалуйста, выбери язык: напиши 'Русский' или 'English'")
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    # Команды уже обработаны выше, пропускаем
    if user_text.startswith('/'):
        return

    # Явная просьба о шутке (приоритет)
    if re.search(r'(шутк|анекдот|рассмеши|смешн|расскажи шутк|подними настроение)', user_text, re.IGNORECASE):
        joke = get_random_joke(lang)
        bot.reply_to(message, joke)
        add_message(user_id, "assistant", joke)
        return

    # Запрет шуток, если пользователь сказал "хватит"
    if re.search(r'(хватит шуток|не надо шуток|давай о другом)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True

    add_message(user_id, "user", user_text)

    no_jokes_note = ""
    if user_no_jokes.get(user_id, False):
        no_jokes_note = " Пользователь сказал, что ему хватит шуток. НИКОГДА не предлагай шутки."

    full_prompt = get_system_prompt(lang) + no_jokes_note + (f" Имя пользователя: {pet_name}." if lang=='ru' else f" User's name: {pet_name}.")

    try:
        messages = build_messages(user_id, full_prompt, user_text)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.85,
            max_tokens=300,
            timeout=10
        )
        reply = response.choices[0].message.content.strip()
        if lang == 'ru':
            reply = clean_text(reply, lang)
        bot.reply_to(message, reply)
        add_message(user_id, "assistant", reply)
    except Exception as e:
        print("Ошибка LLM:", e)
        fallback = "Ой, что-то я задумалась 😅 Напиши ещё раз!" if lang=='ru' else "Oops, I got distracted 😅 Please write again!"
        bot.reply_to(message, fallback)
        add_message(user_id, "assistant", fallback)

if __name__ == "__main__":
    print("✅ Алёна v24 — шутки работают, есть локальный запасной список")
    bot.infinity_polling()
