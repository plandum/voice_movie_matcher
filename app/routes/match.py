import os
import shutil
from collections import defaultdict, Counter
from decimal import Decimal, ROUND_HALF_UP

import librosa
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import SessionLocal
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks
from app import models

import mimetypes
import logging

logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/match", tags=["match"])

MEDIA_DIR = "media/fragments"
os.makedirs(MEDIA_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/audio")
def match_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    logging.info("===> Начали обработку файла")
    # Сохраняем файл
    fragment_path = os.path.join(MEDIA_DIR, file.filename)
    with open(fragment_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logging.info(f"Сохранили файл: {fragment_path}")

    # Определяем MIME-тип (по расширению)
    mime_type, _ = mimetypes.guess_type(fragment_path)

    is_wav = (mime_type == 'audio/wav') or fragment_path.lower().endswith('.wav')

    if is_wav:
        audio_path = fragment_path
        logging.info("Файл уже является .wav, пропускаем извлечение аудио")
    else:
        try:
            audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)
            logging.info(f"Аудио извлечено: {audio_path}")
        except Exception as e:
            logging.error(f"Ошибка при извлечении аудио: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудио: {e}")

    # Извлекаем аудио
    # try:
    #     audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)
    #     logging.info(f"Аудио извлечено: {audio_path}")
    # except Exception as e:
    #     logging.error(f"Ошибка при извлечении аудио: {e}")
    #     raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудио: {e}")
    

    # Генерируем пики
    try:
        y, sr = librosa.load(audio_path, sr=None)
        logging.info(f"Аудио загружено: длина={len(y)}, sr={sr}")
        fragment_peaks = extract_peaks(y, sr)
        logging.info(f"Найдено пиков: {len(fragment_peaks)}")
        if len(fragment_peaks) < 10:
            raise HTTPException(status_code=400, detail="Слишком мало пиков для анализа")
    except Exception as e:
        logging.error(f"Ошибка при генерации пиков: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации пиков: {e}")

    # Получаем все пики из базы с track_id и movie_id
    db_peaks = (
        db.query(
            models.AudioFingerprint.audio_track_id,
            models.AudioFingerprint.timestamp,
            models.AudioTrack.movie_id
        )
        .join(models.AudioTrack, models.AudioFingerprint.audio_track_id == models.AudioTrack.id)
        .all()
    )

    if not db_peaks:
        raise HTTPException(status_code=404, detail="В базе нет отпечатков")

    # Сравнение по смещениям
    offsets = []
    for track_id, db_ts, movie_id in db_peaks:
        for frag_ts in fragment_peaks:
            offset = round(float(db_ts) - float(frag_ts), 1)
            offsets.append(((track_id, movie_id, offset)))

    if not offsets:
        raise HTTPException(status_code=404, detail="Совпадений не найдено")

    counter = Counter(offsets)
    (best_track_id, best_movie_id, best_offset), match_score = counter.most_common(1)[0]
    total_checked = len(fragment_peaks)
    confidence = round(min(match_score, total_checked) / total_checked * 100, 2)

    # Получаем объекты
    track = db.query(models.AudioTrack).filter(models.AudioTrack.id == best_track_id).first()
    movie = db.query(models.Movie).filter(models.Movie.id == best_movie_id).first()

    if not track or not movie:
        raise HTTPException(status_code=404, detail="Фильм или дорожка не найдены")

    valid_offset = 0 <= best_offset <= (movie.duration or 0)

    return {
        "movie": {
            "id": movie.id,
            "title": movie.title,
            "duration": movie.duration,
            "poster_url": movie.poster_url,
            "description": movie.description,
        },
        "audio_track": {
            "id": track.id,
            "language": track.language,
            "track_path": track.track_path,
        },
        "match": {
            "offset": round(best_offset, 2),
            "score": match_score,
            "total_checked": total_checked,
            "confidence": confidence,
            "valid_offset": valid_offset,
        }
    }
