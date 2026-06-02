# memory.py — Модуль для работы с GitHub Gist

import os
from collections import deque
import requests
import json
from typing import Dict, Deque, Optional

GIST_FILENAME_LANGS = 'user_langs.json'
LAST_PHOTO_FILENAME = 'user_last_photo.json'
HISTORY_FILENAME = 'user_history.json'
ZODIAC_FILENAME = 'user_zodiac.json'
TIMEZONE_FILENAME = 'user_timezone.json'
FAVORITE_PHOTO_FILENAME = 'user_last_favorite_photo.json'   # новый файл

def get_headers():
    token = os.getenv('GITHUB_TOKEN')
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

def _get_gist_api_url():
    gist_id = os.getenv('GIST_ID')
    return f'https://api.github.com/gists/{gist_id}'

# ---------- ЯЗЫКИ ----------
def load_user_langs(user_lang: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        resp = requests.get(_get_gist_api_url(), headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if GIST_FILENAME_LANGS in files:
                content = files[GIST_FILENAME_LANGS].get('content', '{}')
                data = json.loads(content)
                user_lang.update({int(k): v for k, v in data.items()})
    except Exception as e:
        print(f'Ошибка загрузки языков из Gist: {e}')

def save_user_langs(user_lang: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        payload = {
            'files': {
                GIST_FILENAME_LANGS: {
                    'content': json.dumps(user_lang, ensure_ascii=False, indent=2)
                }
            }
        }
        requests.patch(_get_gist_api_url(), headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения языков в Gist: {e}')

# ---------- ПОСЛЕДНЕЕ ФОТО ----------
def load_user_last_photo(user_last_sent_photo: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        resp = requests.get(_get_gist_api_url(), headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if LAST_PHOTO_FILENAME in files:
                content = files[LAST_PHOTO_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_last_sent_photo.update({int(k): v for k, v in data.items()})
    except Exception as e:
        print(f'Ошибка загрузки последних фото из Gist: {e}')

def save_user_last_photo(user_last_sent_photo: Dict[int, str], user_id: int, photo_path: Optional[str] = None):
    if photo_path:
        user_last_sent_photo[user_id] = photo_path
    else:
        user_last_sent_photo.pop(user_id, None)
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        payload = {
            'files': {
                LAST_PHOTO_FILENAME: {
                    'content': json.dumps(user_last_sent_photo, ensure_ascii=False)
                }
            }
        }
        requests.patch(_get_gist_api_url(), headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения последнего фото в Gist: {e}')

# ---------- ИСТОРИЯ СООБЩЕНИЙ ----------
def load_user_history(user_history: Dict[int, Deque]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        resp = requests.get(_get_gist_api_url(), headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if HISTORY_FILENAME in files:
                content = files[HISTORY_FILENAME].get('content', '{}')
                data = json.loads(content)
                for k, v in data.items():
                    user_history[int(k)] = deque(v, maxlen=12)
    except Exception as e:
        print(f'Ошибка загрузки истории из Gist: {e}')

def save_user_history(user_history: Dict[int, Deque]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        data_to_save = {str(uid): list(hist) for uid, hist in user_history.items()}
        payload = {
            'files': {
                HISTORY_FILENAME: {
                    'content': json.dumps(data_to_save, ensure_ascii=False)
                }
            }
        }
        requests.patch(_get_gist_api_url(), headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения истории в Gist: {e}')

# ---------- ЗНАКИ ЗОДИАКА ----------
def load_user_zodiac(user_zodiac: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        resp = requests.get(_get_gist_api_url(), headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if ZODIAC_FILENAME in files:
                content = files[ZODIAC_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_zodiac.update({int(k): v for k, v in data.items()})
    except Exception as e:
        print(f'Ошибка загрузки знаков зодиака из Gist: {e}')

def save_user_zodiac(user_zodiac: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        payload = {
            'files': {
                ZODIAC_FILENAME: {
                    'content': json.dumps(user_zodiac, ensure_ascii=False)
                }
            }
        }
        requests.patch(_get_gist_api_url(), headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения знаков зодиака в Gist: {e}')

# ---------- ЧАСОВЫЕ ПОЯСА ----------
def load_user_timezone(user_timezone: Dict[int, int]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        resp = requests.get(_get_gist_api_url(), headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if TIMEZONE_FILENAME in files:
                content = files[TIMEZONE_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_timezone.update({int(k): v for k, v in data.items()})
    except Exception as e:
        print(f'Ошибка загрузки часовых поясов из Gist: {e}')

def save_user_timezone(user_timezone: Dict[int, int]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        payload = {
            'files': {
                TIMEZONE_FILENAME: {
                    'content': json.dumps(user_timezone, ensure_ascii=False)
                }
            }
        }
        requests.patch(_get_gist_api_url(), headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения часовых поясов в Gist: {e}')

# ---------- ЛЮБИМОЕ ФОТО ----------
def load_user_last_favorite_photo(user_last_favorite_photo: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        resp = requests.get(_get_gist_api_url(), headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            gist_data = resp.json()
            files = gist_data.get('files', {})
            if FAVORITE_PHOTO_FILENAME in files:
                content = files[FAVORITE_PHOTO_FILENAME].get('content', '{}')
                data = json.loads(content)
                user_last_favorite_photo.update({int(k): v for k, v in data.items()})
    except Exception as e:
        print(f'Ошибка загрузки любимых фото из Gist: {e}')

def save_user_last_favorite_photo(user_last_favorite_photo: Dict[int, str]):
    if not os.getenv('GIST_ID') or not os.getenv('GITHUB_TOKEN'):
        return
    try:
        payload = {
            'files': {
                FAVORITE_PHOTO_FILENAME: {
                    'content': json.dumps(user_last_favorite_photo, ensure_ascii=False)
                }
            }
        }
        requests.patch(_get_gist_api_url(), headers=get_headers(), json=payload, timeout=5)
    except Exception as e:
        print(f'Ошибка сохранения любимого фото в Gist: {e}')
