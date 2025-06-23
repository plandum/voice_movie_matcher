from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
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

def round_time(t: float) -> float:
    return float(Decimal(str(t)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

@router.post("/audio")
def match_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
        # Открываем в нужном формате, без trim!
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        if np.max(np.abs(y)) > 0:
            y = y / np.max(np.abs(y))
        # Пики и хеши — тот же threshold/fan_value что и при загрузке!
        peaks = extract_peaks(y, sr, frame_size=512, hop_size=128, threshold=0.1)
        hashes = generate_hashes_from_peaks(peaks, fan_value=15)

        print("Длительность аудио (сек):", len(y) / sr)
        print("Количество пиков:", len(peaks))
        print("Количество хешей:", len(hashes))
        print("Пример хеша:", hashes[0] if hashes else "none")

        # Если хешей мало — можно повторить с еще меньшим threshold
        if len(hashes) < 5:
            peaks = extract_peaks(y, sr, frame_size=512, hop_size=128, threshold=0.1)
            hashes = generate_hashes_from_peaks(peaks, fan_value=25)
            print("🔁 Повторно:")
            print("  Кол-во пиков:", len(peaks))
            print("  Кол-во хешей:", len(hashes))
            print("  Пример хеша:", hashes[0] if hashes else "none")

        if len(hashes) == 0:
            raise HTTPException(400, "Слишком мало хешей для анализа")
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки аудио: {e}")

    # --- Сопоставление ---
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

    # Fallback: если совсем не найдено, пробуем короткие хеши (с меньшим весом)
    if not counter:
        short_hash_dict = defaultdict(list)
        for h, track_id, offset in db_hashes:
            short_hash_dict[h[:8]].append((track_id, offset))
        for h, t1 in hashes:
            short = h[:8]
            if short in short_hash_dict:
                for track_id, t2 in short_hash_dict[short]:
                    delta = round_time(t2 - t1)
                    counter[(track_id, delta)] += 0.3
    
    if not counter:
        very_short_hash_dict = defaultdict(list)
        for h, track_id, offset in db_hashes:
            very_short_hash_dict[h[:6]].append((track_id, offset))
        for h, t1 in hashes:
            short = h[:6]
            if short in very_short_hash_dict:
                for track_id, t2 in very_short_hash_dict[short]:
                    delta = round_time(t2 - t1)
                    counter[(track_id, delta)] += 0.1


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
