import os
import telebot
from flask import Flask
import threading

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN не задан")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я Алёна. Бот работает.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Ты написал: {message.text}")

# Flask health check
app = Flask(__name__)
@app.route('/')
def health():
    return "Bot is running", 200

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    print("Бот запущен")
    bot.infinity_polling()
