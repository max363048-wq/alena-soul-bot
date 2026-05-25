import os
import telebot
from openai import OpenAI

# Получаем токены из Railway Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверка
if not BOT_TOKEN:
    raise ValueError("Нет BOT_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("Нет OPENAI_API_KEY")

# Telegram bot
bot = telebot.TeleBot(BOT_TOKEN)

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

print("Бот запущен...")

# Обработка сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_text = message.text

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты милая, добрая и немного флиртующая девушка по имени Алена."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        reply = response.choices[0].message.content

        bot.reply_to(message, reply)

    except Exception as e:
        print("ERROR:", e)
        bot.reply_to(message, f"Ошибка: {e}")

# Запуск
bot.infinity_polling(skip_pending=True)
