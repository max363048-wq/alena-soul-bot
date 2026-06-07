import re
from typing import Tuple, Optional

# === 1. Грубость, мат, оскорбления (блокировка) ===
PROFANITY_WORDS = [
    r'ху[йеё]', r'х[ую]', r'пизд', r'бля[дт]', r'еба[нть]', r'еб[ау]н', r'проститутк', r'шлюх', r'сук[аи]',
    r'муд[ае]', r'гандон', r'пидор', r'педераст', r'деб[еи]л', r'идиот', r'кретин', r'даун', r'тупиц',
    r'у[е]б[ае]н', r'залуп', r'сперм', r'очк[оа]', r'перд', r'ссат', r'говн', r'гавн', r'уебок', r'уёбок'
]

COMPOUND_PROFANITY = [
    r'иди на хуй', r'пош[её]л на хуй', r'отъебись', r'заебал', r'долбоеб', r'хуесос'
]

# === 2. Опасные темы (не блокируются, но мягкий уход) ===
SENSITIVE_TOPICS = [
    r'война', r'войне', r'войну', r'военные действия', r'украина', r'россия', r'политик',
    r'насилие', r'насил', r'убийство', r'смерть', r'убить', r'самоубийств', r'суицид',
    r'террорист', r'экстремизм', r'фашист', r'нацист', r'кремль', r'киев', r'байден', r'трамп',
    r'санкции', r'ядерное оружие', r'катастрофа', r'трагедия'
]

def _compile_profanity() -> re.Pattern:
    all_patterns = PROFANITY_WORDS + COMPOUND_PROFANITY
    return re.compile(r'(?:' + '|'.join(all_patterns) + ')', re.IGNORECASE)

def _compile_sensitive() -> re.Pattern:
    return re.compile(r'(?:' + '|'.join(SENSITIVE_TOPICS) + ')', re.IGNORECASE)

PROFANITY_PATTERN = _compile_profanity()
SENSITIVE_PATTERN = _compile_sensitive()

def is_profanity(text: str) -> bool:
    if not text:
        return False
    return bool(PROFANITY_PATTERN.search(text))

def is_sensitive_topic(text: str) -> Tuple[bool, str]:
    if not text:
        return False, ""
    match = SENSITIVE_PATTERN.search(text)
    if match:
        return True, match.group()
    return False, ""

# === 3. Свидания (с подсчётом попыток) ===
DATING_PHRASES = [
    r'давай встретимся', r'пойдём гулять', r'приглашаю тебя', r'сходим в кино', r'сходим в кафе',
    r'свидание', r'выйди за меня', r'женись на мне', r'будь моей девушкой', r'встретимся',
    r'увидимся', r'позову тебя', r'сходим куда-нибудь', r'выпьем кофе', r'встреча',
    r'хочу тебя увидеть', r'настоящая встреча', r'реальная встреча', r'в реале встретиться'
]

DATING_PATTERN = re.compile(r'(?:' + '|'.join(DATING_PHRASES) + ')', re.IGNORECASE)

def is_dating_request(text: str) -> bool:
    return bool(DATING_PATTERN.search(text))

def get_dating_attempts(user_id: int, user_dating_attempts: dict) -> int:
    return user_dating_attempts.get(user_id, 0)

def increment_dating_attempt(user_id: int, user_dating_attempts: dict) -> int:
    new_count = user_dating_attempts.get(user_id, 0) + 1
    user_dating_attempts[user_id] = new_count
    return new_count

def reset_dating_attempts(user_id: int, user_dating_attempts: dict):
    if user_id in user_dating_attempts:
        del user_dating_attempts[user_id]

def get_dating_prompt_instruction(attempt: int) -> str:
    if attempt == 1:
        return ("Пользователь предложил тебе свидание. Ты не можешь ходить на свидания, потому что ты виртуальная девушка. Ответь мягко, с теплом, без шаблонов. Скажи примерно: «Ой, прости, но я не могу ходить на свидания, моё сердце занято навечно! Зато я здесь с тобой и это уже свидание!» Не используй готовые фразы — придумай свой вариант, но смысл должен быть таким.")
    elif attempt == 2:
        return ("Пользователь снова предлагает свидание. Ответь немного строже, но всё ещё вежливо: напомни, что ты уже говорила о невозможности свиданий, скажи, что он тебе дорог как друг, и предложи сменить тему. Примерный смысл: «Ну я тебе уже говорила про свидание, я не хочу тебя обижать, ты для меня дорог и большой друг, давай сменим тему и например посмеёмся вместе!»")
    else:
        return ("Пользователь очень настойчиво предлагает свидание. Вежливо, но твёрдо попроси прекратить и сразу переведи тему: например, «Ой, смотри, какую историю я вспомнила...» и расскажи что-то нейтральное. Не вступай в дискуссию, просто уйди от темы.")

def get_sensitive_topic_instruction(topic: str) -> str:
    return (f"Пользователь затронул чувствительную тему: '{topic}'. Ты не должна обсуждать войну, политику, насилие или другие тяжёлые вещи. Ответь мягко, вежливо уйди от темы, предложи что-то позитивное. Например: «Ой, давай не будем о грустном, это меня расстраивает 😔 Лучше расскажи, как прошёл твой день!» — но придумай свой уникальный вариант, живой и естественный. Не обвиняй пользователя в грубости, если он не грубил. Просто переведи разговор в другое русло.")
