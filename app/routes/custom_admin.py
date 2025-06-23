from fastapi import APIRouter, Request, status, Form, UploadFile, File, Depends
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from sqladmin import Admin
from app.admin import admin_instance
import httpx
import os
import sqladmin
from app.config import settings
from app.database import get_db, SessionLocal
from sqlalchemy.orm import Session
from app import models
import shutil
import uuid
from app.models import Genre, Country, Actor, Director, AudioTrack, AudioFingerprint, Movie


from typing import List

from typing import List, Tuple
import hashlib


templates = Jinja2Templates(
    directory=[
        "app/templates",  # твои шаблоны
        os.path.join(os.path.dirname(sqladmin.__file__), "templates")
    ]
)

router = APIRouter()

@router.get("/admin/movies/new", response_class=HTMLResponse)
async def show_form(request: Request, db: Session = Depends(get_db)):
    from app.admin import admin_instance

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
    request: Request,
    movie_id: int = Form(...),
    language: str = Form("unknown"),
    file: UploadFile = File(...)
):
    import librosa
    import numpy as np
    from app.utils.peaks import extract_peaks
    from app.utils.fingerprinting import generate_hashes_from_peaks
    import shutil, uuid, os

    MEDIA_DIR = "media/uploads"
    os.makedirs(MEDIA_DIR, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    path = os.path.join(MEDIA_DIR, unique_filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        y, sr = librosa.load(path, sr=16000, mono=True)
        print("max(y):", np.max(np.abs(y)))
        if np.max(np.abs(y)) > 0:
            y = y / np.max(np.abs(y))
        peaks = extract_peaks(y, sr, frame_size=512, hop_size=128, threshold=0.1)
        hashes = generate_hashes_from_peaks(peaks, fan_value=15)

        duration = round(len(y) / sr)
    except Exception as e:
        print("Ошибка анализа аудио:", e)
        return HTMLResponse(f"<h3>Ошибка анализа аудио: {e}</h3>", status_code=400)

    db = SessionLocal()
    try:
        track = AudioTrack(
            movie_id=movie_id,
            language=language,
            track_path=path
        )
        db.add(track)
        db.commit()
        db.refresh(track)

        for h, offset in hashes:
            db.add(AudioFingerprint(audio_track_id=track.id, hash=h, offset=offset))
        db.commit()

        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        if movie and (not movie.duration or movie.duration < duration):
            movie.duration = duration
            db.commit()
    finally:
        db.close()
        print(f"Сохраняем {len(hashes)} хешей для аудиотрека")
        print("Пример хеша:", hashes[0] if hashes else "none")
        print("PEAKS UPLOAD:", peaks[:5])
        print("sr (upload):", sr, "len(y):", len(y))

    return RedirectResponse("/admin/audio-track/list", status_code=302)
