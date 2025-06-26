from fastapi import APIRouter, Request, status, Form, UploadFile, File, Depends, HTTPException
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from sqladmin import Admin
from app.admin import admin_instance
import os
import sqladmin
from app.config import settings
from app.database import get_db, SessionLocal
from sqlalchemy.orm import Session
from app import models
import shutil
import uuid
from app.models import Genre, Country, Actor, Director, AudioTrack, AudioFingerprint, Movie
import hashlib
from typing import List
import logging
import mimetypes
import librosa
import numpy as np
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks
from app.utils.fingerprinting import generate_hashes_from_peaks
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MEDIA_DIR = "media"

def _as_float(x):
    return round(float(x), 2)

templates = Jinja2Templates(
    directory=[
        "app/templates",
        os.path.join(os.path.dirname(sqladmin.__file__), "templates")
    ]
)

router = APIRouter()

@router.get("/admin/movies/new", response_class=HTMLResponse)
async def show_form(request: Request, db: Session = Depends(get_db)):
    genres = db.query(Genre).order_by(Genre.name).all()
    countries = db.query(Country).order_by(Country.name).all()
    actors = db.query(Actor).order_by(Actor.name).all()
    directors = db.query(Director).order_by(Director.name).all()
    return templates.TemplateResponse("admin/movie_upload_form.html", {
        "request": request,
        "admin": admin_instance,
        "genres": genres,
        "countries": countries,
        "actors": actors,
        "directors": directors
    })

