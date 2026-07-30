import os
import re
import asyncio
import subprocess
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

PLATFORMS = [
    (r'youtube\.com|youtu\.be|music\.youtube', 'YouTube'),
    (r'facebook\.com|fb\.watch|fb\.com', 'Facebook'),
    (r'instagram\.com|instagr\.am', 'Instagram'),
    (r'tiktok\.com', 'TikTok'),
    (r'snapchat\.com', 'Snapchat'),
    (r'twitter\.com|x\.com', 'X (Twitter)'),
    (r'spotify\.com', 'Spotify'),
    (r'soundcloud\.com', 'SoundCloud'),
    (r'reddit\.com', 'Reddit'),
    (r'pinterest\.com|pin\.it', 'Pinterest'),
    (r'vimeo\.com', 'Vimeo'),
    (r'dailymotion\.com|dai\.ly', 'Dailymotion'),
    (r'twitch\.tv', 'Twitch'),
    (r'linkedin\.com', 'LinkedIn'),
    (r'mediafire\.com|mega\.nz|drive\.google|dropbox\.com', 'Cloud Storage'),
]

def detect_platform(url):
    for pattern, name in PLATFORMS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    if re.search(r'\.(mp3|mp4|wav|flac|ogg|avi|mkv|mov|pdf|zip|rar|jpg|jpeg|png|gif)$', url, re.IGNORECASE):
        return 'Direct Link'
    return 'Website'

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f]', '', name)
    return name.strip()[:100]

async def download_media(url):
    if not url.startswith(("http://", "https://")):
        return None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _download, url)
        return result
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return None

def _download(url):
    output = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")

    # Try audio first
    cmd = [
        "yt-dlp", url,
        "-o", output,
        "--no-playlist",
        "--print", "after_move:filename",
        "--print", "title",
        "--print", "duration_string",
        "--print", "filesize_approx",
        "--no-warnings",
        "--no-check-certificate",
        "--geo-bypass",
        "--extractor-args", "youtube:player_client=android",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "--max-filesize", "500M",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        # Try video
        cmd = [
            "yt-dlp", url,
            "-o", output,
            "--no-playlist",
            "--print", "after_move:filename",
            "--print", "title",
            "--print", "duration_string",
            "--print", "filesize_approx",
            "--no-warnings",
            "--no-check-certificate",
            "--geo-bypass",
            "--extractor-args", "youtube:player_client=android",
            "-f", "best[height<=1080]",
            "--max-filesize", "500M",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        # Final fallback
        cmd = [
            "yt-dlp", url,
            "-o", output,
            "--no-playlist",
            "--print", "after_move:filename",
            "--no-warnings",
            "--no-check-certificate",
            "--geo-bypass",
            "--max-filesize", "500M",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        stderr = result.stderr[:500]
        logger.error(f"yt-dlp error: {stderr}")
        return None

    lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
    if not lines:
        logger.error(f"No output from yt-dlp")
        return None

    file_path = lines[0]
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return None

    title = lines[1] if len(lines) > 1 else Path(file_path).stem
    duration = lines[2] if len(lines) > 2 else "?"
    size = float(lines[3]) if len(lines) > 3 and re.match(r'^[\d.]+$', lines[3]) else Path(file_path).stat().st_size / (1024*1024)

    return {
        "file_path": file_path,
        "title": sanitize_filename(title),
        "duration": duration,
        "size": size,
    }
