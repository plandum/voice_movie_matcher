import os
import shutil
import hashlib
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

import librosa
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models, schemas
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks

router = APIRouter(prefix="/admin", tags=["admin"])

MEDIA_DIR = "media/uploads"
os.makedirs(MEDIA_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def round_time(t: float) -> float:
    return float(Decimal(str(t)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def compute_peak_hash(peaks: list[float]) -> str:
    joined = ",".join(f"{round(p, 2)}" for p in peaks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@router.post("/upload_video", response_model=schemas.MovieResponse)
def upload_video(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Сохраняем видеофайл
    video_path = os.path.join(MEDIA_DIR, file.filename)
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Извлекаем аудиофайл
    try:
        audio_path = extract_audio_from_video(video_path, MEDIA_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудио: {e}")

    # Загружаем аудио и извлекаем пики
    try:
        y, sr = librosa.load(audio_path, sr=None)
        peak_times = extract_peaks(y, sr)
        duration = round(librosa.get_duration(y=y, sr=sr), 2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения пиков: {e}")

    if not peak_times:
        raise HTTPException(status_code=400, detail="Пики не найдены в аудиодорожке")

    # Проверка на дубликаты
    peak_hash = compute_peak_hash(peak_times)
    existing = db.query(models.Movie).filter_by(fingerprint_hash=peak_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="Такой аудиофайл уже загружен ранее")

    # Сохраняем фильм
    movie = models.Movie(
        title=title,
        duration=duration,
        fingerprint_hash=peak_hash
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)

    # Сохраняем только уникальные пики
    unique_peaks = sorted(set(round_time(t) for t in peak_times))
    for t in unique_peaks:
        db.add(models.AudioFingerprint(movie_id=movie.id, timestamp=t))


    db.commit()

    return movie
