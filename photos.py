# photos.py — финальный модуль фотоальбома (расширено регулярное выражение)

import os, random, base64, re, time
from typing import Dict, Optional, List
from text_utils import clean_english_words, remove_non_russian, distribute_emojis, SAFE_EMOJIS

PHOTO_FOLDER = 'images'
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif')
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_BASE64_SIZE = 4 * 1024 * 1024

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
user_last_photo_request: Dict[int, Dict[str, str]] = {}
user_pending_photo_offer: Dict[int, bool] = {}
user_last_favorite_photo: Dict[int, str] = {}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_photo_list() -> List[str]:
    if not os.path.exists(PHOTO_FOLDER):
        os.makedirs(PHOTO_FOLDER, exist_ok=True)
        return []
    return [os.path.join(PHOTO_FOLDER, f) for f in os.listdir(PHOTO_FOLDER) if f.lower().endswith(SUPPORTED_EXTENSIONS)]

def get_keywords_from_photo_name(photo_path: str) -> str:
    name = os.path.basename(photo_path).lower()
    return os.path.splitext(name)[0]

def search_category_by_query(query: str) -> Optional[str]:
    q = query.lower()
    for cat, words in KEYWORD_MAP.items():
        for w in words:
            if w in q:
                return cat
    return None

def get_photos_by_category(category: str) -> List[str]:
    all_photos = get_photo_list()
    if not all_photos: return []
    if category not in KEYWORD_MAP: return []
    syns = KEYWORD_MAP[category]
    return [p for p in all_photos if any(s in get_keywords_from_photo_name(p) for s in syns)]

def select_thematic_photo(user_id: int, category: str) -> Optional[str]:
    all_thematic = get_photos_by_category(category)
    if not all_thematic: return None
    if user_id not in user_thematic_history: user_thematic_history[user_id] = {}
    if category not in user_thematic_history[user_id]: user_thematic_history[user_id][category] = set()
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
        if os.path.getsize(image_path) > MAX_BASE64_SIZE:
            return "Файл слишком большой, попробуй сжать изображение."
        with open(image_path, "rb") as f: img_b64 = base64.b64encode(f.read()).decode()
        mime = "image/jpeg"
        if image_path.lower().endswith('.png'): mime = "image/png"
        elif image_path.lower().endswith('.gif'): mime = "image/gif"
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
            ]}],
            temperature=0.7, max_tokens=400, timeout=15
        )
        desc = resp.choices[0].message.content.strip()
        if lang == 'ru':
            desc = clean_english_words(desc)
            desc = remove_non_russian(desc)
            desc = distribute_emojis(desc)
        return desc
    except Exception as e:
        print(f"Ошибка vision: {e}")
        return "Ой, что-то пошло не так при анализе фото. Попробуй ещё раз 😅"

def analyze_user_photo(message, bot, client, lang: str) -> bool:
    try:
        if not message.photo:
            bot.send_message(message.chat.id, "Пожалуйста, отправь фото как изображение, а не как файл 😊")
            return False
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        tmp = f"temp_user_{message.from_user.id}_{int(time.time())}.jpg"
        with open(tmp, 'wb') as f: f.write(downloaded)
        prompt = "Ты Алёна, добрая, весёлая, обаятельная девушка. Опиши это фото коротко (2-3 предложения). Будь тёплой, добавь эмодзи. Не начинай ответ с 'Привет'."
        desc = analyze_photo_with_vision(tmp, prompt, client, lang)
        os.remove(tmp)
        user_last_user_image_desc[message.from_user.id] = desc
        bot.send_message(message.chat.id, desc)
        return True
    except Exception as e:
        print(f"Ошибка обработки фото пользователя: {e}")
        bot.send_message(message.chat.id, "Что-то не так с фото, может, попробуешь другое? 😊")
        return False

