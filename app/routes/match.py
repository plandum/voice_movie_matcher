from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import uuid
import tempfile
import shutil
import mimetypes
import logging
import numpy as np
import librosa
import soundfile as sf
from collections import Counter, defaultdict
from app.database import get_db
from app.models import AudioTrack, AudioFingerprint
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks
from app.utils.fingerprinting import generate_hashes_from_peaks
from scipy.signal import butter, lfilter

logger = logging.getLogger("app.routes.match")
MEDIA_DIR = "media"

router = APIRouter()

def _as_float(x):
    return round(float(x), 2)


def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a


def bandpass_filter(data, lowcut=100.0, highcut=4000.0, fs=16000, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    return lfilter(b, a, data)

@router.post("/match/audio")
async def match_audio(
    file: UploadFile = File(...),
    movie_id: int = Form(...),
    language: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Принимает аудиофрагмент и возвращает приблизительное и уточнённое смещение внутри аудиодорожки фильма.
    """
    fragment_path = None
    audio_path = None
    try:
        # Сохранение фрагмента
        os.makedirs(MEDIA_DIR, exist_ok=True)
        fragment_path = os.path.join(MEDIA_DIR, f"frag_{movie_id}_{uuid.uuid4().hex}.tmp")
        with open(fragment_path, "wb") as out_f:
            shutil.copyfileobj(file.file, out_f)

        # Конвертация в WAV при необходимости
        mime_type, _ = mimetypes.guess_type(fragment_path)
        audio_path = fragment_path
        if mime_type != "audio/wav" and not fragment_path.endswith(".wav"):
            audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)

        # Загрузка метаданных дорожки
        track = (
            db.query(AudioTrack)
              .filter(AudioTrack.movie_id == movie_id)
              .filter(AudioTrack.language.ilike(language))
              .first()
        )
        if not track:
            raise HTTPException(status_code=404, detail=f"Аудиодорожка не найдена для фильма {movie_id}, язык '{language}'")

        # Загрузка и фильтрация фрагмента
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        fragment_duration = len(y) / sr
        y = bandpass_filter(y, lowcut=100.0, highcut=4000.0, fs=sr)

        # Извлечение пиков и генерация хешей
        peaks, freqs, _ = extract_peaks(
            y, sr,
            normalize=True,
            return_freqs=True,
            return_amplitudes=False,
            frame_size=2048,
            hop_size=256,
            min_freq=100.0,
            max_freq=4000.0,
            threshold=0.8,
            absolute_threshold=0.2,
            max_peaks=800
        )
        hashes = [
            (h, _as_float(t1))
            for h, t1 in generate_hashes_from_peaks(
                peaks,
                freqs=freqs,
                amplitudes=None,
                fan_value=10,
                min_delta=0.5,
                max_delta=6.0,
                time_precision=0.01,
                target_density=80.0,
                max_hashes=200000
            )
        ]
        if len(hashes) < 5:
            raise HTTPException(status_code=400, detail="Недостаточно хешей для анализа (<5)")

        # Загрузка отпечатков из БД
        db_fps = (
            db.query(AudioFingerprint.hash, AudioFingerprint.offset)
              .filter(AudioFingerprint.audio_track_id == track.id)
              .filter(AudioFingerprint.hash.in_([h for h, _ in hashes]))
              .all()
        )
        if not db_fps:
            raise HTTPException(status_code=404, detail="Отпечатки для аудиодорожки отсутствуют")

        # Группировка по хешу
        fps_dict = defaultdict(list)
        for h_db, off in db_fps:
            fps_dict[h_db].append(off)

        # Подсчёт дельт
        DELTA_TOLERANCE = 0.02
        counts = Counter()
        for h, t1 in hashes:
            for t2 in fps_dict.get(h, []):
                delta = t2 - t1
                bin_delta = round(delta / DELTA_TOLERANCE) * DELTA_TOLERANCE
                counts[round(bin_delta, 3)] += 1
        if not counts:
            raise HTTPException(status_code=404, detail="Совпадений не найдено")

        # Выбор лучшего смещения
        best_offset = max(counts, key=counts.get)
        match_score = counts[best_offset]
        total_checked = len(hashes)
        raw_confidence = round(min(match_score / total_checked, 1.0) * 100, 2)

        # Уточнение смещения через кросс-корреляцию
        refined_offset = best_offset
        corr_confidence = None
        try:
            start_sample = max(0, int(best_offset * sr))
            n_samples = len(y)
            segment, _ = sf.read(track.track_path, start=start_sample, frames=n_samples, dtype='float32')
            if len(segment) < n_samples:
                segment = np.pad(segment, (0, n_samples - len(segment)), mode='constant')
            corr = np.correlate(y, segment, mode='full')
            lag = np.argmax(corr) - (n_samples - 1)
            delta_sec = lag / sr
            refined_offset = best_offset + delta_sec
            norm_corr = corr.max() / np.sqrt(np.dot(y, y) * np.dot(segment, segment))
            corr_confidence = round(norm_corr * 100, 2)
        except Exception as e:
            logger.warning(f"Refinement failed: {e}")

        # Лог и возврат
        logger.info(
            f"[match] movie_id={movie_id}, raw_offset={best_offset}s, score={match_score}, "
            f"raw_confidence={raw_confidence}%, refined_offset={refined_offset}s, "
            f"corr_confidence={corr_confidence}%"
        )

        # Проверка валидности
        track_duration = getattr(track, 'duration', None)
        if track_duration is not None:
            valid_offset = 0 <= refined_offset <= (track_duration - fragment_duration)
        else:
            valid_offset = True

        return {
            "audio_track": {"id": track.id, "language": track.language},
            "match": {
                "raw_offset": float(best_offset),
                "raw_confidence": raw_confidence,
                "refined_offset": float(refined_offset),
                "corr_confidence": corr_confidence,
                "score": int(match_score),
                "total_checked": total_checked,
                "valid_offset": valid_offset
            }
        }
    finally:
        # Удаление временных файлов
        for path in (fragment_path, audio_path):
            try:
                if path and os.path.exists(path) and path.startswith(MEDIA_DIR):
                    os.remove(path)
            except Exception:
                logger.warning(f"Cannot delete temp file {path}")