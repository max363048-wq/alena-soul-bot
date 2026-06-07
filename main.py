import os
import telebot
import time
import threading
from flask import Flask
from openai import OpenAI

BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация клиента OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я Алёна. Спрашивай что угодно 😊")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text
    print(f"[DEBUG] Получено сообщение: {user_text}")
    
    try:
        response = client.chat.completions.create(
            model="openrouter/llama-3.1-8b-instruct:free",
            messages=[
                {"role": "system", "content": "Ты Алёна, добрая, весёлая девушка. Отвечай кратко (2-3 предложения), на русском, с эмодзи. Никогда не начинай с приветствия."},
                {"role": "user", "content": user_text}
            ],
            temperature=0.8,
            max_tokens=600,
            timeout=25
        )
        reply = response.choices[0].message.content.strip()
        print(f"[DEBUG] Ответ OpenRouter: {reply}")
        bot.reply_to(message, reply)
    except Exception as e:
        print(f"[ERROR] OpenRouter ошибка: {type(e).__name__}: {str(e)}")
        # Fallback: эхо-ответ
        bot.reply_to(message, f"Я тебя слышу, но сейчас туплю. Ты написал: {user_text} 😊")

# Flask health check
app = Flask(__name__)
@app.route('/')
def health():
    return "Bot is running", 200

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    print("Бот запущен с OpenRouter")
    bot.infinity_polling()
