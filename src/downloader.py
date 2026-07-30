import os
import re
import asyncio
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

PLATFORMS = [
    (r'youtube\.com|youtu\.be|music\.youtube', 'youtube music'),
    (r'youtube\.com|youtu\.be', 'youtube'),
    (r'facebook\.com|fb\.watch|fb\.com', 'facebook'),
    (r'instagram\.com|instagr\.am', 'instagram'),
    (r'tiktok\.com', 'tiktok'),
    (r'snapchat\.com|snapchat\.com', 'snapchat'),
    (r'twitter\.com|x\.com', 'twitter'),
    (r'spotify\.com', 'spotify'),
    (r'soundcloud\.com', 'soundcloud'),
    (r'reddit\.com', 'reddit'),
    (r'pinterest\.com|pin\.it', 'pinterest'),
    (r'vimeo\.com', 'vimeo'),
    (r'dailymotion\.com|dai\.ly', 'dailymotion'),
    (r'twitch\.tv', 'twitch'),
    (r't\.me|telegram\.me', 'telegram'),
    (r'whatsapp\.com', 'whatsapp'),
    (r'linkedin\.com', 'linkedin'),
    (r'mediafire\.com|mega\.nz|drive\.google|dropbox\.com', 'direct'),
]

def detect_platform(url):
    for pattern, name in PLATFORMS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    if re.search(r'\.(mp3|mp4|wav|flac|ogg|avi|mkv|mov|pdf|zip|rar)$', url, re.IGNORECASE):
        return 'direct download'
    return 'unknown'

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

EXTRACTOR_ARGS = "--extractor-args youtube:player_client=android --extractor-args youtube:skip=webpage"

def _download(url):
    output = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    ea = EXTRACTOR_ARGS.split()

    # Try best audio first
    cmd = [
        "yt-dlp", url,
        "-o", output,
        "--no-playlist",
        "--print", "after_move:filename",
        "--print", "title",
        "--print", "duration_string",
        "--print", "filesize_approx",
        "--no-warnings",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "--max-filesize", "500M",
    ] + ea
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        # Fallback: best video
        cmd = [
            "yt-dlp", url,
            "-o", output,
            "--no-playlist",
            "--print", "after_move:filename",
            "--print", "title",
            "--print", "duration_string",
            "--print", "filesize_approx",
            "--no-warnings",
            "-f", "best",
            "--max-filesize", "500M",
        ] + ea
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            # Last fallback: generic download
            cmd = [
                "yt-dlp", url,
                "-o", output,
                "--no-playlist",
                "--print", "after_move:filename",
                "--no-warnings",
                "--max-filesize", "500M",
            ] + ea
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        logger.error(f"yt-dlp failed: {result.stderr[:300]}")
        return None

    lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
    if not lines:
        logger.error(f"No output from yt-dlp: {result.stderr[:300]}")
        return None

    file_path = lines[0]
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return None

    title = lines[1] if len(lines) > 1 else Path(file_path).stem
    duration = lines[2] if len(lines) > 2 else "?"
    size = float(lines[3]) if len(lines) > 3 and lines[3].replace('.','').replace(',','').isdigit() else Path(file_path).stat().st_size / (1024*1024)

    return {
        "file_path": file_path,
        "title": title,
        "duration": duration,
        "size": size,
    }
