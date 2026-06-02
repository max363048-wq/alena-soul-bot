# photos.py — Модуль фотоальбома Алёны (полная логика показа фото)

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

# Категории строго от специфичных к общим (как в исходной стабильной версии)
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

# Словари (будут импортированы из main.py или определены здесь)
user_last_sent_photo: Dict[int, str] = {}
user_no_photos: Dict[int, bool] = {}
user_thematic_history: Dict[int, Dict[str, set]] = {}
user_last_category: Dict[int, str] = {}
user_last_user_image_desc: Dict[int, str] = {}

user_last_photo_request: Dict[int, Dict[str, str]] = {}
user_pending_photo_offer: Dict[int, bool] = {}
user_last_favorite_photo: Dict[int, str] = {}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ФОТОАЛЬБОМА ----------
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

def try_paris_photo(user_id: int, user_text: str, lang: str, bot, message, client, add_message, save_user_history, save_user_last_photo_func):
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
        save_user_last_photo_func(user_id, chosen_photo)
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

def handle_favorite_photo_repeat(user_id, lang, bot, message):
    """Если любимое фото уже было показано, предлагает повторить. Возвращает True, если обработано."""
    if user_id in user_last_favorite_photo:
        prev_path = user_last_favorite_photo[user_id]
        reply_text = "Я тебе уже показывала своё любимое фото, но если хочешь, покажу его ещё раз! 😊"
        try:
            bot.send_message(message.chat.id, distribute_emojis(reply_text))
            with open(prev_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo)
            return True
        except Exception as e:
            print(f"Ошибка повтора любимого фото: {e}")
            return False
    return False

