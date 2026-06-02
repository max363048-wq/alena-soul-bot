# weather.py — Модуль погоды для Алёны

import os
import re
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Any
import telebot
from text_utils import clean_english_words, remove_non_russian, distribute_emojis

TEXT_NUMBERS = {
    'один': 1, 'одну': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5,
    'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10
}

def extract_city(text: str, user_id: Optional[int] = None, user_last_city: Dict[int, str] = None) -> Optional[str]:
    # Сначала проверяем косвенные указания – они имеют приоритет
    if user_last_city and user_id in user_last_city and re.search(r'(у нас|в нашем городе|в моём городе|в своем городе|в этом городе|в этом|в нашем|здесь)', text, re.IGNORECASE):
        return user_last_city[user_id]

    match = re.search(r'\b(?:в|во|в городе)\s+([А-Яа-я\-]+(?:[-\s]?[А-Яа-я]+)?)', text, re.IGNORECASE)
    if match:
        city = match.group(1).strip().lower()
        city = re.sub(r'\b(ночь|день|вечер|утро|сегодня|завтра|послезавтра|через|будет|самом|начале|начало|начал|сейчас|погода|там|тут)\b', '', city).strip()
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

    # Дополнительные проверки с прогнозными словами
    if user_last_city and re.search(r'(завтра|послезавтра|будет|через \d+|на неделю|на (два|три|четыре|пять) дня|в ближайшие (два|три|четыре|пять) дня)', text, re.IGNORECASE):
        if re.search(r'(погод|температур|дождь|солнце|ветер|градусов)', text, re.IGNORECASE):
            if user_id and user_id in user_last_city:
                return user_last_city[user_id]
    if user_last_city and re.search(r'(сколько градусов|температура|погода|градусов|холодно|тепло)', text, re.IGNORECASE):
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
    api_key = os.getenv('WEATHER_API_KEY')
    if not api_key:
        return None
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric&lang={lang}"
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
    api_key = os.getenv('WEATHER_API_KEY')
    if not api_key:
        return None
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={api_key}&units=metric&lang={lang}"
    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if resp.status_code != 200:
            return None
        target_date = (datetime.utcnow() + timedelta(days=day_delta)).date()
        temps, descs = [], []
        timezone_offset = data.get('city', {}).get('timezone', 0)
        for item in data['list']:
            dt = datetime.utcfromtimestamp(item['dt'])
            if dt.date() == target_date:
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

def generate_natural_weather_response(city: str, weather_data: Dict, lang: str = 'ru', is_forecast: bool = False, day_name: str = '', client=None) -> str:
    if not weather_data:
        return f"Не удалось получить данные о погоде для {city}. Проверь название города 😊"

    timezone_offset = weather_data.get('timezone', 0)
    local_time_str = format_local_time(timezone_offset)

    if is_forecast:
        temp = weather_data['temp']
        desc = weather_data['desc']
        fallback = f"{day_name.capitalize()} в {city} обещают {desc}, около {temp:.0f}°C. Одевайся по погоде и пусть день будет прекрасным! 😊💖"
        prompt = (f"Ты Алёна. Пользователь спросил погоду на {day_name} в {city}. "
                  f"Реальные данные: {desc}, температура {temp:.0f}°C. "
                  f"Сейчас в городе {local_time_str}. "
                  f"Ответь тепло, коротко (2-3 предложения), с эмодзи. "
                  f"НИ В КОЕМ СЛУЧАЕ не называй дату, день недели и точное время. "
                  f"Не упоминай осень, сентябрь, зиму или холодные сезоны, если это не зима. "
                  f"Используй только точные цифры: {temp:.0f}°C и описание {desc}. "
                  f"Без английских слов. Не начинай ответ с приветствия.")
    else:
        desc = weather_data['desc']
        temp = weather_data['temp']
        feels = weather_data['feels']
        hum = weather_data['hum']
        wind = weather_data['wind']
        fallback = f"Сейчас в {city} {desc}, {temp:.0f}°C (ощущается как {feels:.0f}°C). Влажность {hum}%, ветер {wind} м/с. Пусть день принесёт радость! 😊💕"
        prompt = (f"Ты Алёна. Пользователь спросил о погоде в {city}. "
                  f"Реальные данные: сейчас {desc}, температура {temp:.0f}°C, ощущается как {feels:.0f}°C, влажность {hum}%, ветер {wind} м/с. "
                  f"Сейчас в городе {local_time_str}. "
                  f"Ответь тепло, коротко (2-3 предложения), с эмодзи. "
                  f"НИ В КОЕМ СЛУЧАЕ не называй дату, день недели и точное время. "
                  f"Не упоминай осень, сентябрь, зиму или холодные сезоны, если на улице не зима. "
                  f"Используй только точные цифры: {temp:.0f}°C, {desc}. "
                  f"Не пиши 'мне нужно проверить' или 'я не знаю' – ты уже знаешь данные. "
                  f"Без английских слов. Не начинай ответ с приветствия.")
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=150, timeout=5
        )
        reply = resp.choices[0].message.content.strip()
        reply = clean_english_words(reply)
        reply = remove_non_russian(reply)
        reply = re.sub(r'\s+', ' ', reply).strip()
        temp_int = int(round(temp))
        if str(temp_int) not in reply and str(temp_int+1) not in reply and str(temp_int-1) not in reply:
            return fallback
        return distribute_emojis(reply)
    except:
        return distribute_emojis(fallback)

