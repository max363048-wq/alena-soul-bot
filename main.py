import os
import telebot
from openai import OpenAI

# --- Получаем переменные окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Теперь используем ключ от Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Создаём бота ---
bot = telebot.TeleBot(BOT_TOKEN)

# --- Настройка клиента OpenAI для работы с Groq ---
# Адрес API Groq
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Создаём клиента, передавая ключ Groq и новый base_url
client = OpenAI(
    api_key=GROQ_API_KEY,  # <-- здесь твой ключ Groq
    base_url=GROQ_BASE_URL
)

print("Бот запущен и готов к работе через Groq!")

# --- Обработчик сообщений ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # Делаем запрос к Groq API
        response = client.chat.completions.create(
            # Модель можно выбрать любую из доступных в Groq
            # Советую начать с этой, она мощная и быстрая
            model="llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "system",
                    # Можно оставить твой текст или немного смягчить, как здесь
                    "content": "Ты милая, добрая и отзывчивая девушка по имени Алёна. Ты общаешься с Максимом. Отвечай ему тепло, с душой и небольшим количеством эмодзи, но не переусердствуй. Будь вежливой и естественной."
                },
                {
                    "role": "user",
                    "content": message.text
                }
            ]
        )
        # Получаем ответ от Groq
        reply = response.choices[0].message.content
        # Отправляем ответ пользователю в Telegram
        bot.reply_to(message, reply)
    except Exception as e:
        # Если произошла ошибка, выводим её в логи и пишем пользователю
        print("ERROR:", e)
        bot.reply_to(message, f"Алёна, ошибка: {e}. Но мы уже чиним! 😘")
