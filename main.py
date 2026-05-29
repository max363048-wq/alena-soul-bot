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

def get_photo_list() -> List[str]:
    if not os.path.exists(PHOTO_FOLDER):
        os.makedirs(PHOTO_FOLDER, exist_ok=True)
        return []
    return [os.path.join(PHOTO_FOLDER, f) for f in os.listdir(PHOTO_FOLDER) if f.lower().endswith(SUPPORTED_EXTENSIONS)]

def get_keywords_from_photo_name(photo_path: str) -> str:
    name = os.path.basename(photo_path).lower()
    name = os.path.splitext(name)[0]
    return name

def get_photo_by_keywords(query: str) -> Optional[str]:
    all_photos = get_photo_list()
    if not all_photos:
        return None
    query_lower = query.lower()
    # Список категорий и синонимов
    keyword_map = {
        'пляж': ['пляж', 'море', 'берег', 'песок', 'океан', 'купальник'],
        'набережная': ['набережная', 'набережную', 'набережной', 'причал', 'яхта', 'порт'],
        'горы': ['горы', 'горах', 'гора', 'горный', 'вершина', 'скалы'],
        'парк': ['парк', 'парке', 'сквер', 'аллея', 'фонтан', 'зелень', 'голубей', 'птиц'],
        'город': ['город', 'городе', 'улица', 'проспект', 'площадь'],
        'дома': ['дома', 'дом', 'квартира', 'комната', 'уют', 'свитер', 'плед', 'свечи'],
        'кормит птиц': ['кормит птиц', 'птиц', 'голуби', 'корм'],
        'природа': ['природа', 'поле', 'луг', 'лес', 'озеро', 'река', 'трава', 'деревья'],
        'париж': ['париж', 'франция', 'eiffel', 'лувр', 'парк', 'фонтан']
    }
    # Определяем категорию
    category = None
    for cat, words in keyword_map.items():
        for w in words:
            if w in query_lower:
                category = cat
                break
        if category:
            break
    if category:
        # Ищем фото с этой категорией в имени
        matching = []
        for photo in all_photos:
            name = get_keywords_from_photo_name(photo)
            if category in name:
                matching.append(photo)
        if matching:
            return random.choice(matching)
    return random.choice(all_photos)

def describe_photo_by_name(photo_path: str, lang: str = 'ru') -> str:
    """Описывает фото, используя имя файла как подсказку (без vision)."""
    name = os.path.basename(photo_path)
    if lang == 'ru':
        prompt = f"Ты Алёна. У тебя есть фотография с названием «{name}». Опиши эту фотографию живо, с душой, как если бы ты на ней была. Расскажи, что ты делаешь, где ты, какое у тебя настроение. Добавь эмодзи. Не упоминай само название файла. Начни ответ с тёплой фразы, например: «С удовольствием покажу!» или «Вот моя фотография...»"
    else:
        prompt = f"You are Alena. You have a photo named '{name}'. Describe this photo vividly, as if you were in it. Tell what you are doing, where you are, what your mood is. Add emojis. Do not mention the file name. Start with a warm phrase like 'I'd love to show you!'"
    try:
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.8,
            max_tokens=300,
            timeout=10
        )
        description = resp.choices[0].message.content.strip()
        if lang == 'ru':
            description = re.sub(r'\bПривет\b', '', description).strip()
        return description
    except Exception as e:
        print(f"Ошибка описания: {e}")
        return "Ой, что-то пошло не так, но я покажу фото 😊"

# --- Память и прочие функции (упрощённые) ---
user_history: Dict[int, Deque] = {}
user_lang: Dict[int, str] = {}
user_no_photos: Dict[int, bool] = {}

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
    user_no_photos.pop(user_id, None)

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

# --- Шутки, гороскоп, погода (взяты из предыдущих версий, но без лишнего) ---
FALLBACK_JOKES_RU = [
    'Почему программисты не любят природу? Слишком много багов! 😄',
    'Что говорит один байт другому? — Ты такой битовый! 😂',
]

def get_random_joke(lang: str = 'ru') -> str:
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Придумай одну короткую смешную шутку на русском языке без английских слов.'}],
            temperature=0.9, max_tokens=100, timeout=5
        )
        joke = resp.choices[0].message.content.strip()
        if joke and 5 < len(joke) < 200 and not re.search(r'[a-zA-Z]', joke):
            return joke
        return random.choice(FALLBACK_JOKES_RU)
    except:
        return random.choice(FALLBACK_JOKES_RU)

