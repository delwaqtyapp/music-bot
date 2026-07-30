import os
import re
import json
import asyncio
import subprocess
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

PLATFORMS = [
    (r'youtube\.com|youtu\.be|music\.youtube', 'YouTube'),
    (r'youtube\.com/shorts/', 'YouTube Shorts'),
    (r'facebook\.com|fb\.watch|fb\.com', 'Facebook'),
    (r'facebook\.com/reel/', 'Facebook Reels'),
    (r'facebook\.com/stories/', 'Facebook Stories'),
    (r'instagram\.com|instagr\.am', 'Instagram'),
    (r'instagram\.com/reel/', 'Instagram Reels'),
    (r'instagram\.com/stories/', 'Instagram Stories'),
    (r'instagram\.com/p/', 'Instagram Post'),
    (r'tiktok\.com', 'TikTok'),
    (r'tiktok\.com/@.*/video/', 'TikTok Video'),
    (r'tiktok\.com/@.*/photo/', 'TikTok Photo'),
    (r'snapchat\.com/spotlight/', 'Snapchat Spotlight'),
    (r'snapchat\.com/story/', 'Snapchat Story'),
    (r'snapchat\.com/p/', 'Snapchat Profile'),
    (r'snapchat\.com/add/', 'Snapchat Add'),
    (r'snapchat\.com/lens/', 'Snapchat Lens'),
    (r'snapchat\.com/discover/', 'Snapchat Discover'),
    (r'snapchat\.com/t/', 'Snapchat Link'),
    (r'snapchat\.com', 'Snapchat'),
    (r'story\.snapchat\.com', 'Snapchat Story'),
    (r't\.snapchat\.com', 'Snapchat Link'),
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
    (r'telegram\.org|t\.me', 'Telegram'),
    (r'whatsapp\.com', 'WhatsApp'),
]

def detect_platform(url):
    for pattern, name in PLATFORMS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    ext_match = re.search(r'\.(mp3|mp4|wav|flac|ogg|avi|mkv|mov|pdf|zip|rar|jpg|jpeg|png|gif|webp|webm|m4a|aac|opus)$', url, re.IGNORECASE)
    if ext_match:
        return f'File ({ext_match.group(1)})'
    return 'Website'

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()[:100]

def _get_extractor_args():
    """Get YouTube extractor args that help avoid bot detection"""
    return "youtube:player_client=android,youtube_web;youtube:skip=webpage"

def _run_ytdlp(args, timeout=300):
    """Run yt-dlp with the given args"""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp timeout for {' '.join(args[:3])}")
        return None
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

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
    out_tmpl = str(DOWNLOAD_DIR / "%(title)s_%(id)s.%(ext)s")
    base_args = [
        "yt-dlp", url, "-o", out_tmpl,
        "--no-playlist",
        "--no-warnings",
        "--no-check-certificate",
        "--geo-bypass",
        "--extractor-args", _get_extractor_args(),
        "--max-filesize", "500M",
        "--print", "after_move:filepath",
        "--print", "title",
        "--print", "duration_string",
        "--print", "filesize_approx",
        "--restrict-filenames",
    ]

    strategies = [
        [*base_args, "-x", "--audio-format", "mp3", "--audio-quality", "0"],
        [*base_args, "-f", "best[height<=1080]"],
        [*base_args, "-f", "best"],
        [*base_args],
    ]

    for args in strategies:
        logger.info(f"Trying yt-dlp with: {' '.join(args[2:8])}")
        result = _run_ytdlp(args)
        if result and result.returncode == 0:
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            if lines:
                file_path = lines[0]
                if Path(file_path).exists():
                    title = sanitize_filename(lines[1]) if len(lines) > 1 else Path(file_path).stem
                    duration = lines[2] if len(lines) > 2 else "?"
                    size_str = lines[3] if len(lines) > 3 else "0"
                    try:
                        size = float(size_str) if re.match(r'^[\d.]+$', size_str) else Path(file_path).stat().st_size / (1024*1024)
                    except:
                        size = Path(file_path).stat().st_size / (1024*1024)
                    return {
                        "file_path": file_path,
                        "title": title,
                        "duration": duration,
                        "size": size,
                    }

    stderr = result.stderr[:500] if result and hasattr(result, 'stderr') else "Unknown error"
    if result:
        logger.error(f"yt-dlp failed: {stderr}")
    # Better error for Snapchat non-spotlight
    if 'snapchat' in url and 'spotlight' not in url:
        logger.warning("Snapchat non-spotlight URLs need authentication - try a Spotlight link instead")
    return None
