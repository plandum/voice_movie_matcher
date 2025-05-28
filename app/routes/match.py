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
    # Сохраняем файл
    fragment_path = os.path.join(MEDIA_DIR, file.filename)
    with open(fragment_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Извлекаем аудио
    try:
        audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудио: {e}")

    # Генерируем пики
    try:
        y, sr = librosa.load(audio_path, sr=None)
        fragment_peaks = extract_peaks(y, sr)
        if len(fragment_peaks) < 10:
            raise HTTPException(status_code=400, detail="Слишком мало пиков для анализа")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации пиков: {e}")

    # Получаем все пики из базы
    db_peaks = db.query(models.AudioFingerprint.movie_id, models.AudioFingerprint.timestamp).all()
    if not db_peaks:
        raise HTTPException(status_code=404, detail="В базе нет отпечатков")

    # Сравнение
    offsets = []
    for movie_id, db_ts in db_peaks:
        for frag_ts in fragment_peaks:
            offset = round(float(db_ts) - float(frag_ts), 1)
            offsets.append((movie_id, offset))

    if not offsets:
        raise HTTPException(status_code=404, detail="Совпадений не найдено")

    counter = Counter(offsets)
    (best_movie_id, best_offset), match_score = counter.most_common(1)[0]
    total_checked = len(fragment_peaks)
    confidence = round(min(match_score, total_checked) / total_checked * 100, 2)


    movie = db.query(models.Movie).filter(models.Movie.id == best_movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Фильм не найден")

    valid_offset = 0 <= best_offset <= movie.duration

    return {
        "movie_id": best_movie_id,
        "match_offset": round(best_offset, 2),
        "match_score": match_score,
        "total_checked": total_checked,
        "confidence": confidence,
        "duration": movie.duration,
        "title": movie.title,
        "valid_offset": valid_offset
    }