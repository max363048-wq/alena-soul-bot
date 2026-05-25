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
USER_HISTORY_MAXLEN = 10   # Уменьшили для стабильности

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=USER_HISTORY_MAXLEN)
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
    user_history[user_id] = deque(maxlen=USER_HISTORY_MAXLEN)
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

# --- Очистка текста ---
def remove_cjk(text: str) -> str:
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u20000-\u2a6df\u3000-\u303f]', re.UNICODE)
    return cjk_pattern.sub('', text)

def clean_text(text: str, lang: str) -> str:
    if lang != 'ru':
        return text
    text = remove_cjk(text)
    # Глобальные замены
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
    # Удаляем одиночные запятые, точки, вопросительные знаки
    text = re.sub(r'^[,.!?;:]+', '', text)
    return text

def validate_response(text: str, lang: str) -> bool:
    """Проверяет, является ли ответ осмысленным (не мусором)"""
    if not text or len(text) < 3:
        return False
    # Если текст состоит только из символов пунктуации, цифр или эмодзи
    if re.fullmatch(r'[\s,.;:!?()\[\]{}\d😊💖✨🎉😘]+', text):
        return False
    # Если в тексте нет ни одной русской или английской буквы
    if lang == 'ru' and not re.search(r'[а-яА-Я]', text):
        return False
    if lang == 'en' and not re.search(r'[a-zA-Z]', text):
        return False
    return True

# --- Погода и прогноз ---
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
            temperature=0.6,
            max_tokens=150
        )
        text = resp.choices[0].message.content.strip()
        if lang == 'ru':
            text = clean_text(text, lang)
        if not validate_response(text, lang):
            text = "Звёзды говорят, что сегодня тебя ждёт удача и хорошее настроение 😊" if lang=='ru' else "The stars say you'll have luck and good mood today 😊"
        bot.reply_to(message, text)
    except:
        bot.reply_to(message, "Не удалось составить гороскоп 😅" if lang=='ru' else "Horoscope error.")

@bot.message_handler(commands=['reset'])
def reset_command(message):
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
    add_message(user_id, "assistant", "Приветствие с выбором языка")

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
    # Сгенерируем шутку для приветствия
    try:
        joke_response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Придумай одну короткую смешную шутку на русском языке без английских слов. Только текст шутки."}],
            temperature=0.7,
            max_tokens=100
        )
        joke = joke_response.choices[0].message.content.strip()
        if not validate_response(joke, 'ru'):
            joke = "Почему программисты не любят природу? Слишком много багов! 😄"
    except:
        joke = "Почему программисты не любят природу? Слишком много багов! 😄"
    joke = clean_text(joke, 'ru')
    reply = (f"Отлично, {pet}! Будем общаться по-русски 💖\n\n😊 Шутка для настроения: {joke}\n\nА вот что я умею: могу поболтать по душам, рассмешить шуткой, поддержать советом, вдохновить и даже составить для тебя гороскоп ✨ Просто спроси — и я рядом.\n\nРасскажи, как твои дела? 💕")
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

# --- Системный промпт (общий для всех) ---
def get_system_prompt(lang):
    if lang == 'ru':
        return (
            "Ты Алёна — добрая, весёлая, обаятельная девушка. Отвечай кратко (2-4 предложения).\n"
            "Используй эмодзи 😊😄😘💖✨.\n"
            "Никогда не используй английские слова, только русский.\n"
            "Не начинай ответ с 'Привет', не представляйся заново.\n"
            "Если спрашивают погоду, ответь: 'Я могу показать прогноз по команде /weather [город]'.\n"
            "Если спрашивают гороскоп, ответь: 'Напиши /horoscope [твой знак]'.\n"
            "Если просят шутку, расскажи одну короткую смешную шутку.\n"
            "Будь живой и естественной. Всегда обращайся по имени ласково.\n"
        )
    else:
        return (
            "You are Alena — a kind, cheerful, charming girl. Answer briefly (2-4 sentences).\n"
            "Use emojis 😊😄😘💖✨.\n"
            "Never mix languages. Answer only in English.\n"
            "Don't start with 'Hello', don't reintroduce yourself.\n"
            "If asked about weather, say: 'I can show forecast with /weather [city]'.\n"
            "If asked for horoscope, say: 'Type /horoscope [your sign]'.\n"
            "If asked for a joke, tell one short funny joke.\n"
            "Be lively and natural. Always address the user by name kindly.\n"
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

    # Добавляем сообщение пользователя в историю
    add_message(user_id, "user", user_text)

    # Формируем системный промпт
    full_prompt = get_system_prompt(lang) + f" Имя пользователя: {pet_name}."

    max_retries = 2
    for attempt in range(max_retries):
        try:
            messages = build_messages(user_id, full_prompt, user_text)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.6,      # ниже для стабильности
                max_tokens=150,       # короче
                timeout=10
            )
            reply = response.choices[0].message.content.strip()
            if lang == 'ru':
                reply = clean_text(reply, lang)
            if validate_response(reply, lang):
                # Успешный ответ
                bot.reply_to(message, reply)
                add_message(user_id, "assistant", reply)
                return
            else:
                # Невалидный ответ — пробуем ещё раз, если не последняя попытка
                if attempt == max_retries - 1:
                    # Используем запасной ответ
                    fallback = "Извини, я немного зависла 😅 Давай попробуем ещё раз?" if lang=='ru' else "Sorry, I glitched 😅 Let's try again?"
                    bot.reply_to(message, fallback)
                    add_message(user_id, "assistant", fallback)
                else:
                    continue
        except Exception as e:
            print("Ошибка LLM:", e)
            if attempt == max_retries - 1:
                fallback = "Ой, что-то пошло не так 😅 Напиши ещё раз, пожалуйста!" if lang=='ru' else "Oops, something went wrong 😅 Please write again!"
                bot.reply_to(message, fallback)
                add_message(user_id, "assistant", fallback)

if __name__ == "__main__":
    print("✅ Алёна v26 — стабильная, короткая память, низкая температура, валидация ответов")
    bot.infinity_polling()
