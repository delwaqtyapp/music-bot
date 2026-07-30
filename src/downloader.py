import os
import re
import asyncio
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
COOKIES_DIR = Path("cookies")
COOKIES_DIR.mkdir(exist_ok=True)

PLATFORMS = [
    (r'youtube\.com/shorts/', 'YouTube Shorts'),
    (r'youtube\.com|youtu\.be|music\.youtube\.com', 'YouTube'),
    (r'facebook\.com/reel/', 'Facebook Reels'),
    (r'facebook\.com|fb\.watch|fb\.com', 'Facebook'),
    (r'instagram\.com/reel/', 'Instagram Reels'),
    (r'instagram\.com/stories/', 'Instagram Stories'),
    (r'instagram\.com/p/', 'Instagram Post'),
    (r'instagram\.com|instagr\.am', 'Instagram'),
    (r'tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com', 'TikTok'),
    (r'snapchat\.com/spotlight/', 'Snapchat Spotlight'),
    (r'snapchat\.com/story/', 'Snapchat Story'),
    (r'snapchat\.com/p/', 'Snapchat Profile'),
    (r'snapchat\.com/add/', 'Snapchat Add'),
    (r'snapchat\.com/lens/', 'Snapchat Lens'),
    (r'snapchat\.com/discover/', 'Snapchat Discover'),
    (r'snapchat\.com/t/', 'Snapchat Link'),
    (r'snapchat\.com|story\.snapchat\.com|t\.snapchat\.com', 'Snapchat'),
    (r'twitter\.com|x\.com', 'X (Twitter)'),
    (r'spotify\.com', 'Spotify'),
    (r'soundcloud\.com', 'SoundCloud'),
    (r'reddit\.com', 'Reddit'),
    (r'pinterest\.com|pin\.it', 'Pinterest'),
    (r'vimeo\.com', 'Vimeo'),
    (r'dailymotion\.com|dai\.ly', 'Dailymotion'),
    (r'twitch\.tv', 'Twitch'),
    (r'linkedin\.com/posts/', 'LinkedIn Post'),
    (r'linkedin\.com/feed/update/', 'LinkedIn Feed'),
    (r'linkedin\.com/learning/', 'LinkedIn Learning'),
    (r'linkedin\.com/events/', 'LinkedIn Event'),
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

def save_cookies(user_id, filepath):
    dest = COOKIES_DIR / f"{user_id}.txt"
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        if '# Netscape HTTP Cookie File' in content or '#' in content[:50]:
            dest.write_text(content, encoding='utf-8')
            return True
    except:
        pass
    return False

def get_cookies_path(user_id):
    path = COOKIES_DIR / f"{user_id}.txt"
    return str(path) if path.exists() else None

def _run_ytdlp(url, out_tmpl, cookies=None):
    base = [
        "yt-dlp", url, "-o", out_tmpl,
        "--no-playlist", "--no-warnings",
        "--no-check-certificate", "--geo-bypass",
        "--max-filesize", "500M",
        "--print", "after_move:filepath",
        "--print", "title",
        "--print", "duration_string",
        "--print", "filesize_approx",
        "--restrict-filenames",
    ]
    if cookies:
        base.extend(["--cookies", cookies])
    yt_extractor = "youtube:player_client=android,youtube_web"
    strategies = [
        [*base, "--extractor-args", yt_extractor, "-x", "--audio-format", "mp3", "--audio-quality", "0"],
        [*base, "--extractor-args", yt_extractor, "-f", "best[height<=1080]"],
        [*base, "--extractor-args", yt_extractor, "-f", "best"],
        [*base, "-f", "best"],
        base,
    ]
    for i, strategy in enumerate(strategies):
        logger.info(f"yt-dlp strategy {i+1}/{len(strategies)}")
        try:
            result = subprocess.run(strategy, capture_output=True, text=True, timeout=300)
            if result.stderr:
                logger.debug(f"yt-dlp stderr: {result.stderr[:300]}")
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
                if lines and Path(lines[0]).exists():
                    logger.info(f"yt-dlp success: {lines[0]}")
                    return lines
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp timeout")
        except Exception as e:
            logger.warning(f"yt-dlp error: {e}")
    return None

def _run_gallerydl(url, out_dir):
    args = ["gallery-dl", url, "-d", str(out_dir)]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if result.stderr:
            logger.info(f"gallery-dl stderr: {result.stderr[:300]}")
        if result.returncode == 0:
            files = sorted(out_dir.iterdir(), key=lambda f: f.stat().st_mtime)
            if files:
                latest = files[-1]
                logger.info(f"gallery-dl success: {latest}")
                return [str(latest), latest.stem, "?", str(latest.stat().st_size / (1024*1024))]
    except Exception as e:
        logger.warning(f"gallery-dl error: {e}")
    return None

async def download_media(url, user_id=None):
    if not url.startswith(("http://", "https://")):
        return None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _download, url, user_id)
        return result
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return None

def _download(url, user_id=None):
    cookies = get_cookies_path(user_id) if user_id else None
    out_tmpl = str(DOWNLOAD_DIR / "%(title)s_%(id)s.%(ext)s")
    lines = _run_ytdlp(url, out_tmpl, cookies)
    if not lines:
        logger.info("yt-dlp failed, trying gallery-dl fallback...")
        fallback_dir = DOWNLOAD_DIR / "gallery"
        fallback_dir.mkdir(exist_ok=True)
        lines = _run_gallerydl(url, fallback_dir)
    if not lines:
        logger.error(f"All methods failed for {url}")
        return None
    file_path = lines[0]
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return None
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
