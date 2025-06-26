import numpy as np
import librosa
import logging
from scipy.signal import medfilt
from scipy.ndimage import maximum_filter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_peaks(
    audio_data: np.ndarray,
    rate: int,
    normalize: bool = True,
    return_freqs: bool = False,
    return_amplitudes: bool = False,
    frame_size: int = 1024,
    hop_size: int = 256,
    min_freq: float = 100.0,
    max_freq: float = 4000.0,
    threshold: float = 0.6,
    absolute_threshold: float | None = None,
    max_peaks: int | None = None
) -> tuple:
    """
    Извлекает локальные спектральные пики из аудиосигнала с применением
    2D-поиска локальных максимумов и комбинированного порога.

    Args:
        audio_data (np.ndarray): Аудиосигнал.
        rate (int): Частота дискретизации (Гц).
        normalize (bool): Нормализовать аудио по максимуму.
        return_freqs (bool): Возвращать частоты пиков.
        return_amplitudes (bool): Возвращать амплитуды пиков.
        frame_size (int): Размер окна STFT.
        hop_size (int): Шаг окна STFT.
        min_freq (float): Минимальная частота (Гц).
        max_freq (float): Максимальная частота (Гц).
        threshold (float): Относительный порог для пиков (например, 0.6).
        absolute_threshold (float|None): Абсолютный порог (если None — не применяем).
        max_peaks (int|None): Максимальное число пиков (берутся по амплитуде).

    Returns:
        peak_times (np.ndarray): Времена пиков (сек).
        peak_freqs (np.ndarray|None): Частоты пиков (Гц) или None.
        peak_amplitudes (np.ndarray|None): Амплитуды пиков или None.
    """
    # Приведение к numpy-массиву и нормализация
    if not isinstance(audio_data, np.ndarray):
        audio_data = np.array(audio_data, dtype=np.float32)
        logger.warning("Аудиоданные преобразованы в numpy-массив")
    if normalize:
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val
        else:
            logger.warning("Аудио пустое или содержит только нули")
            return np.array([]), (
                np.array([]) if return_freqs else None
            ), (
                np.array([]) if return_amplitudes else None
            )

    # Лёгкая фильтрация артефактов
    audio_data = medfilt(audio_data, kernel_size=3)

    # Построение спектрограммы
    try:
        spec = np.abs(librosa.stft(audio_data, n_fft=frame_size, hop_length=hop_size))
        times = librosa.frames_to_time(np.arange(spec.shape[1]), sr=rate, hop_length=hop_size)
        freqs = librosa.fft_frequencies(sr=rate, n_fft=frame_size)
    except Exception as e:
        logger.error("Ошибка при вычислении STFT: %s", e)
        return np.array([]), (
            np.array([]) if return_freqs else None
        ), (
            np.array([]) if return_amplitudes else None
        )

    # Отсечение вне диапазона
    if spec.size == 0:
        logger.warning("Спектрограмма пуста")
        return np.array([]), (
            np.array([]) if return_freqs else None
        ), (
            np.array([]) if return_amplitudes else None
        )
    freq_mask = (freqs >= min_freq) & (freqs <= max_freq)
    if not np.any(freq_mask):
        logger.warning("Нет частот в диапазоне %.1f-%.1f Гц", min_freq, max_freq)
        return np.array([]), (
            np.array([]) if return_freqs else None
        ), (
            np.array([]) if return_amplitudes else None
        )
    spec = spec[freq_mask, :]
    freqs = freqs[freq_mask]

    # Относительный и локальные максимумы
    spec_max = np.max(spec, axis=0, keepdims=True)
    spec_max = np.where(spec_max == 0, np.finfo(float).eps, spec_max)
    relative_mask = spec > (threshold * spec_max)
    local_max = maximum_filter(spec, size=(3, 3))
    peak_mask = (spec == local_max) & relative_mask
    if absolute_threshold is not None:
        peak_mask &= (spec > absolute_threshold)
    if not np.any(peak_mask):
        logger.warning("Нет пиков при threshold=%.2f%s", threshold,
                       (f" и abs>{absolute_threshold}" if absolute_threshold else ""))
        return np.array([]), (
            np.array([]) if return_freqs else None
        ), (
            np.array([]) if return_amplitudes else None
        )

    # Индексы пиков
    freq_idx, time_idx = np.where(peak_mask)
    peak_times = times[time_idx]
    peak_freqs = freqs[freq_idx] if return_freqs else None
    peak_amplitudes = spec[freq_idx, time_idx]  # всегда доступна для фильтрации

    # Ограничение числа пиков по амплитуде
    if max_peaks is not None and peak_amplitudes.size > max_peaks:
        # берем топ по амплитуде
        order = np.argsort(peak_amplitudes)[::-1][:max_peaks]
        peak_times = peak_times[order]
        peak_freqs = peak_freqs[order] if return_freqs else None
        peak_amplitudes = peak_amplitudes[order]

    # Приведение к numpy
    peak_times = np.array(peak_times, dtype=np.float32)
    peak_freqs = np.array(peak_freqs, dtype=np.float32) if return_freqs else None
    peak_amplitudes = np.array(peak_amplitudes, dtype=np.float32) if return_amplitudes else None

    logger.info("Извлечено %d пиков", peak_times.size)
    return peak_times, peak_freqs, peak_amplitudes
