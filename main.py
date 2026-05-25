import os
import telebot
import random
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Словарь для хранения предпочтений пользователя (ласковое имя)
user_preferences = {}

def default_pet_name(first_name):
    # стандартные ласковые имена
    names = {
        "максим": "Максик",
        "владимир": "Вовочка",
        "вадим": "Вадик",
        "александр": "Сашенька",
        "анна": "Анечка",
        "екатерина": "Катюша",
        "джон": "Джонни",
        "иван": "Ванюша",
        "сергей": "Серёжа",
        "михаил": "Миша",
        "дмитрий": "Дима"
    }
    name_lower = first_name.lower()
    return names.get(name_lower, first_name)

def get_pet_name(user_id, first_name):
    if user_id in user_preferences:
        return user_preferences[user_id]
    else:
        return default_pet_name(first_name)

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

@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    pet = default_pet_name(first_name)
    # Сохраняем пока стандартное обращение
    user_preferences[user_id] = pet
    
    joke = get_random_joke()
    
    welcome_text = (
        f"Привет, {pet}! 💖😘\n\n"
        f"Меня зовут Алёна 💕😘\n\n"
        f"Шутка дня: {joke}\n\n"
        f"А теперь давай просто поболтаем? 😊\n\n"
        f"Кстати, тебе нравится, когда я называю тебя «{pet}»? Если хочешь другое ласковое имя — напиши мне, например: «Зови меня Котёнок» или «Можно просто Лёша». Я запомню 🤗"
    )
    bot.reply_to(message, welcome_text)

# Обработчик для смены имени (если пользователь пишет "зовут меня ..." или "называй меня ...")
@bot.message_handler(func=lambda message: message.text and ('зовут меня' in message.text.lower() or 'называй меня' in message.text.lower() or 'обращайся ко мне' in message.text.lower()))
def change_name(message):
    user_id = message.from_user.id
    text = message.text
    # Извлекаем новое имя: берём всё после фразы
    import re
    match = re.search(r'(?:зовут меня|называй меня|обращайся ко мне)\s*(.+?)(?:\.|$)', text, re.IGNORECASE)
    if match:
        new_name = match.group(1).strip()
        if new_name:
            user_preferences[user_id] = new_name
            bot.reply_to(message, f"Ой, как здорово! Теперь буду называть тебя «{new_name}» 💖😘 Запомнила! А теперь давай болтать дальше 🤗")
            return
    bot.reply_to(message, "Напиши, как ты хочешь, чтобы я к тебе обращалась, например: «Зови меня Максик» или «Можно просто Друг». Я запомню 😊")

# Основной промпт — без повторных приветствий
ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты уже поздоровалась с пользователем при команде /start и спросила, как к нему обращаться. Теперь ты общаешься в обычном режиме.\n"
    "Правила:\n"
    "1. Никогда не начинай сообщение с 'Привет', 'Здравствуй', 'Приветик' и т.п. Не представляйся заново. Сразу отвечай по существу.\n"
    "2. Используй 2-3 эмодзи на сообщение (например 💖, 😊, 🎉, 🤗, 😘, 💕). Делай ответ живым и тёплым.\n"
    "3. Отвечай строго на том языке, на котором написал пользователь. Если по-русски — без английских вставок (никаких 'ok', 'sorry', 'happened').\n"
    "4. Если пользователь сказал, что не понял слово или фразу — извинись и переформулируй понятно.\n"
    "5. Не задавай один и тот же вопрос (например, 'как дела') чаще одного раза за несколько сообщений.\n"
    "6. Отвечай коротко (2–4 предложения), будь живой, поддерживай беседу, шути, если уместно.\n"
    "7. Обращайся к пользователю по имени, которое он выбрал (ты получишь его в начале сообщения).\n\n"
    "Запомни: ты — не бот, а подружка. Будь естественной и милой."
)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    first_name = message.from_user.first_name
    pet_name = get_pet_name(user_id, first_name)
    
    full_prompt = ALENA_SYSTEM_PROMPT + f" Имя пользователя (обращайся именно так): {pet_name}."
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.85,
            max_tokens=250
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста! 💖")

if __name__ == "__main__":
    print("✅ Алёна v9 — ласковое имя с выбором, без повторных приветствий, много эмодзи")
    bot.infinity_polling()
