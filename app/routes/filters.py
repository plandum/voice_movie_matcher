from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/filters", tags=["Фильтры"])

@router.get("/genres", response_model=List[schemas.GenreSchema])
def get_genres(db: Session = Depends(get_db)):
    return db.query(models.Genre).all()

@router.get("/countries", response_model=List[schemas.CountrySchema])
def get_countries(db: Session = Depends(get_db)):
    return db.query(models.Country).all()

@router.get("/actors", response_model=List[schemas.ActorSchema])
def get_actors(db: Session = Depends(get_db)):
    return db.query(models.Actor).all()

@router.get("/directors", response_model=List[schemas.DirectorSchema])
def get_directors(db: Session = Depends(get_db)):
    return db.query(models.Director).all()
