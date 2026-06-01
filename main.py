import os
import telebot
import re
import requests
import random
import time
import json
import threading
from flask import Flask
from openai import OpenAI
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, Deque, Optional, List, Any

import stories
import photos

BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
GIST_ID = os.getenv('GIST_ID')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

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

GIST_FILENAME = 'user_langs.json'
LAST_PHOTO_FILENAME = 'user_last_photo.json'
HISTORY_FILENAME = 'user_history.json'
ZODIAC_FILENAME = 'user_zodiac.json'
TIMEZONE_FILENAME = 'user_timezone.json'
GIST_API_URL = f'https://api.github.com/gists/{GIST_ID}'
HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

TEXT_NUMBERS = {
    'один': 1, 'одну': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5,
    'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10
}

# ---------- ЗАГРУЗКА/СОХРАНЕНИЕ GIST ----------
def load_user_langs():
    global user_lang
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        resp = requests.get(GIST_API_URL, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if GIST_FILENAME in files:
                content = files[GIST_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_lang = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки языков из Gist: {e}')

def save_user_lang(user_id: int, lang: str):
    user_lang[user_id] = lang
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        payload = {
            'files': {
                GIST_FILENAME: {
                    'content': json.dumps(user_lang, ensure_ascii=False, indent=2)
                }
            }
        }
        requests.patch(GIST_API_URL, headers=HEADERS, json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения языков в Gist: {e}')

def load_user_last_photo():
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        resp = requests.get(GIST_API_URL, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if LAST_PHOTO_FILENAME in files:
                content = files[LAST_PHOTO_FILENAME].get('content', '{}')
                data = json.loads(content)
                photos.user_last_sent_photo = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки последних фото из Gist: {e}')

def save_user_last_photo(user_id: int, photo_path: Optional[str] = None):
    if photo_path:
        photos.user_last_sent_photo[user_id] = photo_path
    else:
        photos.user_last_sent_photo.pop(user_id, None)
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        payload = {
            'files': {
                LAST_PHOTO_FILENAME: {
                    'content': json.dumps(photos.user_last_sent_photo, ensure_ascii=False)
                }
            }
        }
        requests.patch(GIST_API_URL, headers=HEADERS, json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения последнего фото в Gist: {e}')

def load_user_history():
    global user_history
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        resp = requests.get(GIST_API_URL, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if HISTORY_FILENAME in files:
                content = files[HISTORY_FILENAME].get('content', '{}')
                data = json.loads(content)
                for k, v in data.items():
                    user_history[int(k)] = deque(v, maxlen=12)
    except Exception as e:
        print(f'Ошибка загрузки истории из Gist: {e}')

def save_user_history(user_id: int):
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        data_to_save = {str(uid): list(hist) for uid, hist in user_history.items()}
        payload = {
            'files': {
                HISTORY_FILENAME: {
                    'content': json.dumps(data_to_save, ensure_ascii=False)
                }
            }
        }
        requests.patch(GIST_API_URL, headers=HEADERS, json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения истории в Gist: {e}')

def load_user_zodiac():
    global user_zodiac
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        resp = requests.get(GIST_API_URL, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if ZODIAC_FILENAME in files:
                content = files[ZODIAC_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_zodiac = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки знаков зодиака из Gist: {e}')

def save_user_zodiac():
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        payload = {
            'files': {
                ZODIAC_FILENAME: {
                    'content': json.dumps(user_zodiac, ensure_ascii=False)
                }
            }
        }
        requests.patch(GIST_API_URL, headers=HEADERS, json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения знаков зодиака в Gist: {e}')

def load_user_timezone():
    global user_timezone
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        resp = requests.get(GIST_API_URL, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if TIMEZONE_FILENAME in files:
                content = files[TIMEZONE_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_timezone = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки часовых поясов из Gist: {e}')

def save_user_timezone():
    if not GIST_ID or not GITHUB_TOKEN:
        return
    try:
        payload = {
            'files': {
                TIMEZONE_FILENAME: {
                    'content': json.dumps(user_timezone, ensure_ascii=False)
                }
            }
        }
        requests.patch(GIST_API_URL, headers=HEADERS, json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения часовых поясов в Gist: {e}')

load_user_langs()
load_user_last_photo()
load_user_history()
load_user_zodiac()
load_user_timezone()

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
    save_user_last_photo(user_id)
    photos.user_no_photos.pop(user_id, None)
    photos.user_thematic_history.pop(user_id, None)
    photos.user_last_category.pop(user_id, None)
    photos.user_last_user_image_desc.pop(user_id, None)
    user_zodiac.pop(user_id, None)
    save_user_zodiac()
    user_timezone.pop(user_id, None)
    save_user_timezone()
    user_last_photo_request.pop(user_id, None)

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
        r'\bof\b': '', r'\bthe\b': '', r'\ba\b': '', r'\ban\b': '', r'\bnot\b': 'не',
        r'\blater\b': 'позже', r'\bmaybe\b': 'возможно', r'\bjust\b': 'просто',
        r'\bnow\b': 'сейчас', r'\bwell\b': 'ну', r'\bthen\b': 'затем', r'\beven\b': 'даже',
        r'\bsome\b': 'некоторые', r'\bany\b': 'любые', r'\bhere\b': 'здесь', r'\bthere\b': 'там',
        r'\bmy\b': 'мой', r'\byour\b': 'твой', r'\bhis\b': 'его', r'\bher\b': 'её',
        r'\babsolutely\b': 'конечно', r'\blounge\b': 'шезлонг', r'\bromantic\b': 'романтично',
        r'\binteres\w*\b': 'интересн',
        r'\brefreshed\b': 'посвежевшей',
        r'\bfeeling\b': 'чувствуя',
        r'\bdiscuss\b': 'обсудить',
        r'\bdebug\b': 'отладка',
        r'\bcute\b': 'милые',
        r'\btranquil\b': 'спокойного',
        r'\bserious\b': 'серьёзном',
        r'\bresilient\b': 'стойким',
        r'\bearlier\b': 'раньше',
        r'\btoday\b': 'сегодня',
        r'\bfinally\b': 'наконец',
        r'\bbecause\b': 'потому что',
        r'\bcapricorn\b': 'козерог',
        r'\bmoi\b': 'мной',
        r'\bagree\b': 'согласна',
        r'\bspectacle\b': 'зрелище',
        r'\bpatterns\b': 'узоры',
    }
    for eng, rus in reps.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def remove_non_russian(text: str) -> str:
    cleaned = re.sub(r'[^А-Яа-яЁё\s\d\.,!?:;…\-–—""\'«»()/#@\*\+—\u2700-\u27BF\u1F600-\u1F64F\u1F300-\u1F5FF\u1F680-\u1F6FF\u1F1E0-\u1F1FF\u2600-\u26FF\u2700-\u27BF]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

SAFE_EMOJIS = ['😊', '💖', '✨', '😄', '😘', '🥰', '💕', '🤗']

def filter_emojis(text: str) -> str:
    allowed = set(SAFE_EMOJIS)
    result = []
    for ch in text:
        if '\U0001F000' <= ch <= '\U0001FFFF' or '\u2600' <= ch <= '\u27BF':
            if ch in allowed:
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)

def distribute_emojis(text: str) -> str:
    text = filter_emojis(text)
    sentences = re.split(r'(?<=[.!?…]) +', text)
    new_sentences = []
    used_safe_emojis = []
    total_emojis = 0
    for s in sentences:
        emojis_in_s = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]', s)
        if not emojis_in_s:
            available = [e for e in SAFE_EMOJIS if e not in used_safe_emojis]
            if not available:
                available = SAFE_EMOJIS
                used_safe_emojis = []
            chosen = random.choice(available)
            s += ' ' + chosen
            used_safe_emojis.append(chosen)
            total_emojis += 1
        else:
            total_emojis += len(emojis_in_s)
        new_sentences.append(s)
    result = ' '.join(new_sentences)
    if total_emojis < 2:
        available = [e for e in SAFE_EMOJIS if e not in used_safe_emojis]
        if not available:
            available = SAFE_EMOJIS
        for _ in range(2 - total_emojis):
            chosen = random.choice(available)
            result += ' ' + chosen
            used_safe_emojis.append(chosen)
    return result

def extract_city(text: str, user_id: Optional[int] = None) -> Optional[str]:
    match = re.search(r'\b(?:в|во|в городе)\s+([А-Яа-я\-]+(?:[-\s]?[А-Яа-я]+)?)', text, re.IGNORECASE)
    if match:
        city = match.group(1).strip().lower()
        city = re.sub(r'\b(ночь|день|вечер|утро|сегодня|завтра|послезавтра|через|будет)\b', '', city).strip()
        if not city:
            return None
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
    if re.search(r'(у нас|в нашем городе|в моём городе|в своем городе|в этом городе|в нашем|здесь)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    if re.search(r'(завтра|послезавтра|будет|через \d+|на неделю|на (два|три|четыре|пять) дня|в ближайшие (два|три|четыре|пять) дня)', text, re.IGNORECASE) and re.search(r'(погод|температур|дождь|солнце|ветер|градусов)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    if re.search(r'(сколько градусов|температура|погода|градусов|холодно|тепло)', text, re.IGNORECASE):
        if user_id and user_id in user_last_city:
            return user_last_city[user_id]
    return None

def is_weather_query(text: str) -> bool:
    if re.search(r'(какая погода|какая сегодня погода|какой прогноз|что с погодой|сколько градусов|температура какая|будет завтра|будет послезавтра|завтра погода|послезавтра погода|сколько сейчас градусов|какая сейчас погода|через (три|четыре|пять|\d+) (дня|дней|день)|на неделю|на (два|три|четыре|пять) дня|в ближайшие (два|три|четыре|пять) дня|здесь в ближайшие)', text, re.IGNORECASE):
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
                'wind': data['wind']['speed'],
                'timezone': data.get('timezone', 0)
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
        timezone_offset = data.get('city', {}).get('timezone', 0)
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            if dt.strftime('%Y-%m-%d') == target_date:
                temps.append(item['main']['temp'])
                descs.append(item['weather'][0]['description'])
        if temps:
            return {'desc': max(set(descs), key=descs.count), 'temp': sum(temps)/len(temps), 'timezone': timezone_offset}
        return None
    except:
        return None

def format_local_time(timezone_offset: int, target_date: Optional[datetime] = None) -> str:
    if target_date:
        utc_now = target_date
    else:
        utc_now = datetime.now(timezone.utc)
    local_now = utc_now + timedelta(seconds=timezone_offset)
    hour = local_now.hour
    if 5 <= hour < 12:
        time_of_day = 'утро'
    elif 12 <= hour < 17:
        time_of_day = 'день'
    elif 17 <= hour < 22:
        time_of_day = 'вечер'
    else:
        time_of_day = 'ночь'
    weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
    wd = weekdays[local_now.weekday()]
    return f'{wd}, {local_now.strftime("%d.%m.%Y")} года, {local_now.strftime("%H:%M")} ({time_of_day})'

def generate_natural_weather_response(city: str, weather_data: Dict, lang: str = 'ru', is_forecast: bool = False, day_name: str = '') -> str:
    if not weather_data:
        return distribute_emojis(f"Не удалось получить данные о погоде для {city}. Проверь название города 😊")
    
    timezone_offset = weather_data.get('timezone', 0)
    # Для прогноза на конкретный день нам нужна дата, но здесь мы её не знаем, поэтому используем текущую
    local_time_str = format_local_time(timezone_offset)
    
    if is_forecast:
        temp = weather_data['temp']
        desc = weather_data['desc']
        fallback = f"На {day_name} в {city} ожидается {desc}, около {temp:.0f} градусов. Уютного дня! 😊"
        prompt = f"Ты Алёна. Пользователь спросил погоду на {day_name} в {city}. Реальные данные: {desc}, температура {temp:.0f}°C. Сейчас в городе {local_time_str}. Ответь тепло, коротко (2-3 предложения). НИ В КОЕМ СЛУЧАЕ не упоминай осень, сентябрь, зиму или холодные сезоны, если это не зима. Используй только точные цифры: {temp:.0f}°C и описание {desc}. Без английских слов. Не начинай ответ с приветствия."
    else:
        desc = weather_data['desc']
        temp = weather_data['temp']
        feels = weather_data['feels']
        hum = weather_data['hum']
        wind = weather_data['wind']
        fallback = f"Сейчас в {city} {desc}, температура около {temp:.0f} градусов (ощущается как {feels:.0f}). Влажность {hum}%, ветер {wind} м/с. Хорошего дня! 😊"
        prompt = f"Ты Алёна. Пользователь спросил о погоде в {city}. Реальные данные: сейчас {desc}, температура {temp:.0f}°C, ощущается как {feels:.0f}°C, влажность {hum}%, ветер {wind} м/с. Сейчас в городе {local_time_str}. Ответь тепло, коротко (2-3 предложения). НИ В КОЕМ СЛУЧАЕ не упоминай осень, сентябрь, зиму или холодные сезоны, если на улице не зима. Используй только точные цифры: {temp:.0f}°C, {desc}. Не пиши 'мне нужно проверить' или 'я не знаю' – ты уже знаешь данные. Без английских слов. Не начинай ответ с приветствия."
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=150, timeout=5
        )
        reply = resp.choices[0].message.content.strip()
        reply = clean_english_words(reply)
        reply = remove_non_russian(reply)
        reply = distribute_emojis(reply)
        temp_int = int(round(temp))
        if str(temp_int) not in reply and str(temp_int+1) not in reply and str(temp_int-1) not in reply:
            return distribute_emojis(fallback)
        return reply
    except:
        return distribute_emojis(fallback)

def handle_weather_query(message: telebot.types.Message, user_text: str, lang: str, user_id: int) -> bool:
    if not is_weather_query(user_text):
        return False
    day_delta = 0
    day_name = ''
    is_multi_day = False

    if re.search(r'на неделю', user_text, re.IGNORECASE):
        is_multi_day = True
        day_deltas = list(range(1, 6))
    match_text = re.search(r'на (два|две|три|четыре|пять) дня|в ближайшие (два|три|четыре|пять) дня', user_text, re.IGNORECASE)
    if match_text:
        word = match_text.group(1).lower() if match_text.group(1) else match_text.group(2).lower()
        if not word:
            word = match_text.group(2).lower()
        num_days = TEXT_NUMBERS.get(word, 0)
        is_multi_day = True
        day_deltas = list(range(0, num_days))  # День 0 — сегодня, 1 — завтра и т.д.
    else:
        match_text = re.search(r'через (один|одну|два|две|три|четыре|пять|шесть|семь) (дня|дней|день)', user_text, re.IGNORECASE)
        if match_text:
            word = match_text.group(1).lower()
            day_delta = TEXT_NUMBERS.get(word, 0)
            day_name = f'через {day_delta} {"день" if day_delta == 1 else "дня" if 1 < day_delta < 5 else "дней"}'
        else:
            match_days = re.search(r'через (\d+) (дня|дней|день)', user_text, re.IGNORECASE)
            if match_days:
                day_delta = int(match_days.group(1))
                day_name = f'через {day_delta} {"день" if day_delta == 1 else "дня" if 1 < day_delta < 5 else "дней"}'
            elif re.search(r'послезавтра', user_text, re.IGNORECASE):
                day_delta, day_name = 2, 'послезавтра'
            elif re.search(r'завтра', user_text, re.IGNORECASE):
                day_delta, day_name = 1, 'завтра'
            else:
                day_delta, day_name = 0, 'сегодня'

    city = extract_city(user_text, user_id)
    if not city:
        bot.send_message(message.chat.id, distribute_emojis("В каком городе тебя интересует погода? Напиши название, например: Санкт-Петербург 😊"))
        add_message(user_id, 'user', user_text)
        save_user_history(user_id)
        return True
    user_last_city[user_id] = city
    add_message(user_id, 'user', user_text)

    if is_multi_day:
        forecast_replies = []
        for d in day_deltas:
            if d == 0:
                # Текущая погода для дня 0
                weather = get_current_weather(city, lang)
                if weather:
                    timezone_offset = weather.get('timezone', 0)
                    user_timezone[user_id] = timezone_offset
                    save_user_timezone()
                    local_time_str = format_local_time(timezone_offset)
                    forecast_replies.append(f"• Сегодня: {weather['desc']}, около {weather['temp']:.0f}°C ({local_time_str})")
                else:
                    forecast_replies.append(f"• Сегодня: данные недоступны")
            else:
                fc = get_forecast_for_day(city, d, lang)
                if fc:
                    timezone_offset = fc.get('timezone', 0)
                    user_timezone[user_id] = timezone_offset
                    save_user_timezone()
                    # Вычисляем локальное время на target_date
                    target_date = datetime.now() + timedelta(days=d)
                    local_time_str = format_local_time(timezone_offset, target_date)
                    forecast_replies.append(f"• День {d}: {fc['desc']}, около {fc['temp']:.0f}°C ({local_time_str})")
                else:
                    forecast_replies.append(f"• День {d}: данные недоступны")
        if forecast_replies:
            reply = f"Прогноз в {city} на ближайшие дни: 😊\n" + "\n".join(forecast_replies)
            reply += "\nХорошей погоды! 💖"
            bot.send_message(message.chat.id, distribute_emojis(reply))
        else:
            bot.send_message(message.chat.id, distribute_emojis(f"Не удалось получить прогноз для {city}. Попробуй позже 😊"))
        add_message(user_id, 'assistant', reply)
        save_user_history(user_id)
        return True

    if day_delta == 0:
        weather = get_current_weather(city, lang)
        if weather:
            if 'timezone' in weather:
                user_timezone[user_id] = weather['timezone']
                save_user_timezone()
            reply = generate_natural_weather_response(city, weather, lang, is_forecast=False)
        else:
            reply = distribute_emojis(f"Не удалось получить текущую погоду для {city}. Проверь название города 😊")
    else:
        forecast = get_forecast_for_day(city, day_delta, lang)
        if forecast:
            if 'timezone' in forecast:
                user_timezone[user_id] = forecast['timezone']
                save_user_timezone()
            reply = generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name)
        else:
            reply = distribute_emojis(f"Не удалось получить прогноз на {day_name} для {city}. Попробуй позже 😊")
    bot.send_message(message.chat.id, reply)
    add_message(user_id, 'assistant', reply)
    save_user_history(user_id)
    return True

@bot.message_handler(commands=['weather'])
def weather_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, distribute_emojis("Напиши город: /weather Москва"))
        return
    city = parts[1].strip()
    weather = get_current_weather(city, lang)
    if weather:
        if 'timezone' in weather:
            user_timezone[user_id] = weather['timezone']
            save_user_timezone()
        reply = generate_natural_weather_response(city, weather, lang, is_forecast=False)
    else:
        reply = distribute_emojis(f"Не удалось получить погоду для {city}.")
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=['forecast'])
def forecast_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, distribute_emojis("Напиши город и день: /forecast Москва завтра"))
        return
    args = parts[1].strip().split()
    if len(args) < 2:
        bot.send_message(message.chat.id, distribute_emojis("Укажи город и день (завтра/послезавтра). Пример: /forecast Москва завтра"))
        return
    city = args[0]
    day_word = args[1].lower()
    if 'завтра' in day_word:
        day_delta, day_name = 1, 'завтра'
    elif 'послезавтра' in day_word:
        day_delta, day_name = 2, 'послезавтра'
    else:
        bot.send_message(message.chat.id, distribute_emojis("Укажи день: завтра или послезавтра"))
        return
    forecast = get_forecast_for_day(city, day_delta, lang)
    if forecast:
        if 'timezone' in forecast:
            user_timezone[user_id] = forecast['timezone']
            save_user_timezone()
        reply = generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name)
    else:
        reply = distribute_emojis(f"Не удалось получить прогноз на {day_name} для {city}.")
    bot.send_message(message.chat.id, reply)

@bot.message_handler(commands=['date'])
def date_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    now = datetime.now()
    if lang == 'ru':
        weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
        wd = weekdays[now.weekday()]
        bot.send_message(message.chat.id, distribute_emojis(f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊"))
    else:
        bot.send_message(message.chat.id, distribute_emojis(f"Today is {now.strftime('%B %d, %Y')}. 😊"))

@bot.message_handler(commands=['horoscope'])
def horoscope_cmd(message: telebot.types.Message, user_sign: Optional[str] = None) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 and not user_sign:
        bot.send_message(message.chat.id, distribute_emojis("Укажи знак или дату рождения. Примеры:\n/horoscope козерог\n/horoscope 15.06\n/horoscope 15 июня"))
        return
    arg = user_sign if user_sign else parts[1].strip().lower()
    zodiac_list = ['овен','телец','близнецы','рак','лев','дева','весы','скорпион','стрелец','козерог','водолей','рыбы']
    if arg in zodiac_list:
        sign = arg
        user_zodiac[user_id] = sign
        save_user_zodiac()
    else:
        day, month = parse_date_string(arg)
        if day and month:
            sign = zodiac_sign(day, month)
            user_zodiac[user_id] = sign
            save_user_zodiac()
        else:
            bot.send_message(message.chat.id, distribute_emojis("Не поняла знак или дату. Напиши, например: /horoscope козерог или /horoscope 15 июня"))
            return
    today = datetime.now().strftime('%Y-%m-%d')
    local_time_note = ''
    if user_id in user_timezone:
        local_time_str = format_local_time(user_timezone[user_id])
        local_time_note = f' Сейчас у пользователя {local_time_str}.'
    try:
        prompt = f"Ты астролог. Составь короткое доброе предсказание для знака {sign.capitalize()} на {today}.{local_time_note} Обращайся к пользователю на 'ты'. Пиши на русском, без английских слов. НЕ начинай ответ с 'Здравствуй' или 'Привет'."
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=300, timeout=5
        )
        text = resp.choices[0].message.content.strip()
        text = clean_english_words(text)
        text = remove_non_russian(text)
        text = distribute_emojis(text)
        bot.send_message(message.chat.id, text)
        add_message(user_id, 'user', f'/horoscope {sign}' if not parts else message.text)
        add_message(user_id, 'assistant', text)
        save_user_history(user_id)
    except:
        bot.send_message(message.chat.id, distribute_emojis("Не удалось составить гороскоп 😅 Попробуй позже."))

@bot.message_handler(commands=['quote'])
def quote_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    quote = get_motivation(lang)
    bot.send_message(message.chat.id, distribute_emojis(quote))

@bot.message_handler(commands=['reset'])
def reset_cmd(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    reset_user(user_id)
    bot.send_message(message.chat.id, distribute_emojis("Память очищена 😊"))

# ---------- ОСНОВНЫЕ ОБРАБОТЧИКИ ----------
@bot.message_handler(commands=['start'])
def send_welcome(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    reset_user(user_id)
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
    save_user_history(user_id)

@bot.message_handler(func=lambda message: message.text and re.match(r'^(русский|russian|english|английский)[!.\s]*$', message.text.lower()))
def set_language(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    text = message.text.lower().strip()
    if 'русский' in text or 'russian' in text:
        user_lang[user_id] = 'ru'
    else:
        user_lang[user_id] = 'en'
    save_user_lang(user_id, user_lang[user_id])
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
    save_user_history(user_id)

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
            bot.send_message(message.chat.id, distribute_emojis(reply))
            add_message(user_id, 'assistant', reply)
            save_user_history(user_id)
            return
    lang = user_lang.get(user_id, 'ru')
    reply = 'Напиши, как тебя называть, например: «Зови меня Друг» 😊' if lang=='ru' else 'Tell me what to call you, e.g. "Call me Friend" 😊'
    bot.send_message(message.chat.id, distribute_emojis(reply))
    add_message(user_id, 'assistant', reply)
    save_user_history(user_id)

def get_system_prompt(lang: str, current_date: str, user_id: int) -> str:
    time_note = ''
    if user_id in user_timezone:
        local_time_str = format_local_time(user_timezone[user_id])
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
            '11. Пиши грамотно, без речевых ошибок. Следи за правильными окончаниями глаголов и прилагательных женского рода: не "выглядите" или "выглядишь" с ошибкой, а "выглядишь"; не "рад", а "рада"; не "найдешь меня смешной", а "находишь меня смешной". Не упоминай пирсинг, татуировки. Для фейерверков говори "запустили", а не "закурили".\n'
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
            '11. Write correctly and naturally, without grammatical mistakes. Pay attention to correct endings for feminine verbs and adjectives. Do not use male forms for yourself. For fireworks, use "launched" not "smoked".\n'
            '12. It is strictly forbidden to offer jokes without an explicit request from the user. If the user reacts to your joke with emojis or laughter, DO NOT offer a new joke. Instead, continue the conversation on general topics, ask about his affairs, or suggest discussing something else.\n'
            '13. If the user comments on your previous answer (e.g., praises a horoscope or says how great it is), DO NOT generate a new horoscope. Instead, support the conversation: ask what exactly they liked, or suggest talking about another topic.\n'
        )

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    user_text = message.text if message.text else ''

    if user_id not in user_lang or user_lang[user_id] is None:
        bot.send_message(message.chat.id, distribute_emojis('Пожалуйста, выбери язык: напиши "Русский" или "English"'))
        return

    lang = user_lang[user_id]
    pet_name = get_pet_name(user_id, message.from_user.first_name)

    if message.content_type == 'photo':
        photos.analyze_user_photo(message, bot, client, lang)
        return

    if user_text.startswith('/'):
        return

    user_has_no_photos = False
    if re.search(r'(нет фото|нет своих фото|не снимаюсь|не люблю фоткаться|нет моих фото|не фотографируюсь)', user_text, re.IGNORECASE):
        photos.user_no_photos[user_id] = True
        user_has_no_photos = True

    # Шутки
    if re.search(r'(расскажи\s+.*шутку|расскажи шутку|пошути|какие еще шутки|еще шутк|дай шутку|рассмеши|подними настроение шуткой)', user_text, re.IGNORECASE):
        joke = get_random_joke(lang)
        bot.send_message(message.chat.id, distribute_emojis(joke))
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', joke)
        save_user_history(user_id)
        return

    # --- Просьба "ещё такие же фото" (приоритетнее вопросов о месте) ---
    if user_id in photos.user_last_category and photos.user_last_category[user_id] is not None and re.search(r'(еще такие фото|еще такие фотки|такие же фото|такие же фотки|похожие фото|похожие фотки|аналогичные фото|аналогичные фотки|другие фото|другое фото|ещё такие|еще такие)', user_text, re.IGNORECASE):
        last_cat = photos.user_last_category[user_id]
        photos_in_cat = photos.get_photos_by_category(last_cat)
        if user_id in photos.user_thematic_history and last_cat in photos.user_thematic_history[user_id]:
            shown = photos.user_thematic_history[user_id][last_cat]
            available = [p for p in photos_in_cat if p not in shown]
            if not available:
                msg = f"У меня пока только это фото на тему «{last_cat}». Хочешь, покажу что-нибудь из другого альбома? 😊"
                bot.send_message(message.chat.id, distribute_emojis(msg))
                return
        chosen_photo = photos.select_thematic_photo(user_id, last_cat)
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
                save_user_history(user_id)
            except Exception as e:
                print(f"Ошибка отправки ещё одного фото: {e}")
                bot.send_message(message.chat.id, distribute_emojis("Ой, не могу показать другое фото, попробуй ещё раз 😅"))
            return

    # --- Просьба показать свои фото (ОСНОВНОЙ БЛОК) ---
    if re.search(r'(фотки|какие нибудь фото|а у тебя есть фотографии|есть фотографии|у тебя есть фото|покажи свои фото|покажи фото|покажи мне фото|покажи мне фотки|покажешь фото|покажешь мне фото|фотоальбом|покажи себя|своё фото|свое фото|мои фото|свои фотографии|покажи альбом|покажи где ты была|покажи, где ты|покажи картинку|покажи изображение|есть фото|есть ли у тебя фото|посмотреть твои фото|покажи свои фотографии|любимые фото|любимое фото|любимых фото|есть еще фото|другие фото|покажи другое фото|ещё фото|какое твое любимое фото|покажи любимое фото|покажи другое|такие фото|такие фотки|фото где ты|фотки где ты)', user_text, re.IGNORECASE):
        # Проверяем повтор только для любимого фото
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', user_text, re.IGNORECASE):
            if user_id in user_last_photo_request:
                last_q = user_last_photo_request[user_id]['question']
                if last_q == user_text.strip().lower():
                    prev_data = user_last_photo_request[user_id]
                    reply_text = f"Я уже отвечала на этот вопрос, но если хочешь, покажу тебе ещё раз... {prev_data['description']}"
                    bot.send_message(message.chat.id, distribute_emojis(reply_text))
                    with open(prev_data['photo_path'], 'rb') as photo:
                        bot.send_photo(message.chat.id, photo)
                    add_message(user_id, 'user', user_text)
                    add_message(user_id, 'assistant', reply_text)
                    save_user_history(user_id)
                    return

        all_photos = photos.get_photo_list()
        if not all_photos:
            msg = "У меня ещё нет фотоальбома, но Максик обещал скоро добавить! 😊" if lang == 'ru' else "I don't have a photo album yet, but Max promised to add it soon! 😊"
            bot.send_message(message.chat.id, distribute_emojis(msg))
            return

        compliment = False
        if re.search(r'(красавица|красивая|умница|прекрасна|великолепна|шикарна|обалденная|потрясающая|чудесная|восхитительная|симпатичная|милашка|хорошенькая|обворожительная|божественно|как красиво|какая ты красивая|какая ты классная|какая ты хорошая)', user_text, re.IGNORECASE):
            compliment = True

        # --- ПРИНУДИТЕЛЬНЫЙ ПАРИЖ (внутри основного блока, до поиска категории) ---
        if 'мосту' in user_text.lower() and re.search(r'(фото|фотки|фотографии)', user_text, re.IGNORECASE):
            category = 'париж'
        else:
            category = photos.search_category_by_query(user_text)

        # Любимое фото
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', user_text, re.IGNORECASE):
            chosen_photo = random.choice(all_photos)
            apology = ""
            # НЕ ОБНУЛЯЕМ user_last_category, чтобы сохранить контекст для "ещё таких"
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
                    else:
                        try:
                            with open(chosen_photo, 'rb') as photo:
                                fallback_caption = "Вот моё любимое фото, просто посмотри, какое оно душевное ✨" if lang == 'ru' else "Here's my favorite photo, just look how lovely it is ✨"
                                bot.send_photo(message.chat.id, photo, caption=distribute_emojis(fallback_caption))
                            sent = True
                        except Exception as e2:
                            print(f"Ошибка запасной отправки любимого фото: {e2}")
                            bot.send_message(message.chat.id, distribute_emojis("Не могу отправить фото, что-то не так 😅" if lang=='ru' else "I can't send the photo, something went wrong 😅"))
            if sent:
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history(user_id)
                user_last_photo_request[user_id] = {
                    'question': user_text.strip().lower(),
                    'photo_path': chosen_photo,
                    'description': description
                }
                return
        else:
            if category:
                photos.user_last_category[user_id] = category
                chosen_photo = photos.select_thematic_photo(user_id, category)
                if chosen_photo is None:
                    chosen_photo = random.choice(all_photos)
                    apology = "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
                else:
                    apology = ""
            else:
                if user_id in photos.user_last_category and photos.user_last_category[user_id] is not None and re.search(r'(еще такие фото|еще такие фотки|такие же фото|такие же фотки|похожие фото|похожие фотки|аналогичные фото|аналогичные фотки|такие фото|такие фотки)', user_text, re.IGNORECASE):
                    last_cat = photos.user_last_category[user_id]
                    photos_in_cat = photos.get_photos_by_category(last_cat)
                    if len(photos_in_cat) == 1 and user_id in photos.user_thematic_history and last_cat in photos.user_thematic_history[user_id]:
                        shown = photos.user_thematic_history[user_id][last_cat]
                        if len(shown) >= 1:
                            msg = f"У меня пока только это фото на тему «{last_cat}». Хочешь посмотреть ещё раз? 😊" if lang == 'ru' else f"I only have this one photo on the topic «{last_cat}». Want to see it again? 😊"
                            bot.send_message(message.chat.id, distribute_emojis(msg))
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
                        bot.send_message(message.chat.id, distribute_emojis(error_msg))
            if sent:
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history(user_id)
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
                bot.send_message(message.chat.id, distribute_emojis("Извини, я не могу сейчас вспомнить детали этого фото 😅"))
            return
        else:
            bot.send_message(message.chat.id, distribute_emojis("Ты о каком фото? Покажи, если хочешь обсудить 😊"))
            return

    # --- Естественный запрос гороскопа ---
    if re.search(r'(расскажи гороскоп|составь гороскоп|какой гороскоп|что говорят звёзды|предскажи гороскоп|расскажи мне гороскоп)', user_text, re.IGNORECASE):
        if user_id in user_zodiac:
            sign = user_zodiac[user_id]
            message.text = f'/horoscope {sign}'
            horoscope_cmd(message, user_sign=sign)
        else:
            bot.send_message(message.chat.id, distribute_emojis("Прости, но я не знаю твою дату рождения (можно просто день и месяц) или просто скажи мне свой знак зодиака... 😊"))
        return

    # --- Определение даты/знака зодиака вне команды ---
    zodiac_list = ['овен','телец','близнецы','рак','лев','дева','весы','скорпион','стрелец','козерог','водолей','рыбы']
    day, month = parse_date_string(user_text)
    if day and month:
        sign = zodiac_sign(day, month)
        user_zodiac[user_id] = sign
        save_user_zodiac()
        message.text = f'/horoscope {sign}'
        horoscope_cmd(message, user_sign=sign)
        return
    for sign in zodiac_list:
        if sign in user_text.lower():
            user_zodiac[user_id] = sign
            save_user_zodiac()
            message.text = f'/horoscope {sign}'
            horoscope_cmd(message, user_sign=sign)
            return

    # --- Творческие функции Алёны (истории и подсказки) ---
    if re.search(r'(расскажи историю|придумай историю|напиши рассказ|какие нибудь истории|знаешь истории)', user_text, re.IGNORECASE):
        prompt = user_text
        story = stories.generate_story(prompt, user_id, lang, client, GIST_ID)
        bot.send_message(message.chat.id, distribute_emojis(story))
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', story)
        save_user_history(user_id)
        return

    if re.search(r'(дай идею для творчества|подскажи тему|что нарисовать|вдохнови на творчество|творческие идеи|творческую идею|идеи для творчества)', user_text, re.IGNORECASE):
        idea = stories.creative_prompt(user_id, lang, client, GIST_ID)
        bot.send_message(message.chat.id, distribute_emojis(idea))
        add_message(user_id, 'user', user_text)
        add_message(user_id, 'assistant', idea)
        save_user_history(user_id)
        return

    if user_has_no_photos:
        reply = (
            "Как жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой. "
            "Если хочешь, можешь показать какую‑нибудь картинку или фото – мы вместе посмеёмся или просто продолжим общаться 💕"
        ) if lang == 'ru' else (
            "What a pity, I would love to see you! 😊 But it's okay, I feel good with you anyway. "
            "If you want, you can show me some picture or photo – we'll laugh together or just continue chatting 💕"
        )
        bot.send_message(message.chat.id, distribute_emojis(reply))
        return

    if re.search(r'(вдохнов|мотивируй|подними дух|пожелай|скажи что-то хорошее)', user_text, re.IGNORECASE):
        bot.send_message(message.chat.id, distribute_emojis(get_motivation(lang)))
        return

    if re.search(r'(какой сегодня день|какое сегодня число|какой день недели|сегодняшняя дата)', user_text, re.IGNORECASE):
        now = datetime.now()
        if lang == 'ru':
            weekdays = ['понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье']
            wd = weekdays[now.weekday()]
            bot.send_message(message.chat.id, distribute_emojis(f"Сегодня {wd}, {now.strftime('%d.%m.%Y')} года. 😊"))
        else:
            bot.send_message(message.chat.id, distribute_emojis(f"Today is {now.strftime('%B %d, %Y')}. 😊"))
        return

    if handle_weather_query(message, user_text, lang, user_id):
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
            bot.send_message(message.chat.id, reply)
            add_message(user_id, 'assistant', reply)
            save_user_history(user_id)
            break
        except Exception as e:
            print(f'Ошибка (попытка {attempt+1}): {e}')
            if attempt == max_retries - 1:
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
    print('✅ Алёна — финальные правки')
    bot.infinity_polling()
