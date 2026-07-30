import os
import asyncio
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

async def separate_audio(file_path):
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _separate, file_path)
        return result
    except Exception as e:
        logger.error(f"Separation failed: {e}")
        return None

def _separate(file_path):
    stem = Path(file_path).stem
    vocals_path = str(OUTPUT_DIR / f"{stem}_vocals.mp3")
    music_path  = str(OUTPUT_DIR / f"{stem}_music.mp3")

    # Method: Center channel extraction (pan filter)
    subprocess.run([
        "ffmpeg", "-i", file_path, "-af", "pan=mono|c0=FC", "-y", vocals_path
    ], capture_output=True, timeout=60)
    subprocess.run([
        "ffmpeg", "-i", file_path, "-af", "pan=stereo|FL=FL+0.5*FC|FR=FR+0.5*FC", "-y", music_path
    ], capture_output=True, timeout=60)

    if Path(vocals_path).exists() and Path(music_path).exists():
        return {"vocals": vocals_path, "music": music_path}

    # Fallback: use highpass/lowpass
    vocal_path2 = str(OUTPUT_DIR / f"{stem}_vocals2.mp3")
    music_path2 = str(OUTPUT_DIR / f"{stem}_music2.mp3")

    subprocess.run(["ffmpeg", "-i", file_path, "-af", "lowpass=f=3000", "-y", vocal_path2], capture_output=True, timeout=60)
    subprocess.run(["ffmpeg", "-i", file_path, "-af", "highpass=f=200", "-y", music_path2], capture_output=True, timeout=60)

    if Path(vocal_path2).exists() and Path(music_path2).exists():
        return {"vocals": vocal_path2, "music": music_path2}

    return None
