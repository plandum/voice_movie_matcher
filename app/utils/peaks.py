# app/utils/peaks.py

def extract_peaks(audio_data, rate, frame_size=512, hop_size=128, threshold=0.1):
    import numpy as np
    import librosa
    from scipy.ndimage import maximum_filter

    S = np.abs(librosa.stft(audio_data, n_fft=frame_size, hop_length=hop_size))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    # Адаптивный порог
    dynamic_thresh = S_db.max() - threshold * 80
    mask = S_db > dynamic_thresh

    # Нахождение локальных максимумов
    filtered = maximum_filter(S_db, size=(3, 3))
    peaks_binary = (S_db == filtered) & mask
    coords = np.argwhere(peaks_binary)

    peak_times = librosa.frames_to_time(coords[:, 1], sr=rate, hop_length=hop_size)
    return list(peak_times)