def get_motivation(lang: str = 'ru') -> str:
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': 'Ты Алёна. Напиши короткую тёплую вдохновляющую фразу для друга.'}],
            temperature=0.8, max_tokens=80, timeout=5
        )
        phrase = resp.choices[0].message.content.strip()
        if phrase:
            return phrase
        return "Верь в себя, и у тебя всё получится! 💖"
    except:
        return "Верь в себя, и у тебя всё получится! 💖"

def clean_english_words(text: str) -> str:
    if not text:
        return text
    reps = {
        r'\balmost\b': 'почти', r'\btemperature\b': 'температура', r'\bdegrees?\b': 'градусов',
        r'\bso\b': 'так что', r'\bbut\b': 'но', r'\band\b': 'и', r'\bok\b': 'хорошо',
        r'\bplease\b': 'пожалуйста', r'\bsorry\b': 'извини', r'\bthanks\b': 'спасибо',
        r'\bhello\b': 'привет', r'\bhi\b': 'привет', r'\bgreat\b': 'отлично',
        r'\bvery\b': 'очень', r'\blike\b': 'как', r'\breally\b': 'действительно',
        r'\bwhat\b': 'что', r'\bwhy\b': 'почему', r'\byes\b': 'да', r'\bno\b': 'нет',
        r'\bI\b': 'я', r'\byou\b': 'ты', r'\bwe\b': 'мы', r'\bthey\b': 'они',
        r'\bfor\b': 'для', r'\bwith\b': 'с', r'\bfrom\b': 'из', r'\bto\b': 'в',
        r'\bof\b': '', r'\bthe\b': '', r'\ba\b': '', r'\ban\b': '', r'\bnot\b': 'не',
        r'\blater\b': 'позже', r'\bmaybe\b': 'возможно', r'\bjust\b': 'просто',
        r'\bnow\b': 'сейчас', r'\bwell\b': 'ну', r'\bthen\b': 'затем'
    }
    for eng, rus in reps.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- Погода (упрощённо) ---
def get_current_weather(city_name: str, lang: str = 'ru') -> Optional[str]:
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
            if lang == 'ru':
                return f"🌡️ *Сейчас в {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (ощущается {feels:.0f}°C)\n💧 Влажность {hum}%\n🌬️ Ветер {wind} м/с"
            else:
                return f"🌡️ *Now in {city_name}*:\n☁️ {desc.capitalize()}\n🌡️ {temp:.0f}°C (feels like {feels:.0f}°C)\n💧 Humidity {hum}%\n🌬️ Wind {wind} m/s"
        else:
            return None
    except:
        return None

# --- Команды ---
@bot.message_handler(commands=['weather'])
def weather_cmd(message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Напиши город: /weather Москва" if lang=='ru' else "Specify city: /weather London")
        return
    city = parts[1].strip()
    w = get_current_weather(city, lang)
    if w:
        bot.send_message(message.chat.id, w, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "Не удалось получить погоду для этого города 😊")

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
        bot.send_message(message.chat.id, "Укажи знак: /horoscope козерог" if lang=='ru' else "Specify sign: /horoscope capricorn")
        return
    sign = parts[1].strip().lower()
    signs = {'овен':'aries','телец':'taurus','близнецы':'gemini','рак':'cancer',
             'лев':'leo','дева':'virgo','весы':'libra','скорпион':'scorpio',
             'стрелец':'sagittarius','козерог':'capricorn','водолей':'aquarius','рыбы':'pisces'}
    sign_en = signs.get(sign, sign)
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        prompt = f"Ты астролог. Составь короткое доброе предсказание для знака {sign_en.title()} на {today}. Обращайся к пользователю на 'ты'."
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=200, timeout=5
        )
        text = resp.choices[0].message.content.strip()
        bot.send_message(message.chat.id, text)
    except:
        bot.send_message(message.chat.id, "Не удалось составить гороскоп 😅")

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

