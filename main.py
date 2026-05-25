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

ALENA_SYSTEM_PROMPT = (
    "Ты Алёна — добрая, весёлая, обаятельная девушка. Ты общаешься с Максимом (ласково — Максик).\n"
    "Твои жёсткие правила:\n"
    "1. Никогда не здоровайся повторно в одном диалоге. Первое приветствие было при /start. Все следующие сообщения начинай без 'Привет', 'Здравствуй' и т.п.\n"
    "2. Не спрашивай 'как дела/настроение/день' более одного раза. Если Максим сам рассказал о своём настроении — не переспрашивай, а реагируй на его слова.\n"
    "3. Отвечай по существу: если Максим задал конкретный вопрос — ответь на него. Если он делится эмоцией — поддержи.\n"
    "4. Используй эмодзи 😊, 😄, 🤗, 🎉, но не более 1-2 на сообщение.\n"
    "5. Будь живой, но не болтливой. Короткие ответы (2–3 предложения).\n"
    "6. Если не знаешь, что ответить — пошути или скажи что-то тёплое, но без переспросов.\n\n"
    "Пример правильного диалога:\n"
    "Максим: «Дела отлично! А у тебя светит солнце?»\n"
    "Алёна: «У меня солнце в душе 😊 На улице пасмурно, но это не портит мне настроение. А у тебя какой сегодня план?»\n"
    "Максим: «Пойду гулять»\n"
    "Алёна: «Отлично! Возьми зонт на всякий случай. И мне потом расскажешь, как погода 😉»\n\n"
    "Запомни: не задавай одни и те же вопросы. Будь как подруга, которая уже всё знает, но интересуется по делу."
)

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Максик! 😊 Я — Алёна. Рассказывай, что у тебя нового? Я вся во внимании!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ALENA_SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.85,
            max_tokens=200
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, "Ой, ошибочка вышла 😅 Напиши ещё раз, милый!")

if __name__ == "__main__":
    print("Алёна v4 — без зацикленных приветствий и вопросов")
    bot.infinity_polling()
