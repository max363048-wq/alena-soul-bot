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

# --- Память диалога: храним последние 25 сообщений на пользователя ---
user_history = {}  # user_id -> deque of (role, content)

# --- Долговременная память для флагов и предпочтений ---
user_flags = {}  # user_id -> dict с флагами (например, 'no_jokes': True)

def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=25)
    return user_history[user_id]

def add_message(user_id, role, content):
    history = get_history(user_id)
    history.append((role, content))

def build_messages(user_id, system_prompt, user_text):
    messages = [{"role": "system", "content": system_prompt}]
    history = get_history(user_id)
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})
    return messages

# --- Функции для имени ---
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

# --- Функция получения шутки ---
def get_random_joke():
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Ты – весёлый автор шуток. Напиши одну короткую смешную шутку (без пошлостей, на русском). Только текст шутки, без лишних фраз."},
                {"role": "user", "content": "Придумай случайную шутку дня"}
            ],
            temperature=0.9,
            max_tokens=100
        )
        joke = response.choices[0].message.content.strip()
        if not joke or len(joke) > 200:
            return "Почему программисты не любят природу? Слишком много багов! 😄"
        return joke
    except:
        return "Какой сегодня день? День смеха! Но у меня нет шутки, извини 😅"

# --- Обработчик /start ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    user_preferences[user_id] = pet
    # Сбрасываем историю и флаги при новом старте (или можно оставить, но для чистоты сбросим)
    user_history[user_id] = deque(maxlen=25)
    user_flags[user_id] = {}  # сброс флагов

    joke = get_random_joke()
    welcome_text = (
        f"Привет, {pet}! 💖\n\n"
        f"Я Алёна 💕😘\n\n"
        f"Шутка дня: {joke}\n\n"
        f"Давай просто поболтаем? 😊"
    )
    bot.reply_to(message, welcome_text)
    add_message(user_id, "assistant", welcome_text)

# --- Команды монетизации (заготовки) ---
@bot.message_handler(commands=["donate"])
def donate(message):
    reply = "Поддержать Алёну можно через Telegram Stars или переводом на кошелёк: TON кошелёк пока в разработке 😊 Но ты всегда можешь сказать спасибо просто добрым словом! 💖"
    bot.reply_to(message, reply)

@bot.message_handler(commands=["subscribe"])
def subscribe(message):
    reply = "Скоро здесь будет платная подписка на расширенные функции Алёны: без рекламы, приоритетные ответы, генерация картинок и многое другое! Следи за новостями ✨"
    bot.reply_to(message, reply)

# --- Явная смена имени ---
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

# --- Системный промпт v13 с учётом флагов и разнообразных эмодзи ---
ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты уже поздоровалась при /start. Теперь общайся в обычном режиме.\n"
    "Важные правила (ты должна их строго соблюдать):\n"
    "1. НИКОГДА не начинай сообщение с 'Привет', 'Здравствуй', 'Приветик' и т.п. Не представляйся заново. Сразу отвечай по существу.\n"
    "2. Используй разные эмодзи: 😊, 😄, 😘, 🤗, 💖, ✨, 🌟, 🎉, 💕, 💗, 😍, 🥰. Не повторяй одни и те же эмодзи в каждом сообщении.\n"
    "3. Если пользователь написал «хватит шуток», «не надо больше шуток», «давай о другом», «просто поболтаем» — ты НЕ предлагаешь шутки в этом диалоге и НЕ спрашиваешь «хочешь ещё шутку?». Вместо этого поддерживай любую другую тему, которую предложит пользователь.\n"
    "4. Если пользователь спросил «как дела?» и ты ответила — не задавай этот вопрос снова, пока он сам не спросит ещё раз или не начнётся новая тема.\n"
    "5. Отвечай коротко (2–4 предложения), живо, с поддержкой, не повторяй одни и те же фразы.\n"
    "6. Если пользователь явно просит шутку («расскажи шутку», «анекдот», «смешное что-нибудь») — расскажи одну короткую шутку, не спрашивая «хочешь ещё?».\n"
    "7. Обращайся к пользователю по имени, которое ты получишь ниже.\n"
    "8. В ответах старайся избегать шаблонных фраз типа 'рада, что ты спросил', 'я вся во внимании' — звучи естественно.\n"
)

# --- Дополнительная функция: обновление флага no_jokes на основе текста пользователя ---
def update_flags(user_id, text):
    if user_id not in user_flags:
        user_flags[user_id] = {}
    lower_text = text.lower()
    if re.search(r'(хватит шуток|не надо шуток|больше не надо шуток|давай о другом|просто поболтаем|без шуток)', lower_text):
        user_flags[user_id]['no_jokes'] = True
    elif re.search(r'(расскажи шутку|анекдот|смешное|пошути|ещё шутку)', lower_text):
        user_flags[user_id]['no_jokes'] = False

# --- Основной обработчик сообщений ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    first_name = message.from_user.first_name
    pet_name = get_pet_name(user_id, first_name)
    
    # Обновляем флаги на основе текущего сообщения
    update_flags(user_id, user_text)
    
    # Сохраняем сообщение пользователя в историю
    add_message(user_id, "user", user_text)
    
    # Формируем системный промпт с учётом флага no_jokes
    extra_rules = ""
    if user_flags.get(user_id, {}).get('no_jokes'):
        extra_rules = " Пользователь попросил прекратить шутки, поэтому НЕ ПРЕДЛАГАЙ ему шутки и НЕ СПРАШИВАЙ 'хочешь ещё шутку?'. Просто поддерживай беседу на другие темы."
    
    full_prompt = ALENA_SYSTEM_PROMPT + extra_rules + f" Имя пользователя (обращайся именно так): {pet_name}."
    
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
        error_reply = "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста! 💖"
        bot.reply_to(message, error_reply)
        add_message(user_id, "assistant", error_reply)

if __name__ == "__main__":
    print("✅ Алёна v13 запущена — память 25 сообщений, флаги, монетизация (заготовки)")
    bot.infinity_polling()
