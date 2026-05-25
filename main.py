import os
import telebot
import re
from openai import OpenAI
from collections import deque

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# --- Память ---
user_history = {}
user_no_jokes = {}
user_preferences = {}

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=25)
    return user_history[user_id]

def add_message(user_id, role, content):
    get_history(user_id).append((role, content))

def build_messages(user_id, system_prompt, user_text):
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in get_history(user_id):
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    return messages

# --- Определение языка (очень простое) ---
def is_russian(text):
    return bool(re.search('[а-яА-Я]', text))

# --- Чистка английских слов ТОЛЬКО для русских ответов ---
def clean_russian_english(text: str) -> str:
    if not is_russian(text):
        return text  # не трогаем не русские ответы
    replacements = {
        r'\bbirds\b': 'птички', r'\bhappened\b': 'случилось',
        r'\bok\b': 'хорошо', r'\bsorry\b': 'извини',
        r'\bplease\b': 'пожалуйста', r'\bhello\b': 'привет',
        r'\bhi\b': 'привет', r'\bthanks\b': 'спасибо',
        r'\bthank you\b': 'спасибо', r'\bby the way\b': 'кстати',
        r'\bso\b': 'так что', r'\bbut\b': 'но',
        r'\band\b': 'и', r'\bfor\b': 'для',
        r'\bwith\b': 'с', r'\bheard\b': 'услышал',
        r'\bhear\b': 'слышать', r'\bon the house\b': 'бесплатно',
        r'\bdrinks are on the house\b': 'напитки бесплатно',
        r'\bcool\b': 'круто', r'\bwow\b': 'ого',
        r'\byes\b': 'да', r'\bno\b': 'нет',
    }
    for eng, rus in replacements.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    return text

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

# --- Шутка дня (на любом языке, но чистая) ---
def get_random_joke(user_lang='ru'):
    # Если пользователь пишет на английском, шутка будет на английском
    lang_prompt = "на русском языке" if user_lang == 'ru' else "in English"
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"Ты автор шуток. Напиши одну короткую смешную шутку {lang_prompt}, без смешивания с другими языками. Только текст шутки."},
                {"role": "user", "content": "Придумай случайную шутку дня"}
            ],
            temperature=0.9,
            max_tokens=100
        )
        joke = response.choices[0].message.content.strip()
        if not joke or len(joke) > 200:
            if user_lang == 'ru':
                return "Почему программисты не любят природу? Слишком много багов! 😄"
            else:
                return "Why don't programmers like nature? Too many bugs! 😄"
        if user_lang == 'ru':
            return clean_russian_english(joke)
        return joke
    except:
        if user_lang == 'ru':
            return "Какой сегодня день? День смеха! Но у меня нет шутки, извини 😅"
        else:
            return "What day is it? April Fools! But I have no joke, sorry 😅"

# --- /start ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    user_history[user_id] = deque(maxlen=25)
    user_no_jokes[user_id] = False

    user_text = message.text
    lang = 'ru' if is_russian(user_text) else 'en'  # по умолчанию определяем по /start
    joke = get_random_joke(lang)

    welcome_text = (
        f"Привет, {pet}! 💖\n\n"
        f"Я Алёна 💕😘\n\n"
        f"Шутка дня: {joke}\n\n"
        f"Знакомься: я умею поддерживать разговор на любые темы, рассказывать шутки, давать советы, мотивировать и даже составлять гороскоп ✨ Просто спроси — и я рядом.\n\n"
        f"Расскажи, как твои дела? 😊"
    )
    if lang == 'en':
        welcome_text = f"Hi, {pet}! 💖\n\nI'm Alena 💕😘\n\nJoke of the day: {joke}\n\nI can chat on any topic, tell jokes, give advice, motivate, and even make horoscopes ✨ Just ask — I'm here.\n\nSo, how are you? 😊"
    
    bot.reply_to(message, welcome_text)
    add_message(user_id, "assistant", welcome_text)

# --- Смена имени ---
@bot.message_handler(func=lambda message: message.text and re.match(r'^(зовут меня|называй меня|обращайся ко мне|call me|name me)\s+', message.text.lower()))
def change_name(message):
    user_id = message.from_user.id
    text = message.text
    match = re.match(r'(?:зовут меня|называй меня|обращайся ко мне|call me|name me)\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if match:
        new_name = match.group(1).strip()
        if new_name:
            user_preferences[user_id] = new_name
            reply = f"Запомнила! Теперь буду называть тебя «{new_name}» 💖😘" if is_russian(text) else f"Got it! Now I'll call you {new_name} 💖😘"
            bot.reply_to(message, reply)
            add_message(user_id, "assistant", reply)
            return
    reply = "Напиши, как тебя называть, например: «Зови меня Друг» 😊" if is_russian(text) else "Tell me what to call you, e.g. 'Call me Friend' 😊"
    bot.reply_to(message, reply)
    add_message(user_id, "assistant", reply)

# --- Системный промпт (мультиязычный, без смешивания) ---
ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты уже поздоровалась при /start.\n"
    "ПРАВИЛА:\n"
    "1. ОПРЕДЕЛИ ЯЗЫК сообщения пользователя. ОТВЕЧАЙ СТРОГО НА ТОМ ЖЕ ЯЗЫКЕ.\n"
    "2. НИКОГДА НЕ СМЕШИВАЙ ЯЗЫКИ в одном ответе (нельзя писать английские слова в русском ответе и наоборот).\n"
    "3. Не начинай ответ с 'Привет'/'Hello' после /start. Не представляйся заново.\n"
    "4. Используй эмодзи в меру, разные.\n"
    "5. Если просят шутку — расскажи ОДНУ короткую шутку на том же языке, без вопросов 'хочешь ещё?'.\n"
    "6. Если сказали 'хватит шуток' — не предлагай шутки.\n"
    "7. Отвечай коротко (2–4 предложения), будь живой и естественной.\n"
    "8. Обращайся к пользователю по имени (ласково).\n"
)

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    first_name = message.from_user.first_name
    pet_name = get_pet_name(user_id, first_name)
    lang = 'ru' if is_russian(user_text) else 'en'  # можно расширить до других языков

    if re.search(r'(хватит шуток|не надо шуток|давай о другом|enough jokes|no more jokes)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True

    add_message(user_id, "user", user_text)

    no_jokes_note = ""
    if user_no_jokes.get(user_id, False):
        no_jokes_note = " Пользователь сказал, что ему хватит шуток. НИКОГДА не предлагай шутки."

    full_prompt = ALENA_SYSTEM_PROMPT + no_jokes_note + f" Имя пользователя (ласково): {pet_name}. Язык ответа: {'русский' if lang == 'ru' else 'английский'}."

    try:
        messages = build_messages(user_id, full_prompt, user_text)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.85,
            max_tokens=300
        )
        reply = response.choices[0].message.content.strip()
        # Чистим только русские ответы от английских вкраплений
        if lang == 'ru':
            reply = clean_russian_english(reply)
        bot.reply_to(message, reply)
        add_message(user_id, "assistant", reply)
    except Exception as e:
        print("Ошибка:", e)
        error_reply = "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста! 💖" if lang == 'ru' else "Oops, an error occurred 😅 Please write again! 💖"
        bot.reply_to(message, error_reply)
        add_message(user_id, "assistant", error_reply)

if __name__ == "__main__":
    print("✅ Алёна v16 — мультиязычная, без смешивания языков")
    bot.infinity_polling()
