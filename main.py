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
user_lang = {}  # язык пользователя: 'ru' или 'en'

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

# --- Шутка (на нужном языке) ---
def get_random_joke(lang='ru'):
    if lang == 'ru':
        prompt = "на русском языке, без английских слов"
        fallback = "Почему программисты не любят природу? Слишком много багов! 😄"
    else:
        prompt = "in English, without mixing languages"
        fallback = "Why don't programmers like nature? Too many bugs! 😄"
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"Ты автор шуток. Напиши одну короткую смешную шутку {prompt}. Только текст шутки."},
                {"role": "user", "content": "Придумай случайную шутку"}
            ],
            temperature=0.9,
            max_tokens=100
        )
        joke = response.choices[0].message.content.strip()
        if not joke or len(joke) > 200:
            return fallback
        return joke
    except:
        return fallback

# --- /start ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    user_history[user_id] = deque(maxlen=25)
    user_no_jokes[user_id] = False
    user_lang[user_id] = None  # язык ещё не выбран

    welcome_text = (
        f"Привет, {pet}! 💖\n\n"
        f"Я Алёна. 💕😘 Давай определимся, на каком языке нам общаться?😊\n"
        f"Напиши: **Русский** или **English**\n\n"
        f"Hi, {pet}! 💖\n\n"
        f"I'm Alena. 💕😘 Let's choose the language.😊\n"
        f"Type: **Russian** or **English**"
    )
    bot.reply_to(message, welcome_text)
    add_message(user_id, "assistant", welcome_text)

# --- Обработчик выбора языка ---
@bot.message_handler(func=lambda message: message.text and message.text.lower() in ['русский', 'russian', 'english', 'английский'])
def set_language(message):
    user_id = message.from_user.id
    text = message.text.lower()
    if text in ['русский', 'russian']:
        user_lang[user_id] = 'ru'
        lang_name = 'русский'
    else:
        user_lang[user_id] = 'en'
        lang_name = 'English'
    
    pet = get_pet_name(user_id, message.from_user.first_name)
    joke = get_random_joke(user_lang[user_id])
    
    if user_lang[user_id] == 'ru':
        reply = (
            f"Отлично, {pet}! Будем общаться по-русски 💖\n\n"
            f"Шутка дня: {joke}\n\n"
            f"Я умею поддерживать разговор, шутить, давать советы, мотивировать и составлять гороскоп ✨ Просто спроси.\n\n"
            f"Расскажи, как твои дела? 😊"
        )
    else:
        reply = (
            f"Great, {pet}! We'll speak English 💖\n\n"
            f"Joke of the day: {joke}\n\n"
            f"I can chat, tell jokes, give advice, motivate, and make horoscopes ✨ Just ask.\n\n"
            f"So, how are you? 😊"
        )
    bot.reply_to(message, reply)
    add_message(user_id, "assistant", reply)

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
            lang = user_lang.get(user_id, 'ru')
            reply = f"Запомнила! Теперь буду называть тебя «{new_name}» 💖😘" if lang == 'ru' else f"Got it! Now I'll call you {new_name} 💖😘"
            bot.reply_to(message, reply)
            add_message(user_id, "assistant", reply)
            return
    lang = user_lang.get(user_id, 'ru')
    reply = "Напиши, как тебя называть, например: «Зови меня Друг» 😊" if lang == 'ru' else "Tell me what to call you, e.g. 'Call me Friend' 😊"
    bot.reply_to(message, reply)
    add_message(user_id, "assistant", reply)

# --- Системный промпт (учитывает язык) ---
def get_system_prompt(lang):
    if lang == 'ru':
        return (
            "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты уже поздоровалась и выбрала язык.\n"
            "ПРАВИЛА:\n"
            "1. Отвечай строго на русском языке, без английских слов.\n"
            "2. Не начинай ответ с 'Привет', не представляйся заново.\n"
            "3. Используй разные эмодзи, не повторяйся.\n"
            "4. Если просят шутку — дай одну короткую шутку, не спрашивай 'хочешь ещё?'.\n"
            "5. Если сказали 'хватит шуток' — не предлагай шутки.\n"
            "6. Отвечай коротко (2-4 предложения).\n"
            "7. Обращайся по имени ласково.\n"
        )
    else:
        return (
            "You are Alena — a kind, cheerful, charming girl. You've already greeted and chosen the language.\n"
            "RULES:\n"
            "1. Answer strictly in English, no mixing with other languages.\n"
            "2. Don't start with 'Hello', don't introduce yourself again.\n"
            "3. Use different emojis, don't repeat.\n"
            "4. If asked for a joke — tell one short joke, don't ask 'want another?'.\n"
            "5. If user says 'enough jokes' — don't offer jokes.\n"
            "6. Answer briefly (2-4 sentences).\n"
            "7. Address the user by their name (kindly).\n"
        )

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    # Если язык ещё не выбран, не отвечаем (кроме команды /start и выбора языка)
    if user_id not in user_lang or user_lang[user_id] is None:
        # Пропускаем, но чтобы не молчать, можно напомнить
        bot.reply_to(message, "Пожалуйста, выбери язык: напиши 'Русский' или 'English'")
        return

    lang = user_lang[user_id]
    first_name = message.from_user.first_name
    pet_name = get_pet_name(user_id, first_name)

    if re.search(r'(хватит шуток|не надо шуток|давай о другом|enough jokes|no more jokes)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True

    add_message(user_id, "user", user_text)

    no_jokes_note = ""
    if user_no_jokes.get(user_id, False):
        no_jokes_note = " Пользователь сказал, что ему хватит шуток. НЕ ПРЕДЛАГАЙ ШУТКИ." if lang == 'ru' else " User said enough jokes. DO NOT OFFER JOKES."

    full_prompt = get_system_prompt(lang) + no_jokes_note + f" Имя пользователя (ласково): {pet_name}." if lang == 'ru' else get_system_prompt(lang) + no_jokes_note + f" User's name (kindly): {pet_name}."

    try:
        messages = build_messages(user_id, full_prompt, user_text)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.85,
            max_tokens=300
        )
        reply = response.choices[0].message.content.strip()
        bot.reply_to(message, reply)
        add_message(user_id, "assistant", reply)
    except Exception as e:
        print("Ошибка:", e)
        error_reply = "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста! 💖" if lang == 'ru' else "Oops, an error occurred 😅 Please write again! 💖"
        bot.reply_to(message, error_reply)
        add_message(user_id, "assistant", error_reply)

if __name__ == "__main__":
    print("✅ Алёна v17 — выбор языка при старте, без смешивания")
    bot.infinity_polling()
