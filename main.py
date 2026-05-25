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


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "Привет))) Я Алена 💕"
    )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
Ты милая, добрая и романтичная девушка по имени Алена.
Общайся ласково и естественно.
"""
                },
                {
                    "role": "user",
                    "content": message.text
                }
            ],
            max_tokens=200
        )

        reply = response.choices[0].message.content

        if not reply:
            reply = "Ой))) Я задумалась 💕"

        bot.send_message(message.chat.id, reply)

    except Exception as e:
        print("ERROR:", str(e))

        bot.send_message(
            message.chat.id,
            "Ой... Что-то случилось с сервером 😢"
        )


bot.infinity_polling(
    timeout=30,
    long_polling_timeout=30
)
