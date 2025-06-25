# app/routes/custom_admin.py

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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    movie_id: int = Form(...),
    language: str = Form("en"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    from app.utils.peaks import extract_peaks
    from app.utils.fingerprinting import generate_hashes_from_peaks

    MEDIA_DIR = "media/uploads"
    os.makedirs(MEDIA_DIR, exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    path = os.path.join(MEDIA_DIR, unique_filename)
    try:
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error("Ошибка сохранения файла %s: %s", file.filename, e)
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {e}")

    try:
        y, sr = librosa.load(path, sr=16000, mono=True)
        duration = len(y) / sr if y.size > 0 else None

        if duration is None or duration < 1.0:
            logger.error("Аудио слишком короткое или пустое: %.2f сек", duration or 0)
            raise HTTPException(status_code=400, detail="Аудио слишком короткое (<1 сек) или пустое")

        logger.debug("Загружен аудиосигнал: длина=%d, частота=%d Гц", y.size, sr)
        peaks, freqs = extract_peaks(
            y,
            sr,
            normalize=True,
            return_freqs=True,
            frame_size=512,
            hop_size=128,
            min_freq=100.0,
            max_freq=4000.0,
            threshold=0.5
        )
        # Проверка, что peaks и freqs — корректные numpy-массивы
        if not isinstance(peaks, np.ndarray) or not isinstance(freqs, np.ndarray):
            logger.error("peaks или freqs не являются numpy-массивами: peaks=%s, freqs=%s", type(peaks), type(freqs))
            raise HTTPException(status_code=400, detail="Некорректный формат пиков или частот")
        if peaks.size == 0 or freqs.size == 0:
            logger.error("peaks или freqs пусты: peaks_size=%d, freqs_size=%d", peaks.size, freqs.size)
            raise HTTPException(status_code=400, detail="Пустые пики или частоты")
        if peaks.size != freqs.size:
            logger.error("Несоответствие размеров peaks (%d) и freqs (%d)", peaks.size, freqs.size)
            raise HTTPException(status_code=400, detail="Несоответствие размеров пиков и частот")
        logger.debug("Пики (первые 5): %s, Частоты (первые 5): %s", peaks[:5], freqs[:5])
        hashes = generate_hashes_from_peaks(
            peaks,
            freqs=freqs,
            fan_value=18,
            min_delta=0.3,
            max_delta=8.0,
            time_precision=0.05
        )

        logger.info("Длительность аудио: %.2f сек", duration)
        logger.info("Количество пиков: %d", peaks.size)
        logger.info("Количество хешей: %d", len(hashes))
        logger.info("Пример хеша: %s", hashes[0] if hashes else "none")

        if len(hashes) < 5:
            logger.warning("Мало хешей (%d), повторная попытка с fan_value=25", len(hashes))
            peaks, freqs = extract_peaks(
                y,
                sr,
                normalize=True,
                return_freqs=True,
                frame_size=512,
                hop_size=128,
                min_freq=100.0,
                max_freq=4000.0,
                threshold=0.3
            )
            if not isinstance(peaks, np.ndarray) or not isinstance(freqs, np.ndarray):
                logger.error("peaks или freqs не являются numpy-массивами при повторной попытке: peaks=%s, freqs=%s", type(peaks), type(freqs))
                raise HTTPException(status_code=400, detail="Некорректный формат пиков или частот при повторной попытке")
            if peaks.size == 0 or freqs.size == 0:
                logger.error("peaks или freqs пусты при повторной попытке: peaks_size=%d, freqs_size=%d", peaks.size, freqs.size)
                raise HTTPException(status_code=400, detail="Пустые пики или частоты при повторной попытке")
            if peaks.size != freqs.size:
                logger.error("Несоответствие размеров peaks (%d) и freqs (%d) при повторной попытке", peaks.size, freqs.size)
                raise HTTPException(status_code=400, detail="Несоответствие размеров пиков и частот при повторной попытке")
            logger.debug("Пики (повторная попытка, первые 5): %s, Частоты (первые 5): %s", peaks[:5], freqs[:5])
            hashes = generate_hashes_from_peaks(
                peaks,
                freqs=freqs,
                fan_value=25,
                min_delta=0.3,
                max_delta=8.0,
                time_precision=0.05
            )
            logger.info("После повторной попытки: %d хешей", len(hashes))

        if len(hashes) < 5:
            logger.error("Не удалось сгенерировать достаточно хешей: %d", len(hashes))
            raise HTTPException(status_code=400, detail="Не удалось сгенерировать достаточно отпечатков (<5)")
    except Exception as e:
        logger.error("Ошибка обработки аудио %s: %s", file.filename, e)
        raise HTTPException(status_code=400, detail=f"Ошибка обработки аудио: {e}")

    try:
        track = AudioTrack(
            movie_id=movie_id,
            language=language,
            track_path=path,
            duration=duration
        )
        db.add(track)
        db.commit()
        db.refresh(track)

        fingerprints = [
            AudioFingerprint(
                audio_track_id=track.id,
                hash=h,
                offset=float(round(float(offset), 5))
            )
            for h, offset in hashes
        ]
        db.bulk_save_objects(fingerprints)
        db.commit()

        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        if movie and (not movie.duration or movie.duration < duration):
            movie.duration = duration
            db.commit()

        logger.info("Сохранено %d хешей для аудиодорожки ID=%d", len(hashes), track.id)
    except Exception as e:
        logger.error("Ошибка сохранения в базу данных: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения в базу данных: {e}")
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning("Ошибка удаления файла %s: %s", path, e)

    return RedirectResponse("/admin/audio-track/list", status_code=302)
