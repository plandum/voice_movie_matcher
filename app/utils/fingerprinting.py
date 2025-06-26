import numpy as np
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_hashes_from_peaks(
    peaks,
    freqs=None,
    amplitudes=None,
    fan_value=15,
    min_delta=0.5,
    max_delta=8.0,
    time_precision=0.05,
    target_density=100.0,
    max_hashes=500000
):
    """
    Генерирует хеши из пиков аудиосигнала для создания аудиоотпечатков.

    Для защиты от взрывного роста числа пар используется динамически
    откорректированный fan_value на основе плотности пиков,
    а также ограничение общего числа хешей (max_hashes).

    Args:
        peaks (array-like): Времена пиков (сек) в виде списка или numpy-массива.
        freqs (array-like, optional): Частоты пиков (Гц).
        amplitudes (array-like, optional): Амплитуды пиков.
        fan_value (int): Базовое число соседей для каждой пикового времени.
        min_delta (float): Мин. временная дельта между пиками (сек).
        max_delta (float): Макс. временная дельта между пиками (сек).
        time_precision (float): Шаг округления времени (сек).
        target_density (float): Целевая плотность пиков (пиков/сек) для масштабирования fan_value.
        max_hashes (int): Макс. число генерируемых хешей.

    Returns:
        list[tuple[str, float]]: Список кортежей (hash, t1).
    """
    peaks_arr = np.asarray(peaks, dtype=np.float32)
    n_peaks = peaks_arr.size
    if n_peaks < 2:
        logger.warning("Недостаточно пиков для генерации хешей: %d", n_peaks)
        return []

    # Вычисление динамического fan_value по плотности
    duration = float(peaks_arr.max() - peaks_arr.min()) if n_peaks > 1 else 0.0
    density = (n_peaks / duration) if duration > 0 else float(n_peaks)
    scale = (target_density / density) if density > 0 else 1.0
    actual_fan = max(1, min(fan_value, int(fan_value * scale)))

    # Квантизация времен пиков
    peak_times = np.round(peaks_arr / time_precision) * time_precision

    # Подготовка массивов частот и амплитуд
    freqs_arr = np.asarray(freqs, dtype=np.float32) if freqs is not None else None
    amps_arr = np.asarray(amplitudes, dtype=np.float32) if amplitudes is not None else None

    hashes = []
    for i in range(n_peaks):
        t1 = float(peak_times[i])
        freq1 = float(freqs_arr[i]) if freqs_arr is not None else None
        amp1 = float(amps_arr[i]) if amps_arr is not None else None

        # Берём следующих actual_fan пиков после i
        end_idx = min(i + actual_fan, n_peaks)
        t2_block = peak_times[i+1:end_idx]
        deltas = t2_block - t1
        mask = (deltas >= min_delta) & (deltas <= max_delta)
        if not np.any(mask):
            continue

        valid_deltas = deltas[mask]
        # Округление дельт
        valid_deltas = np.round(valid_deltas / time_precision) * time_precision
        valid_deltas = np.round(valid_deltas, 5)

        if freqs_arr is not None:
            freq2_block = freqs_arr[i+1:end_idx][mask]
        if amps_arr is not None:
            amp2_block = amps_arr[i+1:end_idx][mask]

        # Генерация хешей
        for idx, delta in enumerate(valid_deltas):
            freq2 = float(freq2_block[idx]) if freqs_arr is not None else None
            amp2 = float(amp2_block[idx]) if amps_arr is not None else None

            # Формирование входа для хеш-функции
            if freqs_arr is not None and amps_arr is not None:
                hash_input = f"{delta:.5f}|{freq1:.1f}|{freq2:.1f}|{amp1:.2f}|{amp2:.2f}"
            elif freqs_arr is not None:
                hash_input = f"{delta:.5f}|{freq1:.1f}|{freq2:.1f}"
            else:
                hash_input = f"{delta:.5f}"

            h = hashlib.sha1(hash_input.encode('utf-8')).hexdigest()[:12]
            hashes.append((h, t1))
            if len(hashes) >= max_hashes:
                logger.warning("Достигнуто макс. число хешей: %d", max_hashes)
                return hashes

    logger.info(
        "Сгенерировано хешей: %d, плотность: %.2f пиков/сек, fan_value: %d", 
        len(hashes), density, actual_fan
    )
    return hashes
