# stories.py — финальная версия с проверкой грамматики и логики

import os
import json
import requests
from datetime import datetime
from text_utils import clean_english_words, remove_non_russian

STORIES_FILENAME = 'user_stories.json'

def _get_gist_headers():
    token = os.getenv('GITHUB_TOKEN')
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

def _load_stories(gist_id: str) -> dict:
    if not gist_id:
        return {}
    try:
        headers = _get_gist_headers()
        url = f'https://api.github.com/gists/{gist_id}'
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if STORIES_FILENAME in files:
                content = files[STORIES_FILENAME].get('content', '{}')
                return json.loads(content)
        return {}
    except Exception as e:
        print(f'Ошибка загрузки историй из Gist: {e}')
        return {}

def _save_stories(gist_id: str, data: dict):
    if not gist_id:
        return
    try:
        headers = _get_gist_headers()
        url = f'https://api.github.com/gists/{gist_id}'
        payload = {
            'files': {
                STORIES_FILENAME: {
                    'content': json.dumps(data, ensure_ascii=False)
                }
            }
        }
        requests.patch(url, headers=headers, json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения историй в Gist: {e}')

def generate_story(prompt: str, user_id: int, lang: str, client, gist_id: str) -> str:
    system_prompt = (
        'Ты Алёна, 25 лет, добрая, весёлая, обаятельная девушка.\n'
        'Расскажи короткую (4-6 предложений) историю ИЗ ТВОЕЙ ЖИЗНИ от первого лица.\n'
        'Обычные, тёплые моменты: прогулка с друзьями, поход в кафе, забавный случай, путешествие.\n'
        'ЗАПРЕЩЕНО: любые странные, неестественные или сюрреалистические сюжеты (например, "девятнадцать лет назад нашли лавочку", "собака научила играть в мяч", "компас в сумке", "цветок со свадьбы сестры").\n'
        'Избегай повторов, нелогичных переходов и странных слов: "весёную" → "весёлую", "поразговаривать" → "поговорить", "обедение" → "обед", "добротно разговариваем" → "хорошо разговаривали".\n'
        'Следи за грамматикой: окончания глаголов и прилагательных должны соответствовать роду (например, "Анастасия получила договор").\n'
        'Пиши просто, живо, с одним-двумя эмодзи в конце. Без английских слов. Не начинай с приветствия.'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            max_tokens=500,
            timeout=10
        )
        story = resp.choices[0].message.content.strip()
        if not story:
            return "Как-то мы с подругой пошли в парк кататься на роликах, и я так разогналась, что не смогла затормозить и врезалась в куст сирени! 😄 Было смешно и немного стыдно, зато теперь я умею тормозить правильно 💕"

        # Дополнительная фильтрация
        forbidden_phrases = ['разведчик', 'шпион', 'секретная миссия', 'оружие', 'война', 'принцесс', 'солдат', 'командир', 'документы', 'крепость', 'враг', 'захват', 'компас', 'цветок на свадьбе', 'девятнадцать лет назад', 'собака научила']
        for phrase in forbidden_phrases:
            if phrase in story.lower():
                return "Ой, лучше я расскажу, как мы с подругой в прошлое воскресенье пошли в кафе и ели огромное мороженое с клубникой! 🍓🍦 Было так весело, что даже официант засмеялся 😄 А потом гуляли по парку и кормили уток. 💕"

        # Дополнительная постобработка
        story = clean_english_words(story)
        story = remove_non_russian(story)
        # Исправление конкретных ошибок
        story = story.replace("весёную", "весёлую")
        story = story.replace("весеную", "весеннюю")
        story = story.replace("Весёную", "Весёлую")

        # Сохраняем в Gist
        gist_id = gist_id or ''
        all_stories = _load_stories(gist_id)
        user_stories = all_stories.get(str(user_id), [])
        user_stories.append({
            'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'type': 'story',
            'text': story
        })
        if len(user_stories) > 20:
            user_stories = user_stories[-20:]
        all_stories[str(user_id)] = user_stories
        _save_stories(gist_id, all_stories)

        return story
    except Exception as e:
        print(f'Ошибка генерации истории: {e}')
        return "Ой, кажется, моя фантазия сегодня устала... Давай попробуем позже? 😊"

def creative_prompt(user_id: int, lang: str, client, gist_id: str) -> str:
    system_prompt = (
        'Ты Алёна — вдохновляющая, творческая девушка. Придумай одну короткую, конкретную идею для творчества '
        '(например: «нарисуй закат на море акварелью» или «напиши стих о летнем дожде»). '
        'Пиши с эмодзи, без английских слов, не предлагай создавать ботов или проекты — только идеи для рисования, стихов, поделок. '
        'Сразу выдай идею, не спрашивай пользователя о его планах.'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': 'Дай мне творческую подсказку на сегодня'}
            ],
            temperature=0.95,
            max_tokens=300,
            timeout=10
        )
        idea = resp.choices[0].message.content.strip()
        if not idea:
            return 'Ой, муза сегодня капризничает... Давай попробуем ещё раз? 😊'
        idea = clean_english_words(idea)
        idea = remove_non_russian(idea)
        # Сохранение в Gist
        gist_id = gist_id or ''
        all_stories = _load_stories(gist_id)
        user_stories = all_stories.get(str(user_id), [])
        user_stories.append({
            'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'type': 'creative_prompt',
            'text': idea
        })
        if len(user_stories) > 20:
            user_stories = user_stories[-20:]
        all_stories[str(user_id)] = user_stories
        _save_stories(gist_id, all_stories)
        return idea
    except Exception as e:
        print(f'Ошибка генерации творческой подсказки: {e}')
        return 'Что-то моя фантазия разыгралась не на шутку... Попробуем позже? 😅'
