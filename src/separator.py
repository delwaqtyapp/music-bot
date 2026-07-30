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
        return await loop.run_in_executor(None, _separate, file_path)
    except Exception as e:
        logger.error(f"Separation failed: {e}")
        return None

def _separate(file_path):
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return None

    stem = Path(file_path).stem
    out_base = str(OUTPUT_DIR / stem)

    # Method 1: Center channel extraction (pan filter)
    vocals_path = f"{out_base}_vocals.mp3"
    music_path  = f"{out_base}_music.mp3"

    r1 = subprocess.run([
        "ffmpeg", "-i", file_path,
        "-af", "pan=mono|c0=FC",
        "-b:a", "192k",
        "-y", vocals_path
    ], capture_output=True, timeout=120)

    r2 = subprocess.run([
        "ffmpeg", "-i", file_path,
        "-af", "pan=stereo|FL=FL+0.5*FC|FR=FR+0.5*FC",
        "-b:a", "192k",
        "-y", music_path
    ], capture_output=True, timeout=120)

    if r1.returncode == 0 and r2.returncode == 0 and Path(vocals_path).exists() and Path(music_path).exists():
        return {"vocals": vocals_path, "music": music_path}

    # Method 2: Highpass/Lowpass filter
    vocals_path2 = f"{out_base}_vocals2.mp3"
    music_path2  = f"{out_base}_music2.mp3"

    r3 = subprocess.run([
        "ffmpeg", "-i", file_path,
        "-af", "lowpass=f=4000,highpass=f=80",
        "-b:a", "192k", "-y", vocals_path2
    ], capture_output=True, timeout=120)

    r4 = subprocess.run([
        "ffmpeg", "-i", file_path,
        "-af", "highpass=f=400,lowpass=f=200",
        "-b:a", "192k", "-y", music_path2
    ], capture_output=True, timeout=120)

    if r3.returncode == 0 and r4.returncode == 0 and Path(vocals_path2).exists() and Path(music_path2).exists():
        return {"vocals": vocals_path2, "music": music_path2}

    return None
