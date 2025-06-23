import numpy as np
import librosa

def extract_peaks(audio_data: np.ndarray, rate: int, frame_size: int = 2048, hop_size: int = 512, threshold: float = 0.02):
    S = np.abs(librosa.stft(audio_data, n_fft=frame_size, hop_length=hop_size))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    # Пороговая фильтрация
    mask = S_db > (S_db.max() - threshold * 80)
    coordinates = np.argwhere(mask)

    peak_frames = np.unique(coordinates[:, 1])
    peak_times = librosa.frames_to_time(peak_frames, sr=rate, hop_length=hop_size)
    return peak_times.tolist()
