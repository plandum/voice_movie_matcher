# app/utils/fingerprinting.py
def generate_hashes_from_peaks(
    peaks, fan_value=25, min_delta=0.2, max_delta=12.0, time_precision=0.1
):
    import hashlib
    hashes = []
    for i in range(len(peaks)):
        t1 = round(float(peaks[i]) / time_precision) * time_precision
        for j in range(1, fan_value):
            if i + j < len(peaks):
                t2 = round(float(peaks[i + j]) / time_precision) * time_precision
                delta = round((t2 - t1) / time_precision) * time_precision
                if min_delta < delta < max_delta:
                    # Только delta — устойчиво к вырезам, легко группировать по offset
                    h = hashlib.sha1(f"{delta:.2f}".encode()).hexdigest()[:12]
                    hashes.append((h, t1))
    return hashes
