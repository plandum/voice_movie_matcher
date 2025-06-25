def extract_peaks(audio_data, rate, frame_size=512, hop_size=128, threshold=0.04, normalize=True, return_freqs=False):
    import numpy as np
    import librosa
    from scipy.ndimage import maximum_filter

    if normalize:
        maxv = np.max(np.abs(audio_data))
        if maxv > 0:
            audio_data = audio_data / maxv

    # Remove leading/trailing silence (не агрессивно, чтобы не потерять sync)
    yt, _ = librosa.effects.trim(audio_data, top_db=35)

    S = np.abs(librosa.stft(yt, n_fft=frame_size, hop_length=hop_size))
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    # Adaptive threshold
    dynamic_thresh = S_db.max() - threshold * 80
    mask = S_db > dynamic_thresh

    # Find local maxima
    filtered = maximum_filter(S_db, size=(3, 3))
    peaks_binary = (S_db == filtered) & mask
    coords = np.argwhere(peaks_binary)

    peak_times = librosa.frames_to_time(coords[:, 1], sr=rate, hop_length=hop_size)
    if return_freqs:
        peak_freqs = librosa.fft_frequencies(sr=rate, n_fft=frame_size)[coords[:, 0]]
        return list(peak_times), list(peak_freqs)
    else:
        return list(peak_times)
