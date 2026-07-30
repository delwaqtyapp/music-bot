import os
import asyncio
import subprocess
import logging
import shutil
import requests
from pathlib import Path

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

FFMPEG_URLS = {
    "linux": "https://github.com/eugenesvk/ffmpeg-static/releases/latest/download/ffmpeg-linux64",
    "win32": "https://github.com/eugenesvk/ffmpeg-static/releases/latest/download/ffmpeg-win64.exe",
    "darwin": "https://github.com/eugenesvk/ffmpeg-static/releases/latest/download/ffmpeg-darwin64",
}

def _get_ffmpeg():
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    local = Path("ffmpeg")
    if local.exists():
        return str(local.absolute())
    platform = os.sys.platform
    url = FFMPEG_URLS.get(platform)
    if not url:
        return None
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        local.write_bytes(r.content)
        local.chmod(0o755)
        logger.info(f"Downloaded static ffmpeg to {local}")
        return str(local.absolute())
    except Exception as e:
        logger.error(f"Failed to download ffmpeg: {e}")
        return None

async def separate_audio(file_path):
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _separate, file_path)
    except Exception as e:
        logger.error(f"Separation failed: {e}")
        return None

def _separate(file_path):
    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        logger.error("FFmpeg not available")
        return None
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return None
    stem = Path(file_path).stem
    out_base = str(OUTPUT_DIR / stem)
    vocals_path = f"{out_base}_vocals.mp3"
    music_path  = f"{out_base}_music.mp3"
    r1 = subprocess.run([
        ffmpeg, "-i", file_path,
        "-af", "pan=mono|c0=FC",
        "-b:a", "192k",
        "-y", vocals_path
    ], capture_output=True, timeout=120)
    r2 = subprocess.run([
        ffmpeg, "-i", file_path,
        "-af", "pan=stereo|FL=FL+0.5*FC|FR=FR+0.5*FC",
        "-b:a", "192k",
        "-y", music_path
    ], capture_output=True, timeout=120)
    if r1.returncode == 0 and r2.returncode == 0 and Path(vocals_path).exists() and Path(music_path).exists():
        return {"vocals": vocals_path, "music": music_path}
    vocals_path2 = f"{out_base}_vocals2.mp3"
    music_path2  = f"{out_base}_music2.mp3"
    r3 = subprocess.run([
        ffmpeg, "-i", file_path,
        "-af", "lowpass=f=4000,highpass=f=80",
        "-b:a", "192k", "-y", vocals_path2
    ], capture_output=True, timeout=120)
    r4 = subprocess.run([
        ffmpeg, "-i", file_path,
        "-af", "highpass=f=400,lowpass=f=200",
        "-b:a", "192k", "-y", music_path2
    ], capture_output=True, timeout=120)
    if r3.returncode == 0 and r4.returncode == 0 and Path(vocals_path2).exists() and Path(music_path2).exists():
        return {"vocals": vocals_path2, "music": music_path2}
    return None
