import numpy as np
import librosa
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_peaks(
    audio_data,
    rate,
    normalize=True,
    return_freqs=False,
    frame_size=512,
    hop_size=128,
    min_freq=100.0,
    max_freq=4000.0,
    threshold=0.7  # Увеличен с 0.5 до 0.7
):
    """
    Извлекает временные пики и их частоты из аудиосигнала.

    Args:
        audio_data (np.ndarray): Аудиосигнал.
        rate (int): Частота дискретизации (Гц).
        normalize (bool): Нормализовать аудио перед обработкой.
        return_freqs (bool): Возвращать частоты пиков.
        frame_size (int): Размер окна STFT.
        hop_size (int): Шаг окна STFT.
        min_freq (float): Минимальная частота (Гц).
        max_freq (float): Максимальная частота (Гц).
        threshold (float): Порог для пиков (относительно максимума).

    Returns:
        tuple: (peak_times, peak_freqs), где peak_times — времена пиков (сек), peak_freqs — частоты (Гц) или None.
    """
    if not isinstance(audio_data, np.ndarray):
        audio_data = np.array(audio_data, dtype=np.float32)
        logger.warning("Аудиоданные преобразованы в numpy-массив")

    if normalize:
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val
        else:
            logger.warning("Аудио пустое или содержит только нули")
            return np.array([]), np.array([]) if return_freqs else None

    try:
        spec = np.abs(librosa.stft(audio_data, n_fft=frame_size, hop_length=hop_size))
        times = librosa.frames_to_time(np.arange(spec.shape[1]), sr=rate, hop_length=hop_size)
        freqs = librosa.fft_frequencies(sr=rate, n_fft=frame_size)
    except Exception as e:
        logger.error("Ошибка при вычислении STFT: %s", e)
        return np.array([]), np.array([]) if return_freqs else None

    if spec.size == 0:
        logger.warning("Спектрограмма пуста")
        return np.array([]), np.array([]) if return_freqs else None

    freq_mask = (freqs >= min_freq) & (freqs <= (max_freq if max_freq > 0 else freqs[-1]))
    if not np.any(freq_mask):
        logger.warning("Нет частот в диапазоне %s-%s Гц", min_freq, max_freq)
        return np.array([]), np.array([]) if return_freqs else None

    spec = spec[freq_mask, :]
    freqs = freqs[freq_mask]

    spec_max = np.max(spec, axis=0, keepdims=True)
    spec_max = np.where(spec_max == 0, 1e-10, spec_max)  # Avoid division by zero
    peak_mask = spec > (threshold * spec_max)
    if not np.any(peak_mask):
        logger.warning("Нет пиков при threshold=%s", threshold)
        return np.array([]), np.array([]) if return_freqs else None

    peak_indices = np.where(peak_mask)
    peak_times = times[peak_indices[1]]
    peak_freqs = freqs[peak_indices[0]] if return_freqs else None

    if return_freqs:
        if peak_times.size != peak_freqs.size:
            logger.error("Несоответствие размеров peak_times (%d) и peak_freqs (%d)", peak_times.size, peak_freqs.size)
            return np.array([]), np.array([])

    peak_times = np.array(peak_times, dtype=np.float32)
    peak_freqs = np.array(peak_freqs, dtype=np.float32) if return_freqs else None
    logger.info("Извлечено %d пиков", peak_times.size)
    return peak_times, peak_freqs