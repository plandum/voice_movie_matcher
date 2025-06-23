from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models

router = APIRouter(prefix="/movies", tags=["movies"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def list_movies(db: Session = Depends(get_db)):
    movies = db.query(models.Movie).all()
    return [
        {
            "id": movie.id,
            "title": movie.title,
            "description": movie.description,
            "poster_url": movie.poster_url,
            "duration": movie.duration,
            "countries": [{"id": c.id, "name": c.name} for c in movie.countries],
            "year": movie.year,
        }
        for movie in movies
    ]

@router.get("/{movie_id}")
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if not movie:
        return {"error": "Фильм не найден"}

    return {
        "id": movie.id,
        "title": movie.title,
        "description": movie.description,
        "poster_url": movie.poster_url,
        "duration": movie.duration,
        "year": movie.year,
        "age_rating": movie.age_rating,
        "genres": [{"id": g.id, "name": g.name} for g in movie.genres],
        "countries": [{"id": c.id, "name": c.name} for c in movie.countries],
        "actors": [{"id": a.id, "name": a.name} for a in movie.actors],
        "directors": [{"id": d.id, "name": d.name} for d in movie.directors],
        "audio_tracks": [
            {
                "id": track.id,
                "language": track.language,
                "track_path": track.track_path,
            }
            for track in movie.audio_tracks
        ]
    }


