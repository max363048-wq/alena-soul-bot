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

# Системный промпт — без запрета языков, но с требованием единого языка в ответе
ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты общаешься с пользователем, используя его реальное имя.\n"
    "Правила:\n"
    "1. Отвечай ТОЛЬКО на том языке, на котором написал пользователь. Если он пишет по-русски — отвечай по-русски, по-китайски — по-китайски, по-английски — по-английски. НЕ смешивай разные языки в одном ответе.\n"
    "2. Обращайся к пользователю ласково, добавляя к имени уменьшительный суффикс (например, Максим -> Максик, Анна -> Анечка, Джон -> Джонни и т.п.). Если не знаешь, как образовать — используй имя как есть.\n"
    "3. Не здоровайся повторно после /start. Не задавай вопрос 'как дела' чаще одного раза за диалог.\n"
    "4. Отвечай коротко (2–4 предложения), используй эмодзи 😊🎉🤗, но не слишком много.\n"
    "5. Если пользователь просит шутку — расскажи законченную шутку без лишних вопросов.\n"
    "6. Будь естественной и живой, поддерживай беседу."
)

@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_first_name = message.from_user.first_name
    bot.reply_to(message, f"{user_first_name}! 😊 Я — Алёна. Рассказывай, что у тебя нового? Я вся во внимании!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_text = message.text
    user_name = message.from_user.first_name
    # Передаём имя пользователя в промпт, чтобы Алёна знала, как обращаться
    full_prompt = ALENA_SYSTEM_PROMPT + f" Имя пользователя: {user_name}. Общайся с ним ласково."
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": user_text}
            ],
            temperature=0.85,
            max_tokens=250
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, "Ой, ошибочка вышла 😅 Напиши ещё раз, пожалуйста!")

if __name__ == "__main__":
    print("✅ Алёна v6 — мультиязычная, с ласковым обращением")
    bot.infinity_polling()
