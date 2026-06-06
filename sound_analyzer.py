import torch
import numpy as np
import tensorflow_hub as hub
import tensorflow as tf
from scipy.io import wavfile
from silero_vad import load_silero_vad, get_speech_timestamps
import tempfile
import os
from typing import List, Tuple, Optional

# ---------- Глобальная загрузка моделей (один раз) ----------
print("[SoundAnalyzer] Загрузка YAMNet...")
yamnet_model = hub.load('https://tfhub.dev/google/yamnet/1')
print("[SoundAnalyzer] YAMNet загружена.")

print("[SoundAnalyzer] Загрузка Silero VAD...")
vad_model = load_silero_vad()
print("[SoundAnalyzer] Silero VAD загружена.")

# Классы YAMNet, которые мы НЕ считаем «фоновым звуком» (речь человека)
SPEECH_CLASSES = {
    'Speech', 'Child speech, kid speaking', 'Conversation', 'Narration, monologue',
    'Male speech, man speaking', 'Female speech, woman speaking', 'Whispering'
}

# ---------- Функции ----------
def _audio_bytes_to_array(audio_bytes: bytes, target_sr: int = 16000) -> np.ndarray:
    """Конвертирует байты аудио (WAV) в numpy массив с целевой частотой."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    sr, audio = wavfile.read(tmp_path)
    os.unlink(tmp_path)
    if sr != target_sr:
        # Простейший ресемплинг через scipy (можно добавить позже)
        # Пока предполагаем, что аудио уже 16 kHz (Telegram voice)
        pass
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32) / 32768.0
    return audio

def vad_has_speech(audio_bytes: bytes, threshold: float = 0.5) -> bool:
    """
    Проверяет, есть ли в аудио человеческая речь (Silero VAD).
    Возвращает True, если речь есть.
    """
    try:
        audio = _audio_bytes_to_array(audio_bytes, 16000)
        # Silero VAD ожидает тензор [batch, samples]
        audio_tensor = torch.from_numpy(audio).unsqueeze(0)
        speech_timestamps = get_speech_timestamps(audio_tensor, vad_model, threshold=threshold)
        return len(speech_timestamps) > 0
    except Exception as e:
        print(f"[VAD] Ошибка: {e}")
        return True   # на всякий случай считаем, что речь есть

def classify_sounds(audio_bytes: bytes, top_k: int = 3, ignore_speech: bool = True) -> List[Tuple[str, float]]:
    """
    Анализирует аудио через YAMNet, возвращает список (название_звука, вероятность).
    Если ignore_speech=True, исключает классы речи (чтобы не путать с фоном).
    """
    try:
        audio = _audio_bytes_to_array(audio_bytes, 16000)
        # YAMNet ожидает [samples] и частоту 16k
        scores, embeddings, spectrogram = yamnet_model(audio)
        # Усредняем по времени
        mean_scores = scores.numpy().mean(axis=0)
        # Получаем классы
        class_names = yamnet_model.class_names()
        top_indices = np.argsort(mean_scores)[-top_k:][::-1]
        results = []
        for idx in top_indices:
            score = float(mean_scores[idx])
            name = class_names[idx].decode('utf-8') if isinstance(class_names[idx], bytes) else class_names[idx]
            if ignore_speech and name in SPEECH_CLASSES:
                continue
            results.append((name, score))
        return results
    except Exception as e:
        print(f"[SoundAnalyzer] Ошибка: {e}")
        return []
