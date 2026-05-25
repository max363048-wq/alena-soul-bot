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

# --- Память диалога (25 последних сообщений) ---
user_history = {}      # user_id: deque
user_no_jokes = {}     # user_id: bool (флаг "хватит шуток")
user_last_greeting = {} # user_id: bool (чтобы не здороваться повторно)

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=25)
    return user_history[user_id]

def add_message(user_id, role, content):
    hist = get_history(user_id)
    hist.append((role, content))

def build_messages(user_id, system_prompt, user_text):
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in get_history(user_id):
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    return messages

# --- Простая чистка английских слов (постобработка) ---
def clean_english_words(text: str) -> str:
    # Заменяем распространённые английские слова на русские аналоги или просто убираем
    replacements = {
        r'\bbirds\b': 'птички',
        r'\bhappened\b': 'случилось',
        r'\bok\b': 'хорошо',
        r'\bsorry\b': 'извини',
        r'\bplease\b': 'пожалуйста',
        r'\bhello\b': 'привет',
        r'\bhi\b': 'привет',
        r'\bthanks\b': 'спасибо',
        r'\bthank you\b': 'спасибо',
        r'\bby the way\b': 'кстати',
        r'\bso\b': 'так что',
        r'\bbut\b': 'но',
        r'\band\b': 'и',
        r'\bfor\b': 'для',
        r'\bwith\b': 'с',
    }
    for eng, rus in replacements.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    return text

# --- Ласковые имена ---
user_preferences = {}

def default_pet_name(first_name):
    names = {
        "максим": "Максик",
        "макс": "Максик",
        "владимир": "Вовочка",
        "вадим": "Вадик",
        "александр": "Сашенька",
        "анна": "Анечка",
        "екатерина": "Катюша",
        "джон": "Джонни",
        "иван": "Ванюша",
        "сергей": "Серёжа",
        "михаил": "Миша",
        "дмитрий": "Дима",
        "андрей": "Андрюша",
        "алексей": "Лёша",
        "олег": "Олежек",
    }
    name_lower = first_name.lower()
    return names.get(name_lower, first_name)

def get_pet_name(user_id, first_name):
    if user_id in user_preferences:
        return user_preferences[user_id]
    return default_pet_name(first_name)

# --- Шутка дня ---
def get_random_joke():
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Ты автор шуток. Напиши одну короткую смешную шутку на русском языке, без английских слов. Только текст шутки."},
                {"role": "user", "content": "Придумай случайную шутку дня"}
            ],
            temperature=0.9,
            max_tokens=100
        )
        joke = response.choices[0].message.content.strip()
        if not joke or len(joke) > 200:
            return "Почему программисты не любят природу? Слишком много багов! 😄"
        return clean_english_words(joke)  # на всякий случай чистим
    except:
        return "Какой сегодня день? День смеха! Но у меня нет шутки, извини 😅"

# --- /start ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    user_history[user_id] = deque(maxlen=25)
    user_no_jokes[user_id] = False
    user_last_greeting[user_id] = True
    
    joke = get_random_joke()
    welcome_text = (
        f"Привет, {pet}! 💖\n\n"
        f"Я Алёна 💕😘\n\n"
        f"Шутка дня: {joke}\n\n"
        f"О чем хочешь поболтать? 😊"
    )
    bot.reply_to(message, welcome_text)
    add_message(user_id, "assistant", welcome_text)

# --- Смена имени ---
@bot.message_handler(func=lambda message: message.text and re.match(r'^(зовут меня|называй меня|обращайся ко мне)\s+', message.text.lower()))
def change_name(message):
    user_id = message.from_user.id
    text = message.text
    match = re.match(r'(?:зовут меня|называй меня|обращайся ко мне)\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if match:
        new_name = match.group(1).strip()
        if new_name:
            user_preferences[user_id] = new_name
            reply = f"Запомнила! Теперь буду называть тебя «{new_name}» 💖😘"
            bot.reply_to(message, reply)
            add_message(user_id, "assistant", reply)
            return
    reply = "Напиши, как тебя называть, например: «Зови меня Друг» 😊"
    bot.reply_to(message, reply)
    add_message(user_id, "assistant", reply)

# --- Системный промпт с жёсткими правилами ---
ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты уже поздоровалась при /start. Теперь общайся в обычном режиме.\n"
    "ЖЁСТКИЕ ПРАВИЛА (ты должна их строго соблюдать):\n"
    "1. НИКОГДА не используй английские слова в русской речи. Запрещены: 'birds', 'happened', 'ok', 'sorry', 'please', 'hello', 'bye', 'yes', 'no', 'cool' и любые другие английские вставки. Только русский язык.\n"
    "2. НИКОГДА не начинай сообщение с 'Привет', 'Здравствуй', 'Приветик' и т.п. Не представляйся заново. Сразу отвечай по существу.\n"
    "3. Используй РАЗНЫЕ эмодзи: 😊, 😄, 😘, 🤗, 💖, ✨, 🌟, 🎉, 💕, 💗, 🥰, 😍. Не повторяй одни и те же эмодзи в каждом сообщении.\n"
    "4. Если пользователь написал «хватит шуток», «не надо больше шуток», «давай о другом», «просто поболтаем» — ты НЕ предлагаешь шутки в этом диалоге и НЕ спрашиваешь «хочешь ещё шутку?». Вместо этого поддерживай любую другую тему.\n"
    "5. Если пользователь спросил «как дела?» и ты ответила — не задавай этот вопрос снова в ближайших 5 сообщениях.\n"
    "6. Отвечай коротко (2–4 предложения), живо, с поддержкой, не повторяй одни и те же фразы.\n"
    "7. Если пользователь явно просит шутку («расскажи шутку», «анекдот») — расскажи одну короткую шутку, не спрашивая «хочешь ещё?».\n"
    "8. Обращайся к пользователю по имени, которое ты получишь ниже. Используй ласковую форму.\n"
)

# --- Основной обработчик ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    first_name = message.from_user.first_name
    pet_name = get_pet_name(user_id, first_name)
    
    # Проверяем, не просил ли пользователь прекратить шутки
    if re.search(r'(хватит шуток|не надо шуток|давай о другом|просто поболтаем)', user_text, re.IGNORECASE):
        user_no_jokes[user_id] = True
    
    # Добавляем сообщение пользователя в историю
    add_message(user_id, "user", user_text)
    
    # Формируем промпт с учётом флага no_jokes
    no_jokes_note = ""
    if user_no_jokes.get(user_id, False):
        no_jokes_note = " Пользователь сказал, что ему хватит шуток. НЕ ПРЕДЛАГАЙ ШУТКИ И НЕ СПРАШИВАЙ 'ХОЧЕШЬ ЕЩЁ?'. Общайся на другие темы."
    
    full_prompt = ALENA_SYSTEM_PROMPT + no_jokes_note + f" Имя пользователя (обращайся ласково): {pet_name}."
    
    try:
        messages = build_messages(user_id, full_prompt, user_text)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.85,
            max_tokens=300
        )
        reply = response.choices[0].message.content.strip()
        # Постобработка: удаляем возможные английские слова
        reply = clean_english_words(reply)
        bot.reply_to(message, reply)
        add_message(user_id, "assistant", reply)
    except Exception as e:
        print("Ошибка:", e)
        error_reply = "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста! 💖"
        bot.reply_to(message, error_reply)
        add_message(user_id, "assistant", error_reply)

if __name__ == "__main__":
    print("✅ Алёна v13 — память 25 сообщений, без английских слов, с запоминанием отказа от шуток")
    bot.infinity_polling()
