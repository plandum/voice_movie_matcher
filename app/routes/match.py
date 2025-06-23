from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import Counter, defaultdict
import os, shutil, librosa, mimetypes, logging

from app.database import SessionLocal
from app.models import AudioFingerprint, AudioTrack, Movie
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks
from app.utils.fingerprinting import generate_hashes_from_peaks

router = APIRouter(prefix="/match", tags=["match"])

MEDIA_DIR = "media/fragments"
logging.basicConfig(level=logging.INFO)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/audio")
def match_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    import os, shutil, librosa, mimetypes
    from decimal import Decimal, ROUND_HALF_UP

    def round_time(t: float) -> float:
        return float(Decimal(str(t)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    fragment_path = os.path.join(MEDIA_DIR, file.filename)
    os.makedirs(os.path.dirname(fragment_path), exist_ok=True)
    with open(fragment_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    mime_type, _ = mimetypes.guess_type(fragment_path)
    is_wav = mime_type == "audio/wav" or fragment_path.endswith(".wav")
    audio_path = fragment_path

    if not is_wav:
        try:
            audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)
        except Exception as e:
            raise HTTPException(500, f"Ошибка извлечения аудио: {e}")

    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        peaks = extract_peaks(y, sr, threshold=0.02)
        hashes = generate_hashes_from_peaks(peaks, fan_value=20)
        if len(hashes) == 0:
            raise HTTPException(400, "Слишком мало хешей для анализа")
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки аудио: {e}")

    db_hashes = db.query(AudioFingerprint.hash, AudioFingerprint.audio_track_id, AudioFingerprint.offset).all()
    hash_dict = defaultdict(list)
    for h, track_id, offset in db_hashes:
        hash_dict[h].append((track_id, offset))

    counter = Counter()
    for h, t1 in hashes:
        if h in hash_dict:
            for track_id, t2 in hash_dict[h]:
                delta = round_time(t2 - t1)
                counter[(track_id, delta)] += 1

    print(f"Совпадающих пар: {sum(counter.values())}")
    print("HASHES SEARCH:", hashes[:5])

    # Soft fallback: если не найдено — пробуем частичные хеши
    if not counter:
        short_hash_dict = defaultdict(list)
        for h, track_id, offset in db_hashes:
            short_hash_dict[h[:8]].append((track_id, offset))

        for h, t1 in hashes:
            short = h[:8]
            if short in short_hash_dict:
                for track_id, t2 in short_hash_dict[short]:
                    delta = round_time(t2 - t1)
                    counter[(track_id, delta)] += 0.3  # сниженный вес

    if not counter:
        raise HTTPException(404, detail="Совпадений не найдено")

    (best_track_id, best_offset), match_score = counter.most_common(1)[0]
    total_checked = len(hashes)
    confidence = round(min(match_score / total_checked, 1.0) * 100, 2)

    track = db.query(AudioTrack).filter(AudioTrack.id == best_track_id).first()
    movie = db.query(Movie).filter(Movie.id == track.movie_id).first()

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
