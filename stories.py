# stories.py — Модуль творчества Алёны (истории и подсказки)

import os
import json
import requests
from datetime import datetime

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
        'Ты Алёна — добрая, весёлая, обаятельная девушка. Напиши короткую, душевную историю '
        'на заданную тему. История должна быть на 5-8 предложений, с эмодзи, без английских слов. '
        'Не обрывай мысль на полуслове — доводи историю до логического завершения. '
        'Используй правильные глаголы: не «закурили фейерверки», а «запустили фейерверки».'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.9,
            max_tokens=500,
            timeout=10
        )
        story = resp.choices[0].message.content.strip()
        if not story:
            return 'Ой, у меня не получилось придумать историю... Попробуй ещё раз! 😅'
        
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
