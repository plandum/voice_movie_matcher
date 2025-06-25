from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, DateTime, func, Boolean, Table, Float
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


movie_genres = Table(
    "movie_genres", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE")),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="CASCADE"))
)

movie_countries = Table(
    "movie_countries", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE")),
    Column("country_id", Integer, ForeignKey("countries.id", ondelete="CASCADE"))
)

movie_actors = Table(
    "movie_actors", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE")),
    Column("actor_id", Integer, ForeignKey("actors.id", ondelete="CASCADE"))
)

movie_directors = Table(
    "movie_directors", Base.metadata,
    Column("movie_id", Integer, ForeignKey("movies.id", ondelete="CASCADE")),
    Column("director_id", Integer, ForeignKey("directors.id", ondelete="CASCADE"))
)

class Genre(Base):
    __tablename__ = "genres"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_genres, back_populates="genres")

    def __str__(self):
        return self.name

class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_countries, back_populates="countries")

    def __str__(self):
        return self.name

class Actor(Base):
    __tablename__ = "actors"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_actors, back_populates="actors")

    def __str__(self):
        return self.name

class Director(Base):
    __tablename__ = "directors"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)

    movies = relationship("Movie", secondary=movie_directors, back_populates="directors")
    
    def __str__(self):
        return self.name




class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, unique=True)
    duration = Column(Integer, nullable=True)
    poster_url = Column(String(255), nullable=True)       # ➕ путь к постеру
    description = Column(String(1000), nullable=True)
    year = Column(Integer, nullable=True)
    age_rating = Column(String(10), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    genres = relationship("Genre", secondary=movie_genres, back_populates="movies")
    countries = relationship("Country", secondary=movie_countries, back_populates="movies")
    actors = relationship("Actor", secondary=movie_actors, back_populates="movies")
    directors = relationship("Director", secondary=movie_directors, back_populates="movies")

    def __str__(self):
        return self.title

    # связь с аудиодорожками
    audio_tracks = relationship(
        "AudioTrack",
        backref="movie",
        cascade="all, delete-orphan"
    )

class AudioTrack(Base):
    __tablename__ = "audio_tracks"

    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(50), nullable=True)  # например, "en", "ru", "es"
    track_path = Column(String(255), nullable=True)  # путь к аудиофайлу
    duration = Column(Float, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # связь с фингерпринтами
    fingerprints = relationship(
        "AudioFingerprint",
        backref="audio_track",
        cascade="all, delete-orphan"
    )

    def __str__(self):
        return self.language

class AudioFingerprint(Base):
    __tablename__ = "audio_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    audio_track_id = Column(Integer, ForeignKey("audio_tracks.id", ondelete="CASCADE"), nullable=False)
    hash = Column(String(16), nullable=False)  # хэш в виде hex (можно и BIGINT если хочешь int)
    offset = Column(Float, nullable=False)     # смещение (в секундах)



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    verification_code = Column(String(6), nullable=True)
    code_generated_at = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    has_subscription = Column(Boolean, default=False, nullable=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def is_subscription_active(self) -> bool:
        return (
            self.has_subscription
            and self.subscription_expires_at is not None
            and self.subscription_expires_at > datetime.utcnow()
        )
