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
    description: str = Form(None),
    poster_url: str = Form(None),
    language: str = Form("unknown"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Проверка: фильм с таким названием уже существует
    existing_movie = db.query(models.Movie).filter_by(title=title).first()
    if existing_movie:
        raise HTTPException(status_code=400, detail="Фильм с таким названием уже существует")

    # Сохраняем видеофайл
    video_path = os.path.join(MEDIA_DIR, file.filename)
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Извлекаем аудиофайл
    try:
        audio_path = extract_audio_from_video(video_path, MEDIA_DIR)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудио: {e}")

    # Обработка аудио
    try:
        y, sr = librosa.load(audio_path, sr=None)
        peak_times = extract_peaks(y, sr)
        duration = round(librosa.get_duration(y=y, sr=sr), 2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения пиков: {e}")

    if not peak_times:
        raise HTTPException(status_code=400, detail="Пики не найдены в аудиодорожке")

    # Создаём фильм
    movie = models.Movie(
        title=title,
        duration=duration,
        description=description,
        poster_url=poster_url
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)

    # Создание аудиодорожки
    track = models.AudioTrack(
        movie_id=movie.id,
        language=language,
        track_path=audio_path
    )
    db.add(track)
    db.commit()
    db.refresh(track)

    # Сохраняем фингерпринты
    unique_peaks = sorted(set(round_time(t) for t in peak_times))
    for t in unique_peaks:
        db.add(models.AudioFingerprint(audio_track_id=track.id, timestamp=t))

    db.commit()

    return movie
