import numpy as np
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_hashes_from_peaks(
    peaks,
    freqs=None,
    fan_value=18,
    min_delta=0.3,
    max_delta=8.0,
    time_precision=0.05
):
    """
    Генерирует хеши из пиков аудиосигнала для создания аудиоотпечатков.
    
    Args:
        peaks (list): Список времен пиков (в секундах).
        freqs (list, optional): Список частот пиков (в Гц). Если None, частоты не используются.
        fan_value (int): Максимальное количество пар пиков для каждого t1.
        min_delta (float): Минимальная временная разница между пиками (сек).
        max_delta (float): Максимальная временная разница между пиками (сек).
        time_precision (float): Точность округления времени (сек).

    Returns:
        list: Список кортежей (hash, t1), где hash — хеш пары пиков, t1 — время первого пика.
    """
    # Convert inputs to NumPy arrays if they aren't already
    if not isinstance(peaks, np.ndarray):
        peaks = np.array(peaks, dtype=np.float32)
    if freqs is not None and not isinstance(freqs, np.ndarray):
        freqs = np.array(freqs, dtype=np.float32)

    # Check for insufficient peaks
    if peaks.size < 2:
        logger.warning("Недостаточно пиков для генерации хешей: %d", peaks.size)
        return []

    # Check for size mismatch between peaks and freqs
    if freqs is not None and freqs.size != peaks.size:
        logger.error("Длина списка частот (%d) не совпадает с длиной пиков (%d)", freqs.size, peaks.size)
        raise ValueError("Несоответствие длины freqs и peaks")

    # Round peak times for consistency
    peak_times = np.round(peaks / time_precision) * time_precision
    peak_times = np.round(peak_times, 5)

    hashes = []
    max_hashes = 100000

    # Iterate over peaks
    for i in range(peak_times.size):
        t1 = peak_times[i]
        freq1 = freqs[i] if freqs is not None else None
        end_idx = min(i + fan_value, peak_times.size)
        t2_candidates = peak_times[i + 1:end_idx]
        freq2_candidates = freqs[i + 1:end_idx] if freqs is not None else None

        if t2_candidates.size == 0:
            continue

        deltas = t2_candidates - t1
        mask = (deltas > min_delta) & (deltas < max_delta)
        if not np.any(mask):
            continue

        valid_deltas = deltas[mask]
        valid_deltas = np.round(valid_deltas / time_precision) * time_precision
        valid_deltas = np.round(valid_deltas, 5)

        if freqs is not None:
            valid_freq2 = freq2_candidates[mask]
            for delta, freq2 in zip(valid_deltas, valid_freq2):
                hash_input = f"{delta:.5f}|{freq1:.0f}|{freq2:.0f}"
                h = hashlib.sha1(hash_input.encode()).hexdigest()[:12]
                hashes.append((h, float(t1)))
                if len(hashes) >= max_hashes:
                    logger.warning("Достигнуто максимальное количество хешей: %d", max_hashes)
                    return hashes
        else:
            for delta in valid_deltas:
                hash_input = f"{delta:.5f}"
                h = hashlib.sha1(hash_input.encode()).hexdigest()[:12]
                hashes.append((h, float(t1)))
                if len(hashes) >= max_hashes:
                    logger.warning("Достигнуто максимальное количество хешей: %d", max_hashes)
                    return hashes

    logger.info("Сгенерировано хешей: %d", len(hashes))
    return hashes