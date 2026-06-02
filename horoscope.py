# horoscope.py — Модуль гороскопа для Алёны

import re
from datetime import datetime
from typing import Dict, Optional
import telebot
from text_utils import clean_english_words, remove_non_russian

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

def format_local_time(timezone_offset: int, target_date: Optional[datetime] = None) -> str:
    from weather import format_local_time as weather_format_local_time
    return weather_format_local_time(timezone_offset, target_date)

def horoscope_cmd(message: telebot.types.Message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, user_sign: Optional[str] = None, pet_name: str = ''):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 and not user_sign:
        bot.send_message(message.chat.id, "Укажи знак или дату рождения. Примеры:\n/horoscope козерог\n/horoscope 15.06\n/horoscope 15 июня")
        return
    arg = user_sign if user_sign else parts[1].strip().lower()
    zodiac_list = ['овен','телец','близнецы','рак','лев','дева','весы','скорпион','стрелец','козерог','водолей','рыбы']
    if arg in zodiac_list:
        sign = arg
        user_zodiac[user_id] = sign
        save_user_zodiac(user_zodiac)
    else:
        day, month = parse_date_string(arg)
        if day and month:
            sign = zodiac_sign(day, month)
            user_zodiac[user_id] = sign
            save_user_zodiac(user_zodiac)
        else:
            bot.send_message(message.chat.id, "Не поняла знак или дату. Напиши, например: /horoscope козерог или /horoscope 15 июня")
            return
    today = datetime.now().strftime('%Y-%m-%d')
    local_time_note = ''
    if user_id in user_timezone:
        local_time_str = format_local_time(user_timezone[user_id])
        local_time_note = f' Сейчас у пользователя {local_time_str}.'

    greeting = f'{pet_name}, ' if pet_name else ''
    try:
        prompt = (f"Ты астролог. Составь короткое доброе предсказание для знака {sign.capitalize()} на {today}.{local_time_note} "
                  f"Начни ответ с обращения к пользователю: '{greeting}' (если имя есть, то используй его ласковую форму). "
                  f"Добавь в конце 2-3 эмодзи (😊✨💖). "
                  f"Пиши на русском, без английских слов. НЕ начинай ответ с 'Здравствуй' или 'Привет'. "
                  f"НИ В КОЕМ СЛУЧАЕ не упоминай текущее время суток (утро, день, вечер, обед), не предполагай, что пользователь уже что-то сделал или не сделал. "
                  f"Говори 'твой гороскоп', 'тебе предсказание', не путай 'свой' и 'твой'."
                  f"Обращайся на 'ты'.")
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7, max_tokens=300, timeout=5
        )
        text = resp.choices[0].message.content.strip()
        text = clean_english_words(text)
        text = remove_non_russian(text)
        if pet_name and not text.startswith(pet_name):
            text = f"{pet_name}, {text[0].lower()}{text[1:]}" if text else text
        bot.send_message(message.chat.id, text)
        add_message(user_id, 'user', f'/horoscope {sign}' if not parts else message.text)
        add_message(user_id, 'assistant', text)
        save_user_history()
    except:
        bot.send_message(message.chat.id, "Не удалось составить гороскоп 😅 Попробуй позже.")

def handle_natural_horoscope(message: telebot.types.Message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, pet_name: str = ''):
    user_id = message.from_user.id
    user_text = message.text
    if re.search(r'(расскажи гороскоп|составь гороскоп|какой гороскоп|что говорят звёзды|предскажи гороскоп|расскажи мне гороскоп)', user_text, re.IGNORECASE):
        if user_id in user_zodiac:
            sign = user_zodiac[user_id]
            message.text = f'/horoscope {sign}'
            horoscope_cmd(message, bot, client, user_lang, user_zodiac, user_timezone, save_user_zodiac, add_message, save_user_history, user_sign=sign, pet_name=pet_name)
        else:
            bot.send_message(message.chat.id, "Прости, но я не знаю твою дату рождения (можно просто день и месяц) или просто скажи мне свой знак зодиака... 😊")
        return True
    return False
