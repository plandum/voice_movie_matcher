from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import Counter, defaultdict
import os, shutil, mimetypes, librosa, numpy as np

from app.database import SessionLocal
from app.models import AudioFingerprint, AudioTrack, Movie
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks
from app.utils.fingerprinting import generate_hashes_from_peaks

router = APIRouter(prefix="/match", tags=["match"])
MEDIA_DIR = "media/fragments"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _as_float(val):
    try:
        return round(float(val), 5)
    except Exception:
        return float(val)

@router.post("/audio")
def match_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    fragment_path = os.path.join(MEDIA_DIR, file.filename)
    os.makedirs(os.path.dirname(fragment_path), exist_ok=True)
    with open(fragment_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    mime_type, _ = mimetypes.guess_type(fragment_path)
    is_wav = mime_type == "audio/wav" or fragment_path.endswith(".wav")
    audio_path = fragment_path

    # --- Извлечение аудио при необходимости ---
    if not is_wav:
        try:
            audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)
        except Exception as e:
            raise HTTPException(500, f"Ошибка извлечения аудио: {e}")

    # --- Препроцессинг и отпечатки ---
    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        if y is None or len(y) == 0:
            raise HTTPException(400, "Ошибка чтения аудиофайла: пустой сигнал")
        peaks = extract_peaks(
            y, sr,
            frame_size=512, hop_size=128,
            threshold=0.05,
            normalize=True
        )
        hashes = [(h, _as_float(t1)) for h, t1 in generate_hashes_from_peaks(peaks, fan_value=25, time_precision=0.1)]
        frag_duration = len(y) / sr

        if len(hashes) < 5:
            peaks = extract_peaks(
                y, sr,
                frame_size=512, hop_size=128,
                threshold=0.03,
                normalize=True
            )
            hashes = [(h, _as_float(t1)) for h, t1 in generate_hashes_from_peaks(peaks, fan_value=35, time_precision=0.1)]

        if len(hashes) == 0:
            raise HTTPException(400, "Слишком мало хешей для анализа")
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки аудио: {e}")

    # --- Сопоставление хешей с базой ---
    db_hashes = [
        (h, track_id, _as_float(offset))
        for h, track_id, offset in db.query(AudioFingerprint.hash, AudioFingerprint.audio_track_id, AudioFingerprint.offset).all()
    ]
    hash_dict = defaultdict(list)
    for h, track_id, offset in db_hashes:
        hash_dict[h].append((track_id, offset))

    # --- Группируем совпадения по (track_id, offset) ---
    DELTA_TOLERANCE = 0.5
    offset_bins = defaultdict(list)

    for h, t1 in hashes:
        for track_id, t2 in hash_dict.get(h, []):
            offset = _as_float(t2 - t1)
            offset_bin = round(offset / DELTA_TOLERANCE) * DELTA_TOLERANCE
            offset_bins[(track_id, offset_bin)].append((t2, t1))

    # --- Фильтрация offset: не может быть больше (длина_трек - длина_фрагмента) ---
    plausible_offsets = {}
    for (track_id, offset), pairs in offset_bins.items():
        track = db.query(AudioTrack).filter(AudioTrack.id == track_id).first()
        movie = db.query(Movie).filter(Movie.id == track.movie_id).first() if track else None
        max_offset = (movie.duration or 0) - frag_duration if movie else None
        # отсекаем странные значения
        if movie and 0 <= offset <= max_offset + 3:
            plausible_offsets[(track_id, offset)] = len(pairs)

    # --- Если ничего не нашли, пробуем fallback по коротким hash ---
    if not plausible_offsets:
        short_hash_dict = defaultdict(list)
        for h, track_id, offset in db_hashes:
            short_hash_dict[h[:8]].append((track_id, offset))
        for h, t1 in hashes:
            short = h[:8]
            for track_id, t2 in short_hash_dict.get(short, []):
                offset = _as_float(t2 - t1)
                offset_bin = round(offset / DELTA_TOLERANCE) * DELTA_TOLERANCE
                plausible_offsets[(track_id, offset_bin)] = plausible_offsets.get((track_id, offset_bin), 0) + 1

    if not plausible_offsets:
        very_short_hash_dict = defaultdict(list)
        for h, track_id, offset in db_hashes:
            very_short_hash_dict[h[:6]].append((track_id, offset))
        for h, t1 in hashes:
            short = h[:6]
            for track_id, t2 in very_short_hash_dict.get(short, []):
                offset = _as_float(t2 - t1)
                offset_bin = round(offset / DELTA_TOLERANCE) * DELTA_TOLERANCE
                plausible_offsets[(track_id, offset_bin)] = plausible_offsets.get((track_id, offset_bin), 0) + 1

    if not plausible_offsets:
        raise HTTPException(404, detail="Совпадений не найдено")

    # --- Выбор лучшего совпадения ---
    (best_track_id, best_offset), match_score = max(plausible_offsets.items(), key=lambda x: x[1])
    total_checked = len(hashes)
    confidence = round(min(match_score / total_checked, 1.0) * 100, 2) if total_checked > 0 else 0.0

    # --- Найти инфо о фильме ---
    track = db.query(AudioTrack).filter(AudioTrack.id == best_track_id).first()
    movie = db.query(Movie).filter(Movie.id == track.movie_id).first() if track else None
    if not track or not movie:
        raise HTTPException(404, "Фильм или трек не найден")

    # --- Чистим временные файлы ---
    try:
        os.remove(fragment_path)
        if not is_wav and os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        pass

    return {
        "movie": {
            "id": movie.id,
            "title": movie.title,
            "duration": movie.duration,
            "poster_url": movie.poster_url,
            "description": movie.description,
        },
        "audio_track": {
            "id": track.id,
            "language": track.language,
            "track_path": track.track_path,
        },
        "match": {
            "offset": best_offset,
            "score": match_score,
            "total_checked": total_checked,
            "confidence": confidence,
            "valid_offset": 0 <= best_offset <= (movie.duration or 0),
        }
    }