def try_paris_photo(uid, txt, lang, bot, msg, client, add_msg, save_hist, save_photo_func):
    if 'мосту' not in txt.lower(): return False
    if not re.search(r'(фото|фотки|фотографии)', txt): return False
    all_photos = get_photo_list()
    paris = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p) and 'париж' in get_keywords_from_photo_name(p)]
    if not paris: paris = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p)]
    if not paris: return False
    user_last_category[uid] = 'париж'
    if uid in user_thematic_history and 'париж' in user_thematic_history[uid]:
        shown = user_thematic_history[uid]['париж']
        available = [p for p in paris if p not in shown]
        chosen = random.choice(available) if available else None
        if not chosen:
            shown.clear()
            chosen = random.choice(paris)
    else:
        chosen = random.choice(paris)
    user_thematic_history.setdefault(uid, {}).setdefault('париж', set()).add(chosen)
    user_last_sent_photo[uid] = chosen
    save_photo_func(uid, chosen)
    try:
        prompt = "Начни свой ответ с душевного восклицания, например: 'Конечно, у меня есть такие фото!' или 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
        desc = analyze_photo_with_vision(chosen, prompt, client, lang)
        if desc.startswith('Привет'): desc = re.sub(r'^Привет[,!\s]*', '', desc)
        desc = distribute_emojis(desc)
        with open(chosen, 'rb') as ph: bot.send_photo(msg.chat.id, ph, caption=desc)
        add_msg(uid, 'user', txt)
        add_msg(uid, 'assistant', desc)
        save_hist()
        return True
    except Exception as e:
        print(f"Ошибка отправки фото моста: {e}")
        bot.send_message(msg.chat.id, "Ой, не могу показать фото моста, попробуй ещё раз 😅")
        return True

def handle_favorite_photo_repeat(uid, lang, bot, msg):
    if uid in user_last_favorite_photo:
        path = user_last_favorite_photo[uid]
        try:
            bot.send_message(msg.chat.id, distribute_emojis("Я тебе уже показывала своё любимое фото, но если хочешь, покажу его ещё раз! 😊"))
            with open(path, 'rb') as ph: bot.send_photo(msg.chat.id, ph)
            return True
        except Exception as e:
            print(f"Ошибка повтора любимого фото: {e}")
    return False