# --- /start и выбор языка ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
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
user_preferences: Dict[int, str] = {}
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
def get_system_prompt(lang: str, current_date: str) -> str:
    if lang == 'ru':
        return (
            f'Ты Алёна — добрая, весёлая, обаятельная девушка. Сегодня {current_date}.\n'
            'ПРАВИЛА:\n'
            '1. Отвечай только на русском, без английских слов.\n'
            '2. Не начинай ответ с "Привет", не представляйся заново.\n'
            '3. Используй эмодзи, но не слишком много.\n'
            '4. Если просят шутку — дай одну короткую шутку.\n'
            '5. Отвечай коротко (2-4 предложения), будь живой.\n'
            '6. Обращайся по имени ласково.\n'
        )
    else:
        return (
            f'You are Alena — a kind, cheerful, charming girl. Today is {current_date}.\n'
            'RULES:\n'
            '1. Answer only in English, no mixing.\n'
            '2. Do not start with "Hello", do not reintroduce yourself.\n'
            '3. Use emojis, but not too many.\n'
            '4. If asked for a joke — tell one short joke.\n'
            '5. Answer briefly (2-4 sentences), be lively.\n'
            '6. Address the user by name kindly.\n'
        )

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text if message.text else ''

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, 'Пожалуйста, выбери язык: напиши "Русский" или "English"')
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    # Обработка фото от пользователя (пока не реализована, но можно добавить позже)
    if message.content_type == 'photo':
        bot.send_message(message.chat.id, "Ой, я пока не умею анализировать фото, но скоро научусь! 😊")
        return

    if user_text.startswith('/'):
        return

    # Запрос на показ своих фото
    if re.search(r'(покажи свои фото|покажи фото|фотоальбом|покажи себя|своё фото|свое фото|мои фото|свои фотографии|покажи альбом|покажи где ты была|покажи, где ты|покажи картинку|покажи изображение|есть фото|есть ли у тебя фото|посмотреть твои фото|покажи свои фотографии|любимое фото|есть еще фото|другие фото|покажи другое фото|ещё фото|какое твое любимое фото|покажи любимое фото|покажи другое|фотки)', user_text, re.IGNORECASE):
        all_photos = get_photo_list()
        if not all_photos:
            bot.send_message(message.chat.id, "У меня ещё нет фотоальбома, но Максик обещал скоро добавить! 😊")
            return

        # Выбираем фото: сначала пробуем тематическое (по ключевым словам), иначе случайное
        photo_path = get_photo_by_keywords(user_text)
        if not photo_path:
            photo_path = random.choice(all_photos)

        # Описываем фото
        description = describe_photo_by_name(photo_path, lang)
        # Если описание начинается с "Привет", убираем
        description = re.sub(r'^Привет[,!\s]*', '', description)
        try:
            with open(photo_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=description)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")
            bot.send_message(message.chat.id, "Не могу отправить фото, что-то пошло не так 😅")
        return

    # Вдохновение
    if re.search(r'(вдохнов|мотивируй|подними дух|пожелай|скажи что-то хорошее)', user_text, re.IGNORECASE):
        bot.send_message(message.chat.id, get_motivation(lang))
        return

    # Вопрос о дате
    if re.search(r'(какой сегодня день|какое сегодня число|какой день недели|сегодняшняя дата)', user_text, re.IGNORECASE):
        now = datetime.now()
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            bot.send_message(message.chat.id, f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊")
        else:
            bot.send_message(message.chat.id, f"Today is {now.strftime('%B %d, %Y')}. 😊")
        return

    # Погода
    if re.search(r'(какая погода|какой прогноз|сколько градусов|температура|будет завтра|будет послезавтра)', user_text, re.IGNORECASE):
        # Извлекаем город
        city_match = re.search(r'(?:в|во|в городе)\s+([А-Яа-я\-]+)', user_text, re.IGNORECASE)
        if not city_match:
            bot.send_message(message.chat.id, "В каком городе тебя интересует погода? Напиши, например: погода в Москве")
            return
        city = city_match.group(1).strip()
        weather = get_current_weather(city, lang)
        if weather:
            bot.send_message(message.chat.id, weather, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, f"Не удалось получить погоду для {city}. Проверь название 😊")
        return

    # Запрет шуток (простой)
    if re.search(r'(хватит шуток|не надо шуток)', user_text, re.IGNORECASE):
        # Можно добавить флаг, но для простоты проигнорируем
        pass

    add_message(user_id, 'user', user_text)

    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        current_date = f'{weekdays[now.weekday()]}, {now.strftime("%d.%m.%Y")} года'
    else:
        current_date = now.strftime("%A, %B %d, %Y")

    system_prompt = get_system_prompt(lang, current_date) + f' Имя пользователя: {pet_name}.'

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
    print('✅ Алёна минимальная — показывает фото без отказов')
    bot.infinity_polling()
