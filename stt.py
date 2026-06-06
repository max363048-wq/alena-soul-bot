# stt.py — временный тест

def speech_to_text(audio_bytes, lang='ru'):
    print("TEST: speech_to_text вызвана")
    return "привет Алена, тестовый текст"

def speech_to_text_with_sounds(audio_bytes, lang='ru'):
    print("TEST: speech_to_text_with_sounds вызвана")
    return "привет Алена, тестовый текст", []

def classify_sounds_remote(audio_bytes):
    return []

def process_voice_message(message, bot, lang, pet_name):
    return True
