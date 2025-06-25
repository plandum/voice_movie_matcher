from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import Counter
import os
import shutil
import mimetypes
import librosa
import numpy as np
import logging
import tempfile
from sklearn.cluster import DBSCAN

from app.database import SessionLocal
from app.models import AudioFingerprint, AudioTrack, Movie
from app.utils.audio import extract_audio_from_video
from app.utils.peaks import extract_peaks
from app.utils.fingerprinting import generate_hashes_from_peaks

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.routes.match")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

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
    except (ValueError, TypeError):
        logger.error("Ошибка преобразования в float: %s", val)
        raise HTTPException(400, f"Некорректное значение для преобразования: {val}")

@router.post("/audio")
async def match_audio(
    file: UploadFile = File(...),
    movie_id: int = Form(...),
    language: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Сопоставляет аудиофрагмент с аудиодорожкой фильма и возвращает временное смещение.

    Args:
        file (UploadFile): Загруженный аудио- или видеофайл.
        movie_id (int): ID фильма.
        language (str): Язык аудиодорожки.
        db (Session): Сессия базы данных.

    Returns:
        dict: Информация о дорожке и результатах матчинга (offset, score, confidence).
    """
    logger.debug("Логирование DEBUG включено")
    # --- Сохраняем файл во временную директорию ---
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".tmp", dir=MEDIA_DIR, delete=False) as temp_file:
            fragment_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
    except Exception as e:
        logger.error("Ошибка сохранения файла: %s", e)
        raise HTTPException(500, f"Ошибка сохранения файла: {e}")

    mime_type, _ = mimetypes.guess_type(fragment_path)
    is_wav = mime_type == "audio/wav" or fragment_path.endswith(".wav")
    audio_path = fragment_path

    # --- Извлекаем аудио (если это не WAV) ---
    if not is_wav:
        try:
            audio_path = extract_audio_from_video(fragment_path, MEDIA_DIR)
        except Exception as e:
            logger.error("Ошибка извлечения аудио: %s", e)
            raise HTTPException(500, f"Ошибка извлечения аудио: {e}")

    # --- Подгружаем нужный AudioTrack ---
    track = (
        db.query(AudioTrack)
        .filter(AudioTrack.movie_id == movie_id)
        .filter(AudioTrack.language.ilike(language))
        .first()
    )
    if not track:
        logger.error("Не найдена аудиодорожка для movie_id=%d, language=%s", movie_id, language)
        raise HTTPException(404, f"Не найдена аудиодорожка для фильма {movie_id} и языка '{language}'")

    # --- Генерируем хеши из загруженного фрагмента ---
    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        fragment_duration = len(y) / sr
        if fragment_duration < 0.5:
            logger.warning("Аудиофрагмент слишком короткий: %.2f сек", fragment_duration)
            raise HTTPException(400, "Аудиофрагмент слишком короткий (<0.5 сек)")
        if y is None or len(y) == 0:
            logger.error("Ошибка чтения аудиофайла: пустой сигнал")
            raise HTTPException(400, "Ошибка чтения аудиофайла: пустой сигнал")
        
        peaks, freqs = extract_peaks(
            y, sr,
            normalize=True,
            return_freqs=True,
            frame_size=512,
            hop_size=128,
            min_freq=100.0,
            max_freq=4000.0,
            threshold=0.7
        )
        if not isinstance(peaks, np.ndarray) or not isinstance(freqs, np.ndarray):
            logger.error("peaks или freqs не являются numpy-массивами: peaks=%s, freqs=%s", type(peaks), type(freqs))
            raise HTTPException(400, detail="Некорректный формат пиков или частот")
        if peaks.size == 0 or freqs.size == 0:
            logger.error("peaks или freqs пусты: peaks_size=%d, freqs_size=%d", peaks.size, freqs.size)
            raise HTTPException(400, detail="Пустые пики или частоты")
        if peaks.size != freqs.size:
            logger.error("Несоответствие размеров peaks (%d) и freqs (%d)", peaks.size, freqs.size)
            raise HTTPException(400, detail="Несоответствие размеров пиков и частот")
        logger.debug("Пики (первые 5): %s, Частоты (первые 5): %s", peaks[:5], freqs[:5])
        hashes = [(h, _as_float(t1)) for h, t1 in generate_hashes_from_peaks(
            peaks, freqs=freqs, fan_value=10, min_delta=0.5, max_delta=5.0, time_precision=0.05
        )]
        logger.info("Длительность аудио: %.2f сек", fragment_duration)
        logger.info("Количество пиков: %d", len(peaks))
        logger.info("Количество хешей: %d", len(hashes))
        logger.info("Пример хеша: %s", hashes[0] if hashes else "none")
        if len(hashes) < 5:
            logger.warning("Слишком мало хешей для анализа: %d", len(hashes))
            raise HTTPException(400, "Слишком мало хешей для анализа (<5)")
    except Exception as e:
        logger.error("Ошибка обработки аудио: %s", e)
        raise HTTPException(500, f"Ошибка обработки аудио: {e}")
    finally:
        try:
            if os.path.exists(fragment_path):
                os.remove(fragment_path)
            if not is_wav and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            logger.warning("Ошибка удаления временных файлов: %s", e)

    # --- Загружаем хеши из базы только для нужной дорожки ---
    try:
        db_hashes = [
            (h, _as_float(offset))
            for h, offset in db.query(AudioFingerprint.hash, AudioFingerprint.offset)
            .filter(AudioFingerprint.audio_track_id == track.id)
            .filter(AudioFingerprint.hash.in_([h for h, _ in hashes]))
            .all()
        ]
        if not db_hashes:
            logger.warning("Отпечатки для аудиодорожки отсутствуют")
            raise HTTPException(404, "Отпечатки для этой аудиодорожки отсутствуют")
    except Exception as e:
        logger.error("Ошибка загрузки хешей из базы: %s", e)
        raise HTTPException(500, f"Ошибка загрузки хешей из базы: {e}")

    # --- Сопоставление хешей ---
    DELTA_TOLERANCE = 0.5  # Шаг для биннинга смещений
    try:
        t1_array = np.array([t1 for _, t1 in hashes])
        hash_set = set(h for h, _ in hashes)
        plausible_offsets = Counter()

        for h, t2_list in [(h, [offset for h_db, offset in db_hashes if h_db == h]) for h in hash_set]:
            if t2_list:
                t2_array = np.array(t2_list)
                deltas = np.round(t2_array[:, None] - t1_array, 2)
                bin_deltas = np.round(deltas / DELTA_TOLERANCE) * DELTA_TOLERANCE
                bin_deltas = np.round(bin_deltas, 2)
                unique, counts = np.unique(bin_deltas, return_counts=True)
                for delta, count in zip(unique, counts):
                    plausible_offsets[delta] += count

        if not plausible_offsets:
            logger.warning("Совпадений не найдено")
            raise HTTPException(404, detail="Совпадений не найдено")

        # --- Фильтрация валидных смещений ---
        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        track_duration = movie.duration if movie and hasattr(movie, "duration") else float('inf')
        valid_candidates = [
            (offset, count)
            for offset, count in plausible_offsets.items()
            if 0 <= offset <= (track_duration - fragment_duration if track_duration != float('inf') else float('inf'))
        ]

        if not valid_candidates:
            logger.warning("Нет валидных смещений после фильтрации")
            raise HTTPException(404, detail="Нет валидных смещений после фильтрации")

        # Проверка на аномальные совпадения
        total_hashes = len(hashes)
        max_reasonable_matches = total_hashes * 100  # Максимум 100 совпадений на хеш
        valid_candidates = [
            (offset, count)
            for offset, count in valid_candidates
            if count <= max_reasonable_matches
        ]
        logger.debug("Общее количество хешей: %d, Максимум разумных совпадений: %d", total_hashes, max_reasonable_matches)
        logger.debug("Суммарное количество совпадений: %d", sum(count for _, count in valid_candidates))

        if not valid_candidates:
            logger.warning("Нет валидных смещений после фильтрации аномалий")
            raise HTTPException(404, detail="Нет валидных смещений после фильтрации аномалий")

        logger.info("Валидные смещения (offset, count):")
        for offset, count in sorted(valid_candidates):
            logger.info("Offset: %.2f, Matches: %d", offset, count)

        # --- Кластеризация ---
        try:
            offsets = np.array([offset for offset, _ in valid_candidates]).reshape(-1, 1)
            counts = np.array([count for _, count in valid_candidates])
            clustering = DBSCAN(eps=2.0, min_samples=3).fit(offsets, sample_weight=counts)
            logger.debug("DBSCAN labels: %s", clustering.labels_)
            logger.debug("Unique labels: %s", np.unique(clustering.labels_))

            # Выводим информацию о кластерах
            unique_labels = np.unique(clustering.labels_)
            cluster_info = []
            for label in unique_labels:
                if label != -1:  # Исключаем шум
                    cluster_offsets = offsets[clustering.labels_ == label]
                    cluster_counts = counts[clustering.labels_ == label]
                    cluster_mean = np.mean(cluster_offsets) if cluster_offsets.size > 0 else 0.0
                    cluster_score = np.sum(cluster_counts)
                    cluster_info.append((label, cluster_mean, cluster_score))
                    logger.debug("Cluster %d: Mean offset=%.2f, Score=%d", label, cluster_mean, cluster_score)

            if len(unique_labels) > 1 and -1 not in unique_labels:
                # Выбираем кластер с наибольшей суммой совпадений
                cluster_scores = [np.sum(counts[clustering.labels_ == i]) for i in unique_labels]
                best_cluster = np.argmax(cluster_scores)
                best_offset = float(np.mean(offsets[clustering.labels_ == best_cluster]))
                match_score = int(np.sum(counts[clustering.labels_ == best_cluster]))
                logger.debug("Cluster scores: %s", cluster_scores)
                logger.debug("Best cluster: %d, Offset: %.2f, Score: %d", best_cluster, best_offset, match_score)
            elif any(label != -1 for label in unique_labels):
                # Выбираем первый нешумовой кластер
                for label in unique_labels:
                    if label != -1:
                        best_offset = float(np.mean(offsets[clustering.labels_ == label]))
                        match_score = int(np.sum(counts[clustering.labels_ == label]))
                        logger.debug("Selected non-noise cluster: %d, Offset: %.2f, Score: %d", label, best_offset, match_score)
                        break
            else:
                # Fallback: Выбираем смещение с максимальным количеством совпадений
                best_offset, match_score = max(valid_candidates, key=lambda x: x[1])
                logger.debug("Fallback to max matches: Offset: %.2f, Score: %d", best_offset, match_score)

            logger.info("Выбран лучший offset: %.2f, matches: %d", best_offset, match_score)
        except Exception as e:
            logger.error("Ошибка выбора лучшего смещения: %s", e)
            raise HTTPException(500, f"Ошибка выбора лучшего смещения: {e}")

        # --- Вычисление уверенности ---
        total_checked = len(hashes)
        if valid_candidates:
            counts = np.array([count for _, count in valid_candidates])
            normalized_counts = counts / counts.sum()
            entropy = -np.sum(normalized_counts * np.log(normalized_counts + 1e-10))
            max_entropy = np.log(len(normalized_counts)) if len(normalized_counts) > 0 else 1
            confidence = round(min(match_score / total_checked, 1.0) * (1 - entropy / max_entropy) * 100, 2)
        else:
            confidence = 0.0

        logger.info("---- Результаты ----")
        logger.info("best_offset: %.2f", best_offset)
        logger.info("match_score: %d", match_score)
        logger.info("total_checked: %d", total_checked)
        logger.info("confidence: %.2f%%", confidence)

        return {
            "audio_track": {
                "id": track.id,
                "language": track.language,
                "track_path": track.track_path,
            },
            "match": {
                "offset": float(best_offset),
                "score": int(match_score),
                "total_checked": int(total_checked),
                "confidence": float(confidence),
                "valid_offset": bool(0 <= best_offset <= (track_duration - fragment_duration if track_duration != float('inf') else float('inf')))
            }
        }
    except Exception as e:
        logger.error("Ошибка сопоставления хешей: %s", e)
        raise HTTPException(500, f"Ошибка сопоставления хешей: {e}")