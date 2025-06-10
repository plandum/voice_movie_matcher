from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, DateTime, func, Boolean
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, unique=True)
    duration = Column(Integer, nullable=True)
    poster_url = Column(String(255), nullable=True)       # ➕ путь к постеру
    description = Column(String(1000), nullable=True)
    created_at = Column(TIMESTAMP)

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
    created_at = Column(TIMESTAMP, server_default=func.now())

    # связь с фингерпринтами
    fingerprints = relationship(
        "AudioFingerprint",
        backref="audio_track",
        cascade="all, delete-orphan"
    )

class AudioFingerprint(Base):
    __tablename__ = "audio_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    audio_track_id = Column(Integer, ForeignKey("audio_tracks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(Integer, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
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
