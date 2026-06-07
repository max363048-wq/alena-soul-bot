# main.py — минимальный тест OpenRouter с рабочей моделью

import os
import telebot
from openai import OpenAI
from flask import Flask
import threading

print("!!! ЗАПУСК МИНИМАЛЬНОГО ТЕСТА OPENROUTЕР (Mistral) !!!")

BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

if not OPENROUTER_API_KEY:
    print("ОШИБКА: OPENROUTER_API_KEY не задан!")
else:
    print(f"Ключ OpenRouter найден, начинается с {OPENROUTER_API_KEY[:10]}...")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я Алёна. Тест OpenRouter (Mistral).")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    print(f"[OpenRouter] Получено сообщение: {message.text}")
    try:
        resp = client.chat.completions.create(
            model="openrouter/mistral-7b-instruct:free",  # заменили на рабочую
            messages=[{"role": "user", "content": message.text}],
            temperature=0.7,
            max_tokens=200,
            timeout=15
        )
        reply = resp.choices[0].message.content.strip()
        print(f"[OpenRouter] Ответ: {reply[:100]}")
        bot.reply_to(message, reply)
    except Exception as e:
        error_msg = f"Ошибка: {type(e).__name__} - {str(e)}"
        print(error_msg)
        bot.reply_to(message, error_msg)

# Flask health check
app = Flask(__name__)
@app.route('/')
def health():
    return "Bot is running", 200

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    print("Тестовый бот OpenRouter с Mistral запущен")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка polling: {e}")
