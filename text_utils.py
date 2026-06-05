# text_utils.py — Общие функции очистки текста
import re
import random

SAFE_EMOJIS = ['😊', '💖', '✨', '😄', '😘', '🥰', '💕', '🤗']

def clean_english_words(text: str) -> str:
    if not text:
        return text
    
    # Расширенный словарь замен (добавлены новые)
    reps = {
        r'\balmost\b': 'почти',
        r'\btemperature\b': 'температура',
        r'\bdegrees?\b': 'градусов',
        r'\bso\b': 'так что',
        r'\bbut\b': 'но',
        r'\band\b': 'и',
        r'\bok\b': 'хорошо',
        r'\bplease\b': 'пожалуйста',
        r'\bsorry\b': 'извини',
        r'\bthanks\b': 'спасибо',
        r'\bhello\b': 'привет',
        r'\bhi\b': 'привет',
        r'\bgreat\b': 'отлично',
        r'\bgood\b': 'хороший',
        r'\bvery\b': 'очень',
        r'\blike\b': 'как',
        r'\breally\b': 'действительно',
        r'\bwhat\b': 'что',
        r'\bwhy\b': 'почему',
        r'\byes\b': 'да',
        r'\bno\b': 'нет',
        r'\bI\b': 'я',
        r'\byou\b': 'ты',
        r'\bwe\b': 'мы',
        r'\bthey\b': 'они',
        r'\bfor\b': 'для',
        r'\bwith\b': 'с',
        r'\bfrom\b': 'из',
        r'\bto\b': 'в',
        r'\bof\b': '',
        r'\bthe\b': '',
        r'\ba\b': '',
        r'\ban\b': '',
        r'\bnot\b': 'не',
        r'\blater\b': 'позже',
        r'\bmaybe\b': 'возможно',
        r'\binside\b': 'внутри',
        r'\bjust\b': 'просто',
        r'\bnow\b': 'сейчас',
        r'\bwell\b': 'ну',
        r'\bthen\b': 'затем',
        r'\beven\b': 'даже',
        r'\bsome\b': 'некоторые',
        r'\bany\b': 'любые',
        r'\bhere\b': 'здесь',
        r'\bthere\b': 'там',
        r'\bmy\b': 'мой',
        r'\byour\b': 'твой',
        r'\bhis\b': 'его',
        r'\bher\b': 'её',
        r'\babsolutely\b': 'конечно',
        r'\blounge\b': 'шезлонг',
        r'\bromantic\b': 'романтично',
        r'\binteres\w*\b': 'интересн',
        r'\brefreshed\b': 'посвежевшей',
        r'\bfeeling\b': 'чувствуя',
        r'\bdiscuss\b': 'обсудить',
        r'\bdebug\b': 'отладка',
        r'\bcute\b': 'милые',
        r'\btranquil\b': 'спокойного',
        r'\btranquility\b': 'спокойствие',
        r'\bserious\b': 'серьёзном',
        r'\bresilient\b': 'стойким',
        r'\bearlier\b': 'раньше',
        r'\btoday\b': 'сегодня',
        r'\bfinally\b': 'наконец',
        r'\bbecause\b': 'потому что',
        r'\bcapricorn\b': 'козерог',
        r'\bmoi\b': 'мной',
        r'\bagree\b': 'согласна',
        r'\bspectacle\b': 'зрелище',
        r'\bpatterns\b': 'узоры',
        r'\boverlooking\b': 'с видом на',
        r'\btouched\b': 'тронули',
        r'\bmagical\b': 'волшебные',
        r'\bfound\b': 'нашла',
        r'\bfeels\b': 'ощущается',
        r'\bthy\b': 'твоё',
        r'\benjoy\w*\b': 'наслажда',
        r'\btranquility\b': 'спокойствие',
        r'\binseparable\b': 'неразлучны',
        r'\bbird\b': 'птица',
        r'\bbirds\b': 'птицы',
        r'\bvaluing\b': 'ценя',
        r'\bamong\b': 'среди',
        r'\baccepting\b': 'принимая',
        r'\bпрощай мне\b': 'прости меня',
        r'\bпрощайте мне\b': 'простите меня',
        r'\bгнца\b': 'прибоя',
        r'\bгнц\b': 'прибой',
        r'\bsettlement\b': 'посёлок',
        r'\brootovat\b': 'болеть',
        r'\broot\b': 'болею',
        # НОВЫЕ ЗАМЕНЫ (по результатам тестов)
        r'\bkind\b': 'добрый',
        r'\bhelpful\b': 'полезной',
        r'\btoo\b': 'слишком',
        r'\bvery\b': 'очень',
        r'\bso\b': 'так',
        r'\bgood\b': 'хороший',
        r'\bgreat\b': 'отлично',
        r'\bperfect\b': 'идеально',
        r'\bnice\b': 'мило',
        r'\bawesome\b': 'потрясающе',
        r'\bcool\b': 'круто',
        r'\bamazing\b': 'удивительно',
        r'\bfun\b': 'весело',
        r'\bhappy\b': 'счастлива',
        r'\bsad\b': 'грустно',
        r'\bbad\b': 'плохо',
        r'\bwrong\b': 'неправильно',
        r'\bright\b': 'правильно',
        r'\btrue\b': 'правда',
        r'\bfalse\b': 'ложь',
        r'\bexactly\b': 'точно',
        r'\bdefinitely\b': 'определённо',
        r'\bprobably\b': 'вероятно',
        r'\bquite\b': 'довольно',
        r'\brather\b': 'скорее',
        r'\bsomehow\b': 'как-то',
        r'\banyway\b': 'в любом случае',
        r'\bhowever\b': 'однако',
        r'\bmoreover\b': 'более того',
        r'\btherefore\b': 'поэтому',
        r'\bthus\b': 'таким образом',
        r'\bsince\b': 'поскольку',
        r'\bwhile\b': 'в то время как',
        r'\bthough\b': 'хотя',
        r'\balthough\b': 'хотя',
        r'\bbeautiful\b': 'красивая',
        r'\bpretty\b': 'симпатичная',
        r'\bhandsome\b': 'красивый',
        r'\blovely\b': 'прекрасная',
        r'\bgorgeous\b': 'великолепная',
        r'\bstunning\b': 'сногсшибательная',
        r'\bwonderful\b': 'замечательная',
        r'\bterrific\b': 'потрясающий',
        r'\bfantastic\b': 'фантастический',
        r'\bbrilliant\b': 'блестящий',
        r'\bsmart\b': 'умный',
        r'\bclever\b': 'умный',
        r'\bintelligent\b': 'интеллигентный',
        r'\bwise\b': 'мудрый',
        r'\bfunny\b': 'смешной',
        r'\bhumorous\b': 'юмористичный',
        r'\bjoyful\b': 'радостный',
        r'\bcheerful\b': 'жизнерадостный',
        r'\bpositive\b': 'позитивный',
        r'\bnegative\b': 'негативный',
        r'\boptimistic\b': 'оптимистичный',
        r'\bpessimistic\b': 'пессимистичный',
        r'\breal\b': 'реальный',
        r'\bvirtual\b': 'виртуальный',
        r'\bdigital\b': 'цифровой',
        r'\bonline\b': 'онлайн',
        r'\boffline\b': 'офлайн',
        r'\bchat\b': 'чат',
        r'\bmessage\b': 'сообщение',
        r'\btext\b': 'текст',
        r'\bvoice\b': 'голос',
        r'\bphoto\b': 'фото',
        r'\bpicture\b': 'картинка',
        r'\bimage\b': 'изображение',
        r'\bvideo\b': 'видео',
        r'\bmusic\b': 'музыка',
        r'\bfilm\b': 'фильм',
        r'\bmovie\b': 'кино',
        r'\bshow\b': 'шоу',
        r'\bgame\b': 'игра',
        r'\bplay\b': 'играть',
        r'\bwork\b': 'работать',
        r'\bstudy\b': 'учиться',
        r'\blearn\b': 'учить',
        r'\bknow\b': 'знать',
        r'\bunderstand\b': 'понимать',
        r'\bremember\b': 'помнить',
        r'\bforget\b': 'забывать',
        r'\bthink\b': 'думать',
        r'\bbelieve\b': 'верить',
        r'\bhope\b': 'надеяться',
        r'\bwish\b': 'желать',
        r'\blove\b': 'любить',
        r'\blike\b': 'нравиться',
        r'\bhate\b': 'ненавидеть',
        r'\bfeel\b': 'чувствовать',
        r'\bsee\b': 'видеть',
        r'\blook\b': 'смотреть',
        r'\bwatch\b': 'смотреть',
        r'\blisten\b': 'слушать',
        r'\bhear\b': 'слышать',
        r'\bsay\b': 'сказать',
        r'\btell\b': 'рассказать',
        r'\bspeak\b': 'говорить',
        r'\btalk\b': 'разговаривать',
        r'\bask\b': 'спросить',
        r'\banswer\b': 'ответить',
        r'\bquestion\b': 'вопрос',
        r'\banswer\b': 'ответ',
        r'\bproblem\b': 'проблема',
        r'\bsolution\b': 'решение',
        r'\bidea\b': 'идея',
        r'\bthought\b': 'мысль',
        r'\bfeeling\b': 'чувство',
        r'\bemotion\b': 'эмоция',
        r'\bfriend\b': 'друг',
        r'\bfamily\b': 'семья',
        r'\bpeople\b': 'люди',
        r'\bperson\b': 'человек',
        r'\bman\b': 'мужчина',
        r'\bwoman\b': 'женщина',
        r'\bgirl\b': 'девушка',
        r'\bboy\b': 'парень',
        r'\bchild\b': 'ребёнок',
        r'\bday\b': 'день',
        r'\bnight\b': 'ночь',
        r'\bmorning\b': 'утро',
        r'\bevening\b': 'вечер',
        r'\bafternoon\b': 'день',
        r'\bweek\b': 'неделя',
        r'\bmonth\b': 'месяц',
        r'\byear\b': 'год',
        r'\btoday\b': 'сегодня',
        r'\byesterday\b': 'вчера',
        r'\btomorrow\b': 'завтра',
        r'\bnow\b': 'сейчас',
        r'\bthen\b': 'тогда',
        r'\balways\b': 'всегда',
        r'\bnever\b': 'никогда',
        r'\boften\b': 'часто',
        r'\bsometimes\b': 'иногда',
        r'\busually\b': 'обычно',
        r'\balready\b': 'уже',
        r'\bstill\b': 'всё ещё',
        r'\byet\b': 'ещё',
        r'\balso\b': 'также',
        r'\bas well\b': 'также',
        r'\bthen\b': 'затем',
        r'\bfirst\b': 'сначала',
        r'\bsecond\b': 'второй',
        r'\blast\b': 'последний',
        r'\bnext\b': 'следующий',
        r'\bprevious\b': 'предыдущий',
        r'\banother\b': 'другой',
        r'\bother\b': 'другой',
        r'\bsame\b': 'тот же',
        r'\bdifferent\b': 'разный',
        r'\bspecial\b': 'особенный',
        r'\busual\b': 'обычный',
        r'\bnormal\b': 'нормальный',
        r'\bstrange\b': 'странный',
        r'\bweird\b': 'странный',
        r'\bfunny\b': 'смешной',
        r'\bserious\b': 'серьёзный',
        r'\beasy\b': 'легко',
        r'\bdifficult\b': 'трудно',
        r'\bhard\b': 'трудно',
        r'\bsoft\b': 'мягкий',
        r'\bhight\b': 'высокий',
        r'\blow\b': 'низкий',
        r'\bhot\b': 'горячий',
        r'\bcold\b': 'холодный',
        r'\bwarm\b': 'тёплый',
        r'\bcool\b': 'прохладный',
        r'\bsunny\b': 'солнечно',
        r'\bcloudy\b': 'облачно',
        r'\brainy\b': 'дождливо',
        r'\bwindy\b': 'ветрено',
        r'\bsnowy\b': 'снежно',
    }
    for eng, rus in reps.items():
        text = re.sub(eng, rus, text, flags=re.IGNORECASE)
    
    # Удаляем любые оставшиеся английские слова (состоящие из букв a-z, возможно с дефисом)
    text = re.sub(r'\b[a-zA-Z]+(?:-[a-zA-Z]+)*\b', '', text)
    # Удаляем одиночные английские буквы (которые могли остаться)
    text = re.sub(r'\s+[a-zA-Z]\s+', ' ', text)
    
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def remove_non_russian(text: str) -> str:
    cleaned = re.sub(
        r'[^А-Яа-яЁё\s\d\.,!?:;…\-–—""\'«»()/#@\*\+—\u2700-\u27BF\u1F600-\u1F64F\u1F300-\u1F5FF\u1F680-\u1F6FF\u1F1E0-\u1F1FF\u2600-\u26FF\u2700-\u27BF]',
        '', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def filter_emojis(text: str) -> str:
    allowed = set(SAFE_EMOJIS)
    result = []
    for ch in text:
        if '\U0001F000' <= ch <= '\U0001FFFF' or '\u2600' <= ch <= '\u27BF':
            if ch in allowed:
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)

def distribute_emojis(text: str) -> str:
    text = filter_emojis(text)
    sentences = re.split(r'(?<=[.!?…]) +', text)
    new_sentences = []
    used_safe_emojis = []
    total_emojis = 0
    for s in sentences:
        emojis_in_s = re.findall(
            r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]',
            s)
        if not emojis_in_s:
            available = [e for e in SAFE_EMOJIS if e not in used_safe_emojis]
            if not available:
                available = SAFE_EMOJIS
                used_safe_emojis = []
            chosen = random.choice(available)
            s += ' ' + chosen
            used_safe_emojis.append(chosen)
            total_emojis += 1
        else:
            total_emojis += len(emojis_in_s)
        new_sentences.append(s)
    result = ' '.join(new_sentences)
    if total_emojis < 2:
        available = [e for e in SAFE_EMOJIS if e not in used_safe_emojis]
        if not available:
            available = SAFE_EMOJIS
        for _ in range(2 - total_emojis):
            chosen = random.choice(available)
            result += ' ' + chosen
            used_safe_emojis.append(chosen)
    return result
