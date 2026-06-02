# gender.py — Модуль распознавания пола собеседника

import re
from typing import Dict, Optional

# Простые однозначные имена (добавлены все ласковые формы из default_pet_name)
GENDER_MAP = {
    'максим': 'male', 'макс': 'male', 'максик': 'male',
    'владимир': 'male', 'вова': 'male', 'вовочка': 'male',
    'александр': 'male', 'саня': 'male', 'саша': None, 'сашенька': None,
    'анна': 'female', 'анечка': 'female',
    'екатерина': 'female', 'катя': 'female', 'катюша': 'female',
    'джон': 'male', 'джонни': 'male',
    'иван': 'male', 'ваня': 'male', 'ванюша': 'male',
    'сергей': 'male', 'серёжа': 'male',
    'михаил': 'male', 'миша': 'male',
    'дмитрий': 'male', 'дима': 'male',
    'андрей': 'male', 'андрюша': 'male',
    'алексей': 'male', 'лёша': 'male',
    'олег': 'male', 'олежек': 'male',
    'пётр': 'male', 'петя': 'male', 'петр': 'male',
    'женя': None, 'валя': None,
    'вадим': 'male', 'вадик': 'male',
    'даша': 'female', 'дарья': 'female',
    'мария': 'female', 'маша': 'female',
    'лиза': 'female', 'елизавета': 'female',
    'лена': 'female', 'алена': 'female',
    'ольга': 'female', 'оля': 'female',
    'татьяна': 'female', 'таня': 'female',
    'юлия': 'female', 'юля': 'female',
}

def get_gender_by_name(name: str) -> Optional[str]:
    """Возвращает 'male', 'female' или None, если пол не определён."""
    name_lower = name.strip().lower()
    return GENDER_MAP.get(name_lower)

def is_name_like(text: str) -> bool:
    """Проверяет, похожа ли строка на имя (только буквы, пробелы, дефис)."""
    return bool(re.match(r'^[А-Яа-яЁё\s\-]+$', text))

def ensure_gender_known(user_id: int, first_name: str, user_preferences: Dict[int, str],
                        user_gender: Dict[int, str], user_awaiting_gender: Dict[int, bool],
                        bot, message, save_user_gender_func) -> bool:
    """
    Проверяет, знаем ли мы пол пользователя.
    Если нет – пытается определить по имени, а при необходимости задаёт вопрос.
    Возвращает True, если пол уже известен (можно продолжать диалог),
    и False, если бот задал вопрос и ждёт ответа.
    """
    # Если пол уже сохранён, всё хорошо
    if user_id in user_gender:
        return True

    # Если пользователь сейчас отвечает на вопрос о поле
    if user_awaiting_gender.get(user_id):
        answer = message.text.strip().lower()
        if answer in ['парень', 'мужчина', 'мужской', 'м', 'мальчик', 'male', 'я парень']:
            user_gender[user_id] = 'male'
            user_awaiting_gender[user_id] = False
            save_user_gender_func()
            bot.send_message(message.chat.id, "Поняла! Буду знать 😊💖")
            return True
        elif answer in ['девушка', 'женщина', 'женский', 'ж', 'девочка', 'female', 'я девушка']:
            user_gender[user_id] = 'female'
            user_awaiting_gender[user_id] = False
            save_user_gender_func()
            bot.send_message(message.chat.id, "Поняла! Буду знать 😊💖")
            return True
        else:
            bot.send_message(message.chat.id, "Прости, я не совсем поняла... Скажи, пожалуйста: ты парень или девушка? 😊")
            return False

    # Пытаемся определить по имени
    name_to_check = user_preferences.get(user_id) or first_name
    gender = get_gender_by_name(name_to_check)

    if gender is not None:
        # Пол определён однозначно
        user_gender[user_id] = gender
        save_user_gender_func()
        return True

    # Имя неоднозначное или не похоже на имя – спрашиваем, как обращаться (если ещё не спросили)
    if not user_preferences.get(user_id):
        bot.send_message(message.chat.id, f"Я хочу обращаться к тебе правильно! Как мне тебя называть? 😊")
        return False

    # Имя уже есть в preferences, но пол не ясен – задаём вопрос о поле
    user_awaiting_gender[user_id] = True
    bot.send_message(message.chat.id, f"{user_preferences[user_id]}, скажи, пожалуйста: ты парень или девушка? 😊💖")
    return False
