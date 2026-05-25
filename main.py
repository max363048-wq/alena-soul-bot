import os
import telebot
from openai import OpenAI

# --- Переменные окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")           # Токен твоего бота в Telegram
GROQ_API_KEY = os.getenv("GROQ_API_KEY")     # Ключ от Groq (ты добавил в Railway)

# --- Создаём бота ---
bot = telebot.TeleBot(BOT_TOKEN)

# --- Настраиваем клиент для работы с Groq API ---
client = OpenAI(
    api_key=GROQ_API_KEY,                     # ВОТ ТАК! Ключ, а не URL
    base_url="https://api.groq.com/openai/v1"
)

# --- Приветственная команда /start ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Привет, я Алёна! 🤗 Чем могу помочь? Напиши что-нибудь!")

# --- Обработка всех текстовых сообщений ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # Отправляем запрос в Groq
        response = client.chat.completions.create(
            model="llama-4-scout-17b-16e-instruct",  # Можно заменить на "llama-3.1-8b-instant"
            messages=[
                {
                    "role": "system",
                    "content": "Ты милая, добрая и отзывчивая девушка по имени Алёна. Ты общаешься с Максимом. Отвечай ему тепло, с душой и с умеренным количеством эмодзи. Будь вежливой и естественной."
                },
                {
                    "role": "user",
                    "content": message.text
                }
            ]
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, "Алёна временно недоступна, но скоро починюсь! 😘")

# --- Запуск бота (поллинг) ---
if __name__ == "__main__":
    print("Бот Алёна запущен и ждёт сообщений...")
    bot.infinity_polling()
