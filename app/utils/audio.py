import os
import subprocess
from pathlib import Path

def extract_audio_from_video(video_path: str, output_dir: str) -> str:
    filename = Path(video_path).stem
    audio_path = os.path.join(output_dir, f"{filename}.wav")

    command = [
        "ffmpeg",
        "-y",  # overwrite if exists
        "-i", video_path,
        "-vn",  # no video
        "-acodec", "pcm_s16le",
        "-ar", "16000",  # 16 kHz
        "-ac", "1",      # mono
        audio_path
    ]

    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return audio_path
