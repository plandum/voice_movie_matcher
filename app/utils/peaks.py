import numpy as np
from scipy.ndimage import maximum_filter
from skimage.feature import peak_local_max

def extract_peaks(audio_data: np.ndarray, rate: int, frame_size: int = 2048, hop_size: int = 512, threshold: float = 0.1):
    """
    Извлекает пики из аудиосигнала как координаты локальных максимумов по времени.

    :param audio_data: одномерный numpy-массив аудио
    :param rate: частота дискретизации
    :param frame_size: размер окна STFT
    :param hop_size: шаг окна STFT
    :param threshold: относительный порог амплитуды для пиков
    :return: список таймкодов в секундах, где обнаружены пики
    """
    import librosa

    # Спектрограмма
    S = np.abs(librosa.stft(audio_data, n_fft=frame_size, hop_length=hop_size))

    # Нормализация
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    # Порог
    mask = S_db > (S_db.max() - threshold * 80)  # например, -8 дБ при threshold=0.1

    # Находим координаты максимумов
    coordinates = peak_local_max(S_db, min_distance=1, threshold_abs=None, labels=mask)

    # Преобразуем координаты в таймкоды
    peak_frames = np.unique(coordinates[:, 1])
    peak_times = librosa.frames_to_time(peak_frames, sr=rate, hop_length=hop_size)

    return peak_times.tolist()
