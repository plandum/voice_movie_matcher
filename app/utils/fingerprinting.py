from typing import List, Tuple
import hashlib
from app.utils.rounding import round_time

def generate_hashes_from_peaks(peaks: List[float], fan_value: int = 20) -> List[Tuple[str, float]]:
    result = []
    for i in range(len(peaks)):
        for j in range(1, fan_value + 1):
            if i + j < len(peaks):
                t1 = peaks[i]
                t2 = peaks[i + j]
                delta = t2 - t1
                if 0.5 <= delta <= 5.0:
                    h = hashlib.sha1(f"{round_time(t1)}|{round_time(t2)}|{round_time(delta)}".encode()).hexdigest()[:16]
                    result.append((h, round_time(t1)))
    return result
