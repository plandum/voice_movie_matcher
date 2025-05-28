import os
import subprocess

def generate_fingerprints(audio_path: str) -> dict:
    audio_path = os.path.abspath(audio_path)

    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Файл не найден: {audio_path}")

    command = ["fpcalc", "-raw", "-length", "120", audio_path]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"fpcalc error: {result.stderr.strip()}")

    output = result.stdout.strip().split("\n")
    fingerprint_str = None
    duration = None

    for line in output:
        if line.startswith("FINGERPRINT="):
            fingerprint_str = line[len("FINGERPRINT="):]
        elif line.startswith("DURATION="):
            duration = int(line[len("DURATION="):])

    if fingerprint_str is None:
        raise ValueError("Отсутствует строка FINGERPRINT в выводе fpcalc")
    if duration is None:
        raise ValueError("Отсутствует строка DURATION в выводе fpcalc")

    try:
        fingerprint_list = list(map(int, fingerprint_str.split(",")))
    except ValueError as e:
        raise ValueError(f"Ошибка парсинга отпечатков: {e}")

    print("Fingerprint успешно получен:", fingerprint_list[:5], "...", "длительность:", duration)
    return {"fingerprint": fingerprint_list, "duration": duration}