@router.post("/admin/movies/new")
async def handle_upload(
    title: str = Form(...),
    description: str = Form(None),
    age_rating: str = Form(None),
    genre_ids: list[int] = Form([]),
    country_ids: list[int] = Form([]),
    actor_ids: list[int] = Form([]),
    director_ids: list[int] = Form([]),
    poster: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    existing_movie = db.query(models.Movie).filter_by(title=title).first()
    if existing_movie:
        raise HTTPException(status_code=400, detail="Фильм с таким названием уже существует")

    poster_url = None
    if poster:
        os.makedirs("media/posters", exist_ok=True)
        ext = os.path.splitext(poster.filename)[1]
        generated_name = f"{uuid.uuid4().hex}{ext}"
        poster_path = os.path.join("media/posters", generated_name)
        with open(poster_path, "wb") as f:
            shutil.copyfileobj(poster.file, f)
        poster_url = poster_path

    genres = db.query(Genre).filter(Genre.id.in_(genre_ids)).all()
    countries = db.query(Country).filter(Country.id.in_(country_ids)).all()
    actors = db.query(Actor).filter(Actor.id.in_(actor_ids)).all()
    directors = db.query(Director).filter(Director.id.in_(director_ids)).all()
        
    movie = models.Movie(
        title=title,
        description=description,
        age_rating=age_rating,
        poster_url=poster_url,
        genres=genres,
        countries=countries,
        actors=actors,
        directors=directors
    )

    db.add(movie)
    db.commit()
    db.refresh(movie)

    return RedirectResponse("/admin/movie/list", status_code=status.HTTP_302_FOUND)

@router.get("/admin/audio-track/new", response_class=HTMLResponse)
async def show_audio_track_form(request: Request):
    from app.models import Movie
    from app.database import SessionLocal
    from app.admin import admin_instance

    db = SessionLocal()
    movies = db.query(Movie).order_by(Movie.title).all()
    db.close()

    return templates.TemplateResponse("admin/upload_track.html", {
        "request": request,
        "admin": admin_instance,
        "movies": movies
    })

@router.post("/admin/audio-track/new")
async def handle_audio_track_upload(
    file: UploadFile = File(...),
    movie_id: int = Form(...),
    language: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Обрабатывает загрузку аудиодорожки, извлекает отпечатки и сохраняет их в базе данных.

    Args:
        file (UploadFile): Загруженный аудио- или видеофайл.
        movie_id (int): ID фильма.
        language (str): Язык аудиодорожки.
        db (Session): Сессия базы данных.

    Returns:
        dict: Информация о сохранённой аудиодорожке.
    """
    logger.debug("Логирование DEBUG включено для handle_audio_track_upload")

    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        file_extension = os.path.splitext(file.filename)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(suffix=file_extension, dir=MEDIA_DIR, delete=False) as temp_file:
            track_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
    except Exception as e:
        logger.error("Ошибка сохранения файла: %s", e)
        raise HTTPException(500, f"Ошибка сохранения файла: {e}")

    mime_type, _ = mimetypes.guess_type(track_path)
    is_wav = mime_type == "audio/wav" or track_path.endswith(".wav")
    audio_path = track_path

    if not is_wav:
        try:
            audio_path = extract_audio_from_video(track_path, MEDIA_DIR)
        except Exception as e:
            logger.error("Ошибка извлечения аудио: %s", e)
            raise HTTPException(500, f"Ошибка извлечения аудио: {e}")

    try:
        track = AudioTrack(movie_id=movie_id, language=language, track_path=audio_path)
        db.add(track)
        db.commit()
        db.refresh(track)
    except Exception as e:
        logger.error("Ошибка сохранения AudioTrack: %s", e)
        raise HTTPException(500, f"Ошибка сохранения AudioTrack: {e}")

    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        track_duration = len(y) / sr
        if track_duration < 0.5:
            logger.warning("Аудиодорожка слишком короткая: %.2f сек", track_duration)
            raise HTTPException(400, "Аудиодорожка слишком короткая (<0.5 сек)")
        if y is None or len(y) == 0:
            logger.error("Ошибка чтения аудиофайла: пустой сигнал")
            raise HTTPException(400, "Ошибка чтения аудиофайла: пустой сигнал")

        peaks, freqs, amplitudes = extract_peaks(
            y, sr,
            normalize=True,
            return_freqs=True,
            return_amplitudes=True,
            frame_size=1024,
            hop_size=256,
            min_freq=100.0,
            max_freq=4000.0,
            threshold=0.6
        )
        if not isinstance(peaks, np.ndarray) or not isinstance(freqs, np.ndarray) or not isinstance(amplitudes, np.ndarray):
            logger.error("peaks, freqs или amplitudes не являются numpy-массивами: peaks=%s, freqs=%s, amplitudes=%s", type(peaks), type(freqs), type(amplitudes))
            raise HTTPException(400, detail="Некорректный формат пиков, частот или амплитуд")
        if peaks.size == 0 or freqs.size == 0 or amplitudes.size == 0:
            logger.error("peaks, freqs или amplitudes пусты: peaks_size=%d, freqs_size=%d, amplitudes_size=%d", peaks.size, freqs.size, amplitudes.size)
            raise HTTPException(400, detail="Пустые пики, частоты или амплитуды")
        if peaks.size != freqs.size or peaks.size != amplitudes.size:
            logger.error("Несоответствие размеров: peaks (%d), freqs (%d), amplitudes (%d)", peaks.size, freqs.size, amplitudes.size)
            raise HTTPException(400, detail="Несоответствие размеров пиков, частот или амплитуд")
        logger.debug("Пики (первые 5): %s, Частоты (первые 5): %s, Амплитуды (первые 5): %s", peaks[:5], freqs[:5], amplitudes[:5])
        hashes = [(h, _as_float(t1)) for h, t1 in generate_hashes_from_peaks(
            peaks, freqs=freqs, amplitudes=None, fan_value=15, min_delta=0.5, max_delta=8.0, time_precision=0.05
        )]
        logger.info("Длительность аудиодорожки: %.2f сек", track_duration)
        logger.info("Количество пиков: %d", len(peaks))
        logger.info("Количество хешей: %d", len(hashes))
        logger.info("Пример хеша: %s", hashes[0] if hashes else "none")
        if len(hashes) < 5:
            logger.warning("Слишком мало хешей для анализа: %d", len(hashes))
            raise HTTPException(400, "Слишком мало хешей для анализа (<5)")
    except Exception as e:
        logger.error("Ошибка обработки аудио: %s", e)
        raise HTTPException(500, f"Ошибка обработки аудио: {e}")

    try:
        fingerprints = [
            AudioFingerprint(audio_track_id=track.id, hash=h, offset=t1)
            for h, t1 in hashes
        ]
        db.bulk_save_objects(fingerprints)
        db.commit()
        logger.info("Сохранено %d хешей для аудиодорожки ID=%d", len(fingerprints), track.id)
    except Exception as e:
        logger.error("Ошибка сохранения отпечатков: %s", e)
        raise HTTPException(500, f"Ошибка сохранения отпечатков: {e}")
    finally:
        try:
            if os.path.exists(track_path) and track_path != audio_path:
                os.remove(track_path)
            if not is_wav and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            logger.warning("Ошибка удаления временных файлов: %s", e)

    return {
        "id": track.id,
        "movie_id": track.movie_id,
        "language": track.language,
        "track_path": track.track_path,
        "hashes_saved": len(fingerprints)
    }