# stories.py — Модуль творчества Алёны (истории и подсказки) с проверкой грамматики

import os
import json
import requests
import re
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

def _fix_common_errors(text: str) -> str:
    """Исправляет типичные странные слова, которые может сгенерировать LLM."""
    fixes = {
        'прирулили': 'приехали',
        'прирулил': 'приехал',
        'запусть': 'запустят',
        'запустьи': 'запустили',
        'гудели': 'говорили',
        'подолгу гудали': 'долго разговаривали',
        'звяк на': 'щёлк — и',
        'осень жизни': 'осенью',
        'я так благодарна, что удалось собрать': 'я так рада, что собрала',
        'стоит на такое приятно': 'стоит ради такого приятного',
    }
    for wrong, right in fixes.items():
        text = re.sub(wrong, right, text, flags=re.IGNORECASE)
    return text

def generate_story(prompt: str, user_id: int, lang: str, client, gist_id: str) -> str:
    system_prompt = (
        'Ты Алёна — добрая, весёлая, обаятельная девушка. '
        'Расскажи короткую (4-6 предложений) историю ИЗ ТВОЕЙ СОБСТВЕННОЙ ЖИЗНИ от первого лица, с твоими чувствами. '
        'Ты — главная героиня. История должна быть тёплой, повседневной: прогулка с друзьями, поход в кафе, встреча с подругой, забавный случай, путешествие. '
        'Категорически запрещены: разведчики, шпионы, секретные миссии, армия, война, оружие, принцессы, солдаты, командиры, преступления, детективные сюжеты. '
        'ОЧЕНЬ ВАЖНО: перед отправкой прочитай историю и исправь все грамматические ошибки, нелепые слова ("прирулили", "запусть", "гудели" и т.п.). '
        'История должна быть логичной, без повторов и странных фраз. Говори просто, без канцелярита. '
        'Используй 2-3 эмодзи в разных местах. Пиши на русском, без английских слов. Не начинай с приветствия.'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.85,
            max_tokens=500,
            timeout=10
        )
        story = resp.choices[0].message.content.strip()
        if not story:
            return "Как-то я пошла в парк и встретила старого друга, мы так приятно поболтали, что забыли о времени 💕 Было очень душевно!"

        # Постобработка: исправление типичных ошибок
        story = _fix_common_errors(story)
        
        # Дополнительная фильтрация запрещённых слов
        forbidden = ['разведчик', 'шпион', 'секретная миссия', 'оружие', 'война', 'принцесс', 'солдат', 'командир', 'документы', 'крепость', 'враг', 'захват']
        if any(word in story.lower() for word in forbidden):
            return "Ой, я немного увлеклась 😅 Давай лучше расскажу, как мы с подругой в прошлое воскресенье пошли в кафе и ели огромное мороженое с клубникой 🍓🍦 Было так весело, что даже официант засмеялся 😄 А потом гуляли по парку и кормили уток 💕"

        story = clean_english_words(story)
        story = remove_non_russian(story)

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
        return 'Ой, кажется, моя фантазия сегодня устала... Давай попробуем позже? 😊'

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