def handle_weather_query(message: telebot.types.Message, user_text: str, lang: str, user_id: int, user_last_city: Dict[int, str], user_timezone: Dict[int, int], client, save_user_history, save_user_timezone, add_message, bot) -> bool:
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
        day_deltas = list(range(0, num_days))
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

    city = extract_city(user_text, user_id, user_last_city)
    if not city:
        bot.send_message(message.chat.id, "В каком городе тебя интересует погода? Напиши название, например: Санкт-Петербург 😊")
        add_message(user_id, 'user', user_text)
        save_user_history()
        return True
    user_last_city[user_id] = city
    add_message(user_id, 'user', user_text)

    if is_multi_day:
        # Собираем реальные данные по дням
        day_data = []
        for d in day_deltas:
            if d == 0:
                wdata = get_current_weather(city, lang)
                label = 'сегодня'
            else:
                wdata = get_forecast_for_day(city, d, lang)
                if d == 1:
                    label = 'завтра'
                elif d == 2:
                    label = 'послезавтра'
                else:
                    label = f'через {d} дней'

            if wdata:
                timezone_offset = wdata.get('timezone', 0)
                user_timezone[user_id] = timezone_offset
                save_user_timezone(user_timezone)
                day_data.append({
                    'label': label,
                    'desc': wdata['desc'],
                    'temp': wdata['temp'],
                    'timezone_offset': timezone_offset
                })
            else:
                day_data.append({
                    'label': label,
                    'desc': None,
                    'temp': None,
                    'timezone_offset': 0
                })

        # Формируем промпт для LLM
        data_lines = []
        for d in day_data:
            if d['desc']:
                data_lines.append(f"{d['label']}: {d['desc']}, около {d['temp']:.0f}°C")
            else:
                data_lines.append(f"{d['label']}: данные пока недоступны")
        data_text = '\n'.join(data_lines)

        prompt = (f"Ты Алёна. Пользователь спросил погоду в {city} на ближайшие дни. "
                  f"Вот ТОЛЬКО РЕАЛЬНЫЕ данные, которые у тебя есть:\n{data_text}\n\n"
                  f"Составь тёплый, короткий ответ (3-5 предложений) на основе ТОЛЬКО этих данных. "
                  f"Не придумывай ничего нового. Не называй дни недели. "
                  f"Для дней, где данных нет, скажи, что пока не знаешь, но обязательно узнаешь позже. "
                  f"Добавь эмодзи. Без английских слов. Не начинай с приветствия.")

        try:
            resp = client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.7, max_tokens=250, timeout=8
            )
            reply = resp.choices[0].message.content.strip()
        except:
            # Если LLM не ответила, соберём простой список
            reply = '\n'.join([f"• {d['label'].capitalize()}: {d['desc']}, около {d['temp']:.0f}°C" if d['desc'] else f"• {d['label'].capitalize()}: данные недоступны" for d in day_data])

        reply = clean_english_words(reply)
        reply = remove_non_russian(reply)
        reply = distribute_emojis(reply)
        bot.send_message(message.chat.id, reply)
        add_message(user_id, 'assistant', reply)
        save_user_history()
        return True

    if day_delta == 0:
        weather_data = get_current_weather(city, lang)
        if weather_data:
            if 'timezone' in weather_data:
                user_timezone[user_id] = weather_data['timezone']
                save_user_timezone(user_timezone)
            reply = generate_natural_weather_response(city, weather_data, lang, is_forecast=False, client=client)
        else:
            reply = f"Не удалось получить текущую погоду для {city}. Проверь название города 😊"
    else:
        forecast = get_forecast_for_day(city, day_delta, lang)
        if forecast:
            if 'timezone' in forecast:
                user_timezone[user_id] = forecast['timezone']
                save_user_timezone(user_timezone)
            reply = generate_natural_weather_response(city, forecast, lang, is_forecast=True, day_name=day_name, client=client)
        else:
            reply = f"Не удалось получить прогноз на {day_name} для {city}. Попробуй позже 😊"
    bot.send_message(message.chat.id, reply)
    add_message(user_id, 'assistant', reply)
    save_user_history()
    return True
