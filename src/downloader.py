import os
import re
import shlex
import asyncio
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

async def download_media(url):
    if not url.startswith(("http://", "https://")):
        return None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _download, url)
        return result
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None

def _download(url):
    output = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")

    # Download best audio
    cmd = [
        "yt-dlp", url,
        "-o", output,
        "--no-playlist",
        "--print", "after_move:filename",
        "--print", "title",
        "--print", "duration_string",
        "--no-warnings",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        # Fallback: download best video
        cmd = [
            "yt-dlp", url,
            "-o", output,
            "--no-playlist",
            "--print", "after_move:filename",
            "--print", "title",
            "--print", "duration_string",
            "--no-warnings",
            "-f", "best",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            logger.error(f"yt-dlp error: {result.stderr[:200]}")
            return None

    lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
    if not lines:
        logger.error(f"No output from yt-dlp: {result.stderr[:200]}")
        return None

    file_path = lines[0]
    title = lines[1] if len(lines) > 1 else Path(file_path).stem
    duration = lines[2] if len(lines) > 2 else "0:00"
    size_mb = Path(file_path).stat().st_size / (1024 * 1024) if Path(file_path).exists() else 0

    return {
        "file_path": file_path,
        "title": title,
        "duration": duration,
        "size": size_mb,
    }