# --- ГЛАВНАЯ ФУНКЦИЯ ---
def handle_photo_request(uid, txt, lang, bot, msg, client,
                         add_msg, save_hist, save_photo_func,
                         save_fav_photo_func, user_has_no_photos=False):
    # Париж
    if try_paris_photo(uid, txt, lang, bot, msg, client, add_msg, save_hist, save_photo_func):
        user_pending_photo_offer[uid] = False
        return True

    # "ещё такие же"
    if uid in user_last_category and user_last_category[uid] is not None and \
       re.search(r'(еще такие фото|еще такие фотки|такие же фото|такие же фотки|похожие фото|похожие фотки|аналогичные фото|аналогичные фотки|другие фото|другое фото|ещё такие|еще такие|еще такое фото|ещё такое фото|такое же фото|ещё такие фотки)', txt, re.IGNORECASE):
        user_pending_photo_offer[uid] = False
        cat = user_last_category[uid]
        if cat == 'париж':
            all_photos = get_photo_list()
            paris = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p) and 'париж' in get_keywords_from_photo_name(p)]
            if not paris: paris = [p for p in all_photos if 'мост' in get_keywords_from_photo_name(p)]
            if paris:
                if uid in user_thematic_history and cat in user_thematic_history[uid]:
                    shown = user_thematic_history[uid][cat]
                    available = [p for p in paris if p not in shown]
                else:
                    available = paris
                if available:
                    chosen = random.choice(available)
                    user_thematic_history[uid].setdefault(cat, set()).add(chosen)
                else:
                    try: bot.send_message(msg.chat.id, "У меня пока только это фото на тему «Париж». Хочешь, покажу что-нибудь из другого альбома? 😊")
                    except: pass
                    return True
            else:
                try: bot.send_message(msg.chat.id, "Ой, не могу найти парижские фото, попробуй ещё раз 😅")
                except: pass
                return True
        else:
            chosen = select_thematic_photo(uid, cat)
            if not chosen:
                try: bot.send_message(msg.chat.id, f"У меня пока только это фото на тему «{cat}». Хочешь, покажу что-нибудь из другого альбома? 😊")
                except: pass
                return True
        if chosen:
            user_last_sent_photo[uid] = chosen
            save_photo_func(uid, chosen)
            try:
                prompt = "Начни свой ответ с душевного восклицания, например: 'Конечно, у меня есть такие фото!' или 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                desc = analyze_photo_with_vision(chosen, prompt, client, lang)
                if desc.startswith('Привет'): desc = re.sub(r'^Привет[,!\s]*', '', desc)
                desc = distribute_emojis(desc)
                with open(chosen, 'rb') as ph: bot.send_photo(msg.chat.id, ph, caption=desc)
                add_msg(uid, 'user', txt)
                add_msg(uid, 'assistant', desc)
                save_hist()
            except Exception as e:
                print(f"Ошибка отправки ещё одного фото: {e}")
                try: bot.send_message(msg.chat.id, "Ой, не могу показать другое фото, попробуй ещё раз 😅")
                except: pass
        return True

    # Основной показ – расширенный список фраз
    if re.search(r'(фотки|какие нибудь фото|а у тебя есть фотографии|есть фотографии|у тебя есть фото|покажи свои фото|покажи фото|покажи мне фото|покажи мне фотки|покажешь фото|покажешь мне фото|фотоальбом|покажи себя|своё фото|свое фото|мои фото|свои фотографии|покажи альбом|покажи где ты была|покажи, где ты|покажи картинку|покажи изображение|есть фото|есть ли у тебя фото|посмотреть твои фото|покажи свои фотографии|любимые фото|любимое фото|любимых фото|есть еще фото|другие фото|покажи другое фото|ещё фото|какое твое любимое фото|покажи любимое фото|покажи другое|такие фото|такие фотки|фото где ты|фотки где ты|какие фото у тебя еще есть|какие фото ещё есть|какие у тебя ещё фото|какие ещё фото|какие фото еще|какие еще фото|какие у тебя есть фото|какие фото у тебя есть|какие фото есть|есть ещё фото|есть еще фотки|ещё фотки есть|какие фотки|покажешь фотки|твои фото|твои фотки)', txt, re.IGNORECASE):
        user_pending_photo_offer[uid] = False

        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', txt):
            if handle_favorite_photo_repeat(uid, lang, bot, msg):
                add_msg(uid, 'user', txt)
                save_hist()
                return True

        all_photos = get_photo_list()
        if not all_photos:
            msg_text = "У меня ещё нет фотоальбома, но Максик обещал скоро добавить! 😊" if lang=='ru' else "I don't have a photo album yet, but Max promised to add it soon! 😊"
            try: bot.send_message(msg.chat.id, msg_text)
            except: pass
            return True

        compliment = bool(re.search(r'(красавица|красивая|умница|прекрасна|великолепна|шикарна|обалденная|потрясающая|чудесная|восхитительная|симпатичная|милашка|хорошенькая|обворожительная|божественно|как красиво|какая ты красивая|какая ты классная|какая ты хорошая)', txt, re.IGNORECASE))

        # Любимое фото (первый показ)
        if re.search(r'(любимые фото|любимое фото|любимых фото|какое твое любимое фото|покажи любимое фото)', txt):
            chosen = random.choice(all_photos)
            user_last_sent_photo[uid] = chosen
            save_photo_func(uid, chosen)
            user_last_favorite_photo[uid] = chosen
            save_fav_photo_func()

            for attempt in range(3):
                try:
                    prompt = ""
                    if compliment: prompt += "Ты ДОЛЖНА сначала поблагодарить пользователя за комплимент (например, 'Спасибо, мне очень приятно! 😊'), а затем уже описывай фото. "
                    prompt += "Начни свой ответ с тёплой фразы, например: 'Вот моё любимое фото...' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                    desc = analyze_photo_with_vision(chosen, prompt, client, lang)
                    if desc.startswith('Привет'): desc = re.sub(r'^Привет[,!\s]*', '', desc)
                    if user_has_no_photos:
                        desc += "\n\nКак жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой."
                    desc = distribute_emojis(desc)
                    with open(chosen, 'rb') as ph: bot.send_photo(msg.chat.id, ph, caption=desc)
                    sent = True
                    break
                except Exception as e:
                    print(f"Ошибка любимого (попытка {attempt+1}): {e}")
                    if attempt == 2:
                        try:
                            with open(chosen, 'rb') as ph:
                                bot.send_photo(msg.chat.id, ph, caption="Вот моё любимое фото, просто посмотри, какое оно душевное ✨")
                        except:
                            try: bot.send_message(msg.chat.id, "Не могу отправить фото, что-то не так 😅")
                            except: pass
            else:
                try: bot.send_message(msg.chat.id, "Не могу отправить фото, что-то не так 😅")
                except: pass
            add_msg(uid, 'user', txt)
            save_hist()
            return True

        # Остальные запросы
        category = search_category_by_query(txt)
        if category:
            user_last_category[uid] = category
            chosen = select_thematic_photo(uid, category) or random.choice(all_photos)
            apology = "" if chosen else "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
        else:
            if re.search(r'(еще такие|такие же|похожие|аналогичные|ещё такие)', txt):
                last_photo = user_last_sent_photo.get(uid)
                if last_photo:
                    pname = get_keywords_from_photo_name(last_photo)
                    for cat, words in KEYWORD_MAP.items():
                        if any(s in pname for s in words):
                            user_last_category[uid] = cat
                            chosen = select_thematic_photo(uid, cat)
                            break
                    else:
                        chosen = random.choice(all_photos)
                else:
                    chosen = random.choice(all_photos)
                apology = "" if chosen else "Ой, у меня пока нет фото на эту тему, но вот одно из моих любимых – надеюсь, тебе понравится! "
            else:
                chosen = random.choice(all_photos)
                pname = get_keywords_from_photo_name(chosen)
                for cat, words in KEYWORD_MAP.items():
                    if any(s in pname for s in words):
                        user_last_category[uid] = cat
                        user_thematic_history.setdefault(uid, {}).setdefault(cat, set()).add(chosen)
                        break
                else:
                    user_last_category[uid] = None
                apology = ""

        user_last_sent_photo[uid] = chosen
        save_photo_func(uid, chosen)

        for attempt in range(3):
            try:
                prompt = ""
                if compliment: prompt += "Ты ДОЛЖНА сначала поблагодарить пользователя за комплимент (например, 'Спасибо, мне очень приятно! 😊'), а затем уже описывай фото. "
                prompt += apology + "Начни свой ответ с душевного восклицания, например: 'Конечно, у меня есть такие фото!' или 'С удовольствием покажу!' Затем опиши фото: что ты на нём делаешь, где ты, какое у тебя настроение. Расскажи короткую историю. Обязательно добавь 2-3 эмодзи, чтобы описание было живым. Не начинай ответ с 'Привет'."
                desc = analyze_photo_with_vision(chosen, prompt, client, lang)
                if desc.startswith('Привет'): desc = re.sub(r'^Привет[,!\s]*', '', desc)
                if not category and not re.search(r'(такие|таких|похожие|аналогичные)', txt):
                    desc += "\n\nКстати, у меня много разных фотографий! Есть где я на пляже, в горах или на природе... Какие именно тебя интересуют? 😊"
                if user_has_no_photos:
                    desc += "\n\nКак жаль, а я бы с удовольствием посмотрела на тебя! 😊 Но ничего страшного, мне и так хорошо с тобой."
                desc = distribute_emojis(desc)
                with open(chosen, 'rb') as ph: bot.send_photo(msg.chat.id, ph, caption=desc)
                break
            except Exception as e:
                print(f"Ошибка отправки (попытка {attempt+1}): {e}")
                if attempt == 2:
                    try:
                        with open(chosen, 'rb') as ph:
                            bot.send_photo(msg.chat.id, ph, caption="Вот ещё одно моё фото, просто посмотри, какое оно душевное ✨")
                    except:
                        try: bot.send_message(msg.chat.id, "Не могу отправить фото, что-то не так 😅")
                        except: pass
        add_msg(uid, 'user', txt)
        save_hist()
        return True

    return False
