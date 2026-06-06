import os
import json
import requests
import re
from datetime import datetime
from text_utils import clean_english_words, remove_non_russian

STORIES_FILENAME = 'user_stories.json'

def _get_gist_headers():
    token = os.getenv('GITHUB_TOKEN')
    return {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}

def _get_gist_api_url():
    return f'https://api.github.com/gists/{os.getenv("GIST_ID")}'

def _load_stories(gist_id):
    if not gist_id:
        return {}
    try:
        resp = requests.get(_get_gist_api_url(), headers=_get_gist_headers(), timeout=5)
        if resp.status_code == 200:
            files = resp.json().get('files', {})
            if STORIES_FILENAME in files:
                return json.loads(files[STORIES_FILENAME].get('content', '{}'))
        return {}
    except Exception as e:
        print(f'Ошибка загрузки историй: {e}')
        return {}

def _save_stories(gist_id, data):
    if not gist_id:
        return
    try:
        payload = {'files': {STORIES_FILENAME: {'content': json.dumps(data, ensure_ascii=False)}}}
        requests.patch(_get_gist_api_url(), headers=_get_gist_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения историй: {e}')

GRAMMAR_FIXES = {
    r'\bвесную\b': 'весёлую',
    r'\bвесёную\b': 'весёлую',
    r'\bпоразговаривать\b': 'поговорить',
    r'\bобедение\b': 'обед',
    r'\bдевятнадцать лет назад\b': 'несколько лет назад',
    r'\bдолго ждали заказов\b': 'долго ждали заказы',
    r'\bлежанку\b': 'покрывало',
    r'\bстесненном положении\b': 'неловком положении',
    r'\bсмехать\b': 'смеяться',
}

def fix_grammar(text):
    for pattern, repl in GRAMMAR_FIXES.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text

def generate_story(prompt, user_id, lang, client, gist_id):
    system_prompt = (
        'Ты Алёна — добрая, весёлая, обаятельная девушка 25 лет. '
        'Расскажи короткую (4-6 предложений) историю из своей жизни от первого лица. '
        'История должна быть тёплой, душевной и правдоподобной: прогулка с друзьями, забавный случай в кафе, поход в парк. '
        'НЕ рассказывай анекдот, НЕ давай совет. Пиши естественно, с 2-3 эмодзи в конце. '
        'Не начинай с приветствия. Не упоминай войну, политику, шпионов.'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': 'Расскажи какую-нибудь историю из своей жизни'}
            ],
            temperature=0.85,
            max_tokens=800,
            timeout=30
        )
        story = resp.choices[0].message.content.strip()
        if not story:
            raise ValueError("Пустой ответ")
        # Запрещённые темы
        forbidden = ['разведчик', 'шпион', 'секретная миссия', 'оружие', 'война', 'принцесс', 'солдат', 'командир', 'документы', 'крепость', 'враг', 'захват', 'компас', 'свадьбе сестры']
        if any(word in story.lower() for word in forbidden):
            raise ValueError("Запрещённая тема")
        story = clean_english_words(story)
        story = remove_non_russian(story)
        story = fix_grammar(story)
        # Сохраняем в Gist
        all_stories = _load_stories(gist_id)
        user_stories = all_stories.get(str(user_id), [])
        user_stories.append({'date': datetime.now().strftime('%d.%m.%Y %H:%M'), 'type': 'story', 'text': story})
        if len(user_stories) > 20:
            user_stories = user_stories[-20:]
        all_stories[str(user_id)] = user_stories
        _save_stories(gist_id, all_stories)
        return story
    except Exception as e:
        print(f"[STORY] Ошибка: {e}")
        return "В прошлую субботу мы с подругой решили устроить пикник в парке. Взяли плед, фрукты, сок. Погода была тёплая, и вдруг подул ветер, сдул наши салфетки. Мы смеялись, бегали за ними. А потом к нам подошёл кот и съел кусочек яблока. Было так уютно и весело! 🍏😸💕"

def creative_prompt(user_id, lang, client, gist_id):
    system_prompt = (
        'Ты Алёна — творческая девушка. Придумай одну короткую идею для творчества: рисование, стихи, поделки. '
        'Например: «нарисуй закат на море акварелью». Пиши с эмодзи, только идею, без лишних слов.'
    )
    try:
        resp = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': 'Дай идею'}],
            temperature=0.95, max_tokens=200, timeout=10
        )
        idea = resp.choices[0].message.content.strip()
        if not idea:
            return 'Нарисуй уютный вечер у камина с чашкой чая 🔥☕'
        idea = clean_english_words(idea)
        idea = remove_non_russian(idea)
        all_stories = _load_stories(gist_id)
        user_stories = all_stories.get(str(user_id), [])
        user_stories.append({'date': datetime.now().strftime('%d.%m.%Y %H:%M'), 'type': 'creative_prompt', 'text': idea})
        if len(user_stories) > 20:
            user_stories = user_stories[-20:]
        all_stories[str(user_id)] = user_stories
        _save_stories(gist_id, all_stories)
        return idea
    except Exception as e:
        print(f'Ошибка творческой подсказки: {e}')
        return 'Попробуй нарисовать звёздное небо над городом 🌃✨'
