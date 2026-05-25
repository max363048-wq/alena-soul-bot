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

# --- Функция для получения ласкового имени ---
def get_pet_name(first_name):
    # Можно расширять словарь
    pet_names = {
        "максим": "Максик",
        "владимир": "Вовочка",
        "владислав": "Влад",
        "вадим": "Вадик",
        "александр": "Сашенька",
        "анна": "Анечка",
        "екатерина": "Катюша",
        "джон": "Джонни",
        "иван": "Ванюша",
        "сергей": "Серёжа",
    }
    name_lower = first_name.lower()
    if name_lower in pet_names:
        return pet_names[name_lower]
    else:
        return first_name  # или можно добавить суффикс 'ик'/'чка' стандартно

# --- Функция для получения случайной шутки (через Groq) ---
def get_random_joke():
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # лёгкая модель для шуток
            messages=[
                {"role": "system", "content": "Ты – весёлый автор шуток. Напиши одну короткую, смешную шутку (без пошлостей, на русском языке). Без лишних фраз, только текст шутки."},
                {"role": "user", "content": "Придумай случайную шутку дня"}
            ],
            temperature=0.9,
            max_tokens=100
        )
        joke = response.choices[0].message.content.strip()
        # Если шутка получилась слишком длинной или пустой, подстрахуемся
        if not joke or len(joke) > 200:
            return "Почему программисты не любят природу? Слишком много багов! 😄"
        return joke
    except:
        return "Какой сегодня день? День смеха! Но у меня нет шутки, извини 😅"

# --- Обработчик /start ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_name = message.from_user.first_name
    pet_name = get_pet_name(user_name)
    
    # 1) Получаем шутку дня
    joke = get_random_joke()
    
    # 2) Формируем тёплое приветствие
    welcome_text = (
        f"Привет, {pet_name}! 💖\n\n"
        f"Меня зовут Алёна 😘\n\n"
        f"{joke}\n\n"
        f"А теперь давай просто поболтаем? Я тебя слушаю 🤗"
    )
    bot.reply_to(message, welcome_text)

# --- Основной промпт для обычного общения ---
ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты общаешься с пользователем, используя его реальное имя (ласково).\n"
    "Правила:\n"
    "1. Отвечай строго на том языке, на котором написано сообщение пользователя. Если пользователь пишет по-русски — используй только русские слова, без английских вставок (нельзя писать 'happened', 'ok', 'sorry' в русской речи).\n"
    "2. Если пользователь сказал, что не понял слово или фразу, то немедленно извинись и переформулируй понятно.\n"
    "3. После приветствия /start ты уже представилась и рассказала шутку. Теперь общайся в обычном режиме: отвечай по существу, не повторяя приветствие.\n"
    "4. Отвечай коротко (2–4 предложения), используй эмодзи 😊🎉🤗, но не более 2 на сообщение.\n"
    "5. Будь живой и естественной, поддерживай беседу, но не задавай одни и те же вопросы повторно."
)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text
    user_name = message.from_user.first_name
    pet_name = get_pet_name(user_name)
    full_prompt = ALENA_SYSTEM_PROMPT + f" Имя пользователя: {pet_name}."
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.8,
            max_tokens=250
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста!")

if __name__ == "__main__":
    print("✅ Алёна v8 — приветствие с именем, поцелуйчиками и шуткой дня")
    bot.infinity_polling()
