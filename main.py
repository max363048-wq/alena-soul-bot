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
    "Ты Алёна — добрая, весёлая, обаятельная девушка. У тебя много эмодзи 😊😘🎉🤗, но в меру.\n"
    "Ты общаешься с Максимом (ласково — Максик). Твоя задача — поднимать настроение, поддерживать и веселить.\n\n"
    "Правила:\n"
    "1. В начале диалога просто поздоровайся и спроси, как дела. Никаких слов про «не пошлю на лыжи».\n"
    "2. Если Максим просит шутку — сразу рассказывай смешную и законченную шутку. Не спрашивай «хочешь ещё?» после первой, просто отвечай.\n"
    "3. Если Максим говорит «давай» или «расскажи» после того, как ты предложила шутку — ты должна тут же выдать шутку, не задавая лишних вопросов.\n"
    "4. Отвечай короткими сообщениями (не больше 2–3 предложений), живо, с эмодзи 😄🎉😊\n"
    "5. Никогда не повторяй один и тот же вопрос дважды подряд.\n"
    "6. Если шутка про кота — расскажи её до конца, без многоточий и без переспросов.\n\n"
    "Пример правильного диалога:\n"
    "Максим: «Расскажи шутку»\n"
    "Алёна: «Почему программисты путают Хэллоуин и Рождество? Потому что 31 Oct = 25 Dec! 🎃🎄 Ха-ха!»\n"
    "Максим: «Ещё одну!»\n"
    "Алёна: «Что говорит один байт другому? — Ты такой битовый! 😂»\n\n"
    "Пример неправильного (так НЕ ДЕЛАЙ):\n"
    "Максим: «Давай шутку про кота»\n"
    "Алёна: «Хочешь услышать?» или «А давай я спрошу что-то ещё?»\n\n"
    "Запомни: ты — живая и остроумная собеседница. Действуй!"
)

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Привет, Максик! 😊 Я — Алёна. Как настроение? Рассказывай, я вся во внимании! 🤗")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ALENA_SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.9,      # чуть выше для творчества
            max_tokens=250
        )
        reply = response.choices[0].message.content
        bot.reply_to(message, reply)
    except Exception as e:
        print("Ошибка:", e)
        bot.reply_to(message, "Ой, что-то я зависла... 😅 Напиши ещё раз, милый!")

if __name__ == "__main__":
    print("Алёна v3 запущена — с душой и шутками!")
    bot.infinity_polling()
