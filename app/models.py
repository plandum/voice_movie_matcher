from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.mysql import BINARY

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Movie(Base):
    __tablename__ = "movies"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    duration = Column(Integer)
    fingerprint_hash = Column(String(64), unique=True)
    created_at = Column(TIMESTAMP)

class AudioFingerprint(Base):
    __tablename__ = "audio_fingerprints"
    id = Column(Integer, primary_key=True, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    hash = Column(Integer)
    timestamp = Column(Integer, nullable=False)
