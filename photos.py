# photos.py — Модуль фотоальбома Алёны (исправлен порядок категорий)

import os
import random
import base64
import re
import time
from typing import Dict, Optional, List
from text_utils import clean_english_words, remove_non_russian, distribute_emojis, SAFE_EMOJIS

PHOTO_FOLDER = 'images'
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif')
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_BASE64_SIZE = 4 * 1024 * 1024

# Категории строго от специфичных к общим (как в исходной рабочей версии)
KEYWORD_MAP = {
    'кормит птиц': ['кормит птиц', 'птиц', 'голуби', 'корм'],
    'зима': ['зима', 'зимой', 'зимние', 'лыжи', 'лыжах', 'кататься', 'катаешься'],
    'пикник': ['пикник', 'пикнике', 'пикника', 'пикником', 'плед', 'корзина', 'еда', 'фрукты', 'клубника'],
    'париж': ['париж', 'франция', 'eiffel', 'лувр', 'парк', 'фонтан', 'мост', 'мосту', 'моста', 'мостом'],
    'осень': ['осень', 'осенние', 'осенью', 'листья'],
    'собака': ['собака', 'собакой', 'собаке', 'собаку', 'пёс', 'щенок', 'играю', 'играешь', 'гуляю', 'гуляешь'],
    'набережная': ['набережная', 'набережную', 'набережной', 'причал', 'яхта', 'порт'],
    'дома': ['дома', 'дом', 'квартира', 'комната', 'уют', 'свитер', 'плед', 'свечи'],
    'горы': ['горы', 'горах', 'гора', 'горный', 'вершина', 'скалы'],
    'парк': ['парк', 'парке', 'сквер', 'аллея', 'фонтан', 'зелень', 'голубей'],
    'пляж': ['пляж', 'море', 'берег', 'песок', 'океан', 'купальник', 'вода', 'воде', 'воду', 'водой', 'купаюсь', 'купаешься', 'купаться', 'плаваю', 'плаваешь'],
    'природа': ['природа', 'природе', 'на природе', 'поле', 'луг', 'лес', 'озеро', 'река', 'трава', 'деревья'],
    'город': ['город', 'городе', 'улица', 'проспект', 'площадь']
}

user_last_sent_photo: Dict[int, str] = {}
user_no_photos: Dict[int, bool] = {}
user_thematic_history: Dict[int, Dict[str, set]] = {}
user_last_category: Dict[int, str] = {}
user_last_user_image_desc: Dict[int, str] = {}

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
            description = clean_english_words(description)
            description = remove_non_russian(description)
            description = distribute_emojis(description)
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

def try_paris_photo(user_id: int, user_text: str, lang: str, bot, message, client, add_message, save_user_history, save_user_last_photo):
    if 'мосту' not in user_text.lower():
        return False
    if not re.search(r'(фото|фотки|фотографии)', user_text, re.IGNORECASE):
        return False

    all_photos = get_photo_list()
    paris_photos = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p) and 'париж' in get_keywords_from_photo_name(p)]
    if not paris_photos:
        paris_photos = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p)]

    if paris_photos:
        category = 'париж'
        user_last_category[user_id] = category
        if user_id in user_thematic_history and category in user_thematic_history[user_id]:
            shown = user_thematic_history[user_id][category]
            available = [p for p in paris_photos if p not in shown]
            if available:
                chosen_photo = random.choice(available)
            else:
                shown.clear()
                chosen_photo = random.choice(paris_photos)
        else:
            chosen_photo = random.choice(paris_photos)

        if user_id not in user_thematic_history:
            user_thematic_history[user_id] = {}
        if category not in user_thematic_history[user_id]:
            user_thematic_history[user_id][category] = set()
        user_thematic_history[user_id][category].add(chosen_photo)

        user_last_sent_photo[user_id] = chosen_photo
        save_user_last_photo(user_id, chosen_photo)
        try:
            if lang == 'ru':
                analysis_prompt = "Начни свой ответ с душевного восклицания, например: 'Конечно, у меня есть такие фото!' или 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
            else:
                analysis_prompt = "Start your answer with a warm phrase, e.g., 'I'm so glad you asked! Here's one of my photos...' Then describe the photo: what you are doing, where you are, what mood you are in. Tell a short story. Be sure to add 2-3 emojis to make the description lively. Do not start with 'Hello'."
            description = analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
            if description.startswith('Привет'):
                description = re.sub(r'^Привет[,!\s]*', '', description)
            description = distribute_emojis(description)
            with open(chosen_photo, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=description)
            add_message(user_id, 'user', user_text)
            add_message(user_id, 'assistant', description)
            save_user_history()
            return True
        except Exception as e:
            print(f"Ошибка отправки фото моста: {e}")
            bot.send_message(message.chat.id, "Ой, не могу показать фото моста, попробуй ещё раз 😅")
            return True
    return False
