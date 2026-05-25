import os
import telebot
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

client = OpenAI(
    api_key=OPENAI_API_KEY
)

print("Бот запущен...")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
Ты милая девушка по имени Алена.

Пользователь: {message.text}
"""
        )

        reply = response.output_text

        bot.reply_to(message, reply)

    except Exception as e:
        print("ERROR:", e)
        bot.reply_to(message, f"Ошибка: {e}")

bot.infinity_polling()
