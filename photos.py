# photos.py — Модуль фотоальбома Алёны

import os
import random
import base64
import re
import time
from typing import Dict, Optional, List

PHOTO_FOLDER = 'images'
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif')
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_BASE64_SIZE = 4 * 1024 * 1024

KEYWORD_MAP = {
    'пляж': ['пляж', 'море', 'берег', 'песок', 'океан', 'купальник', 'вода', 'воде', 'воду', 'водой', 'купаюсь', 'купаешься', 'купаться', 'плаваю', 'плаваешь'],
    'набережная': ['набережная', 'набережную', 'набережной', 'причал', 'яхта', 'порт'],
    'горы': ['горы', 'горах', 'гора', 'горный', 'вершина', 'скалы'],
    'парк': ['парк', 'парке', 'сквер', 'аллея', 'фонтан', 'зелень', 'голубей'],
    'пикник': ['пикник', 'пикнике', 'пикника', 'пикником', 'плед', 'корзина', 'еда', 'фрукты', 'клубника'],
    'город': ['город', 'городе', 'улица', 'проспект', 'площадь'],
    'дома': ['дома', 'дом', 'квартира', 'комната', 'уют', 'свитер', 'плед', 'свечи'],
    'кормит птиц': ['кормит птиц', 'птиц', 'голуби', 'корм'],
    'природа': ['природа', 'природе', 'на природе', 'поле', 'луг', 'лес', 'озеро', 'река', 'трава', 'деревья'],
    'париж': ['париж', 'франция', 'eiffel', 'лувр', 'парк', 'фонтан', 'мост', 'мосту', 'моста', 'мостом'],
    'осень': ['осень', 'осенние', 'осенью', 'листья'],
    'зима': ['зима', 'зимой', 'зимние', 'лыжи', 'лыжах', 'кататься', 'катаешься'],
    'собака': ['собака', 'собакой', 'собаке', 'собаку', 'пёс', 'щенок', 'играю', 'играешь', 'гуляю', 'гуляешь']
}

user_last_sent_photo: Dict[int, str] = {}
user_no_photos: Dict[int, bool] = {}
user_thematic_history: Dict[int, Dict[str, set]] = {}
user_last_category: Dict[int, str] = {}
user_last_user_image_desc: Dict[int, str] = {}

def _clean_english(text: str) -> str:
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

def _remove_non_russian(text: str) -> str:
    cleaned = re.sub(r'[^А-Яа-яЁё\s\d\.,!?:;…\-–—""\'«»()/#@\*\+—\u2700-\u27BF\u1F600-\u1F64F\u1F300-\u1F5FF\u1F680-\u1F6FF\u1F1E0-\u1F1FF\u2600-\u26FF\u2700-\u27BF]', '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

SAFE_EMOJIS = ['😊', '💖', '✨', '😄', '😘', '🥰', '💕', '🤗']

def _filter_emojis(text: str) -> str:
    allowed = set(SAFE_EMOJIS)
    result = []
    for ch in text:
        if '\U0001F000' <= ch <= '\U0001FFFF' or '\u2600' <= ch <= '\u27BF':
            if ch in allowed:
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)

def _distribute_emojis(text: str) -> str:
    text = _filter_emojis(text)
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

def get_photo_list() -> List[str]:
    if not os.path.exists(PHOTO_FOLDER):
        os.makedirs(PHOTO_FOLDER, exist_ok=True)
        return []
    return [os.path.join(PHOTO_FOLDER, f) for f in os.listdir(PHOTO_FOLDER) if f.lower().endswith(SUPPORTED_EXTENSIONS)]

def get_keywords_from_photo_name(photo_path: str) -> str:
    name = os.path.basename(photo_path).lower()
    name = os.path.splitext(name)[0]
    return name

def search_category_by_query(query: str) -> Optional[str]:
    query_lower = query.lower()
    for cat, words in KEYWORD_MAP.items():
        for w in words:
            if w in query_lower:
                return cat
    return None

def get_photos_by_category(category: str) -> List[str]:
    all_photos = get_photo_list()
    if not all_photos:
        return []
    if category not in KEYWORD_MAP:
        return []
    synonyms = KEYWORD_MAP[category]
    matching = []
    for photo in all_photos:
        name = get_keywords_from_photo_name(photo)
        for syn in synonyms:
            if syn in name:
                matching.append(photo)
                break
    return matching

def select_thematic_photo(user_id: int, category: str) -> Optional[str]:
    all_thematic = get_photos_by_category(category)
    if not all_thematic:
        return None
    if user_id not in user_thematic_history:
        user_thematic_history[user_id] = {}
    if category not in user_thematic_history[user_id]:
        user_thematic_history[user_id][category] = set()
    shown = user_thematic_history[user_id][category]
    available = [p for p in all_thematic if p not in shown]
    if available:
        chosen = random.choice(available)
    else:
        shown.clear()
        chosen = random.choice(all_thematic)
    shown.add(chosen)
    return chosen

def analyze_photo_with_vision(image_path: str, prompt: str, client, lang: str = 'ru') -> str:
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
            max_tokens=400,
            timeout=15
        )
        description = response.choices[0].message.content.strip()
        if lang == 'ru':
            description = _clean_english(description)
            description = _remove_non_russian(description)
            description = _distribute_emojis(description)
        return description
    except Exception as e:
        print(f"Ошибка vision-анализа: {e}")
        return "Ой, что-то пошло не так при анализе фото. Попробуй ещё раз 😅"

def analyze_user_photo(message, bot, client, lang: str) -> bool:
    try:
        if not message.photo:
            bot.send_message(message.chat.id, "Пожалуйста, отправь фото как изображение, а не как файл 😊")
            return False
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_path = f"temp_user_image_{message.from_user.id}_{int(time.time())}.jpg"
        with open(temp_path, 'wb') as f:
            f.write(downloaded_file)
        if lang == 'ru':
            prompt = "Ты Алёна, добрая, весёлая, обаятельная девушка. Опиши это фото коротко (2-3 предложения). Будь тёплой, добавь эмодзи. Не начинай ответ с 'Привет'."
        else:
            prompt = "You are Alena, a kind, cheerful, charming girl. Describe this photo briefly (2-3 sentences). Be warm, add emojis. Do not start with 'Hello'."
        description = analyze_photo_with_vision(temp_path, prompt, client, lang)
        os.remove(temp_path)
        user_last_user_image_desc[message.from_user.id] = description
        bot.send_message(message.chat.id, description)
        return True
    except Exception as e:
        print(f"Ошибка обработки фото пользователя: {e}")
        if lang == 'ru':
            bot.send_message(message.chat.id, "Что-то не так с фото, может, попробуешь другое? 😊")
        else:
            bot.send_message(message.chat.id, "Something's wrong with the photo, maybe try another one? 😊")
        return False