# --- ГЛАВНАЯ ФУНКЦИЯ ОБРАБОТКИ ФОТО-ЗАПРОСОВ ---
def handle_photo_request(user_id: int, user_text: str, lang: str, bot, message, client,
                         add_message, save_user_history, save_user_last_photo_func,
                         save_user_last_favorite_photo_func, user_has_no_photos: bool = False):
    """
    Обрабатывает любой запрос, связанный с показом фото.
    Возвращает True, если фото было отправлено (или обработано), иначе False.
    """
    # --- ГАРАНТИРОВАННЫЙ ПАРИЖ (САМЫЙ ПЕРВЫЙ!) ---
    if try_paris_photo(user_id, user_text, lang, bot, message, client, add_message, save_user_history, save_user_last_photo_func):
        user_pending_photo_offer[user_id] = False
        return True

    # --- Просьба "ещё такие же фото" ---
    if user_id in user_last_category and user_last_category[user_id] is not None and re.search(r'(еще такие фото|еще такие фотки|такие же фото|такие же фотки|похожие фото|похожие фотки|аналогичные фото|аналогичные фотки|другие фото|другое фото|ещё такие|еще такие|еще такое фото|ещё такое фото|такое же фото|ещё такие фотки)', user_text, re.IGNORECASE):
        user_pending_photo_offer[user_id] = False
        last_cat = user_last_category[user_id]
        if last_cat == 'париж':
            all_photos = get_photo_list()
            paris_photos = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p) and 'париж' in get_keywords_from_photo_name(p)]
            if not paris_photos:
                paris_photos = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p)]
            if paris_photos:
                if user_id in user_thematic_history and last_cat in user_thematic_history[user_id]:
                    shown = user_thematic_history[user_id][last_cat]
                    available = [p for p in paris_photos if p not in shown]
                else:
                    available = paris_photos
                if available:
                    chosen_photo = random.choice(available)
                    if user_id not in user_thematic_history:
                        user_thematic_history[user_id] = {}
                    if last_cat not in user_thematic_history[user_id]:
                        user_thematic_history[user_id][last_cat] = set()
                    user_thematic_history[user_id][last_cat].add(chosen_photo)
                else:
                    try:
                        bot.send_message(message.chat.id, "У меня пока только это фото на тему «Париж». Хочешь, покажу что-нибудь из другого альбома? 😊")
                    except:
                        pass
                    return True
            else:
                try:
                    bot.send_message(message.chat.id, "Ой, не могу найти парижские фото, попробуй ещё раз 😅")
                except:
                    pass
                return True
        else:
            chosen_photo = select_thematic_photo(user_id, last_cat)
            if chosen_photo is None:
                try:
                    bot.send_message(message.chat.id, f"У меня пока только это фото на тему «{last_cat}». Хочешь, покажу что-нибудь из другого альбома? 😊")
                except:
                    pass
                return True

        if chosen_photo:
            user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo_func(user_id, chosen_photo)
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
                description = analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
                if description.startswith('Привет'):
                    description = re.sub(r'^Привет[,!\s]*', '', description)
                description = distribute_emojis(description)
                with open(chosen_photo, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=description)
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
            except Exception as e:
                print(f"Ошибка отправки ещё одного фото: {e}")
                try:
                    bot.send_message(message.chat.id, "Ой, не могу показать другое фото, попробуй ещё раз 😅")
                except:
                    pass
            return True

    # --- Основной показ фото (любимое, тематическое, случайное) ---
    if re.search(r'(фотки|какие нибудь фото|а у тебя есть фотографии|есть фотографии|у тебя есть фото|покажи свои фото|покажи фото|покажи мне фото|покажи мне фотки|покажешь фото|покажешь мне фото|фотоальбом|покажи себя|своё фото|свое фото|мои фото|свои фотографии|покажи альбом|покажи где ты была|покажи, где ты|покажи картинку|покажи изображение|есть фото|есть ли у тебя фото|посмотреть твои фото|покажи свои фотографии|любимые фото|любимое фото|любимых фото|есть еще фото|другие фото|покажи другое фото|ещё фото|какое твое любимое фото|покажи любимое фото|покажи другое|такие фото|такие фотки|фото где ты|фотки где ты|какие фото у тебя еще есть|какие фото ещё есть|какие у тебя ещё фото|какие ещё фото|какие фото еще|какие еще фото|какие у тебя есть фото)', user_text, re.IGNORECASE):
        user_pending_photo_offer[user_id] = False

        # Проверка на повтор любимого фото
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', user_text, re.IGNORECASE):
            if handle_favorite_photo_repeat(user_id, lang, bot, message):
                add_message(user_id, 'user', user_text)
                save_user_history()
                return True

        all_photos = get_photo_list()
        if not all_photos:
            msg = "У меня ещё нет фотоальбома, но Максик обещал скоро добавить! 😊" if lang == 'ru' else "I don't have a photo album yet, but Max promised to add it soon! 😊"
            try:
                bot.send_message(message.chat.id, msg)
            except:
                pass
            return True

        compliment = False
        if re.search(r'(красавица|красивая|умница|прекрасна|великолепна|шикарна|обалденная|потрясающая|чудесная|восхитительная|симпатичная|милашка|хорошенькая|обворожительная|божественно|как красиво|какая ты красивая|какая ты классная|какая ты хорошая)', user_text, re.IGNORECASE):
            compliment = True

        # Любимое фото (первый показ)
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', user_text, re.IGNORECASE):
            chosen_photo = random.choice(all_photos)
            apology = ""
            user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo_func(user_id, chosen_photo)
            # Запоминаем как последнее любимое фото
            user_last_favorite_photo[user_id] = chosen_photo
            save_user_last_favorite_photo_func()
            # НЕ переопределяем категорию!

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
                    description = analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
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
                        user_last_sent_photo[user_id] = chosen_photo
                        save_user_last_photo_func(user_id, chosen_photo)
                        user_last_favorite_photo[user_id] = chosen_photo
                        save_user_last_favorite_photo_func()
                    else:
                        try:
                            with open(chosen_photo, 'rb') as photo:
                                fallback_caption = "Вот моё любимое фото, просто посмотри, какое оно душевное ✨" if lang == 'ru' else "Here's my favorite photo, just look how lovely it is ✨"
                                bot.send_photo(message.chat.id, photo, caption=distribute_emojis(fallback_caption))
                            sent = True
                        except Exception as e2:
                            print(f"Ошибка запасной отправки любимого фото: {e2}")
                            try:
                                bot.send_message(message.chat.id, "Не могу отправить фото, что-то не так 😅")
                            except:
                                pass
            if sent:
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
                user_last_photo_request[user_id] = {
                    'question': user_text.strip().lower(),
                    'photo_path': chosen_photo,
                    'description': description
                }
                return True
        else:
            category = search_category_by_query(user_text)
            if category:
                user_last_category[user_id] = category
                chosen_photo = select_thematic_photo(user_id, category)
                if chosen_photo is None:
                    chosen_photo = random.choice(all_photos)
                    apology = "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
                else:
                    apology = ""
            else:
                if user_id in user_last_category and user_last_category[user_id] is not None and re.search(r'(еще такие|такие же|похожие|аналогичные|ещё такие)', user_text, re.IGNORECASE):
                    last_cat = user_last_category[user_id]
                    chosen_photo = select_thematic_photo(user_id, last_cat)
                    if chosen_photo is None:
                        chosen_photo = random.choice(all_photos)
                        apology = "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
                    else:
                        apology = ""
                else:
                    # Случайное фото – запоминаем категорию
                    chosen_photo = random.choice(all_photos)
                    apology = ""
                    photo_name = get_keywords_from_photo_name(chosen_photo)
                    cat_found = False
                    for cat, words in KEYWORD_MAP.items():
                        if any(syn in photo_name for syn in words):
                            user_last_category[user_id] = cat
                            if user_id not in user_thematic_history:
                                user_thematic_history[user_id] = {}
                            if cat not in user_thematic_history[user_id]:
                                user_thematic_history[user_id][cat] = set()
                            user_thematic_history[user_id][cat].add(chosen_photo)
                            cat_found = True
                            break
                    if not cat_found:
                        user_last_category[user_id] = None

            user_last_sent_photo[user_id] = chosen_photo
            save_user_last_photo_func(user_id, chosen_photo)

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
                    description = analyze_photo_with_vision(chosen_photo, analysis_prompt, client, lang)
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
                        user_last_sent_photo[user_id] = chosen_photo
                        save_user_last_photo_func(user_id, chosen_photo)
                        photo_name = get_keywords_from_photo_name(chosen_photo)
                        cat_found = False
                        for cat, words in KEYWORD_MAP.items():
                            if any(syn in photo_name for syn in words):
                                user_last_category[user_id] = cat
                                if user_id not in user_thematic_history:
                                    user_thematic_history[user_id] = {}
                                if cat not in user_thematic_history[user_id]:
                                    user_thematic_history[user_id][cat] = set()
                                user_thematic_history[user_id][cat].add(chosen_photo)
                                cat_found = True
                                break
                        if not cat_found:
                            user_last_category[user_id] = None
                    else:
                        error_msg = "Не могу отправить фото, что-то не так 😅" if lang=='ru' else "I can't send the photo, something went wrong 😅"
                        try:
                            bot.send_message(message.chat.id, error_msg)
                        except:
                            pass
            if sent:
                add_message(user_id, 'user', user_text)
                add_message(user_id, 'assistant', description)
                save_user_history()
                return True

    return False
