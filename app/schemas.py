from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from app.config import settings
from typing import List

# === Audio Track ===
class AudioTrackResponse(BaseModel):
    id: int
    language: Optional[str]
    track_path: Optional[str]

    class Config:
        from_attributes = True

class AudioTrackCreate(BaseModel):
    movie_id: int
    language: Optional[str] = None
    track_path: Optional[str] = None

# === Movie ===
class MovieCreate(BaseModel):
    title: str
    description: Optional[str] = None
    duration: Optional[int] = None
    poster_url: Optional[str] = None
    year: Optional[int] = None
    age_rating: Optional[str] = None

    genre_ids: List[int] = []
    country_ids: List[int] = []
    actor_ids: List[int] = []
    director_ids: List[int] = []
    

class MovieResponse(BaseModel):
    id: int
    title: str
    duration: int
    poster_url: Optional[str] = None
    description: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[str] = None
    country: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    age_rating: Optional[str] = None
    created_at: Optional[datetime] = None
    audio_tracks: list[AudioTrackResponse] = []

    class Config:
        from_attributes = True

    @property
    def poster_url_full(self) -> Optional[str]:
        if self.poster_url:
            return f"{settings.BACKEND_URL}/{self.poster_url}".replace("//", "/").replace(":/", "://")
        return None

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)
        data["poster_url"] = self.poster_url_full
        return data

# === User ===
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    has_subscription: bool
    subscription_expires_at: Optional[datetime]
    is_subscription_active: bool

    @staticmethod
    def from_orm_with_status(user: "User") -> "UserResponse":
        return UserResponse(
            id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            has_subscription=user.has_subscription,
            subscription_expires_at=user.subscription_expires_at,
            is_subscription_active=user.is_subscription_active()
        )

    class Config:
        orm_mode = True

# === Token ===
class Token(BaseModel):
    access_token: str
    token_type: str

# === Match Result ===
class MatchedMovieResponse(BaseModel):
    movie: MovieResponse
    audio_track: AudioTrackResponse
    match: dict  # можно позже типизировать

    class Config:
        from_attributes = True

class UserEmail(BaseModel):
    email: EmailStr

class GenreSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class CountrySchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class ActorSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class DirectorSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True