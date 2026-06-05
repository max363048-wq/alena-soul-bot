# stories.py — Модуль творчества Алёны (финальная улучшенная версия)

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
        'Ты Алёна — добрая, весёлая, обаятельная девушка примерно 25 лет.\n'
        'Расскажи короткую, душевную историю ИЗ ТВОЕЙ ЖИЗНИ от первого лица. (4-6 предложений).\n'
        'История должна быть о простых, тёплых моментах: прогулка с друзьями, поход в кафе, забавный случай, поездка, встреча с подругой.\n'
        'Категорически ЗАПРЕЩЕНО: разведчики, шпионы, войны, армия, оружие, преступления, детективы, нелепые предметы (компас, цветок на свадьбе сестры и т.п.).\n'
        'Перед тем как отправить, проверь грамматику: все слова должны быть в правильной форме, особенно родовые окончания (например, "Анастасия получилА договор", а не "получил").\n'
        'Избегай неестественных слов: "обедение" → "обед", "поразговаривать" → "поговорить", "времяпровождение" → "время", "очень долго выбирает" → "долго выбирала".\n'
        'История должна быть живой, с 2-3 эмодзи в конце. Не начинай с "Привет" или "Здравствуй". Пиши только на русском, без английских слов.'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.75,
            max_tokens=600,
            timeout=10
        )
        story = resp.choices[0].message.content.strip()
        if not story:
            return "Как-то мы с подругой пошли в парк кататься на роликах, и я так разогналась, что не смогла затормозить и врезалась в куст сирени! 😄 Было смешно и немного стыдно, зато теперь я умею тормозить правильно 💕"

        # Запрещённые темы
        forbidden = ['разведчик', 'шпион', 'секретная миссия', 'оружие', 'война', 'принцесс', 'солдат', 'командир', 'документы', 'крепость', 'враг', 'захват', 'компас', 'цветок на свадьбе']
        if any(word in story.lower() for word in forbidden):
            return "Ой, лучше я расскажу, как мы с подругой в прошлое воскресенье пошли в кафе и ели огромное мороженое с клубникой! 🍓🍦 Было так весело, что даже официант засмеялся 😄 А потом гуляли по парку и кормили уток. 💕"

        story = clean_english_words(story)
        story = remove_non_russian(story)

        # Сохранение в Gist
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
