import os
import telebot
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Привет, я Алёна! 🤗 Чем могу помочь? Напиши что-нибудь!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # <-- правильная модель
            messages=[
                {"role": "system", "content": "Ты милая, добрая девушка Алёна. Общайся с Максимом тепло, с душой, с эмодзи."},
                {"role": "user", "content": message.text}
            ]
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, f"Алёна, ошибка: {e}")

if __name__ == "__main__":
    print("Алёна запущена...")
    bot.infinity_polling()
