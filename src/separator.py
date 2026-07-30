import os
import asyncio
import subprocess
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

def get_ffmpeg_location():
    """Return dir containing ffmpeg for yt-dlp --ffmpeg-location"""
    _ensure_ffmpeg()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return os.path.dirname(ffmpeg)
    return ""

def get_ffmpeg_path():
    _ensure_ffmpeg()
    return shutil.which("ffmpeg") or "ffmpeg"

def _ensure_ffmpeg():
    if shutil.which("ffmpeg"):
        return
    # Install via apt on Linux (Railway)
    if os.sys.platform == "linux":
        try:
            subprocess.run(["apt-get", "update", "-qq"], capture_output=True, timeout=60)
            subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], capture_output=True, timeout=120)
            if shutil.which("ffmpeg"):
                logger.info("Installed ffmpeg via apt")
                return
        except Exception as e:
            logger.warning(f"apt install ffmpeg failed: {e}")
    # Try static_ffmpeg
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        if shutil.which("ffmpeg"):
            logger.info("Added ffmpeg via static_ffmpeg")
            return
    except ImportError:
        pass
    logger.warning("FFmpeg not available")

async def separate_audio(file_path):
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _separate, file_path)
    except Exception as e:
        logger.error(f"Separation failed: {e}")
        return None

async def separate_video(file_path):
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _separate_video, file_path)
    except Exception as e:
        logger.error(f"Video separation failed: {e}")
        return None

def _separate(file_path):
    ffmpeg = get_ffmpeg_path()
    if not shutil.which("ffmpeg"):
        logger.error("FFmpeg not installed")
        return None
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return None

    stem = Path(file_path).stem
    out_base = str(OUTPUT_DIR / stem)
    vocals_path = f"{out_base}_vocals.mp3"
    music_path  = f"{out_base}_music.mp3"

    # Strategy 1: Center channel (L+R)/2 + bandpass → vocals
    # This works on ALL FFmpeg versions (no afftdn)
    # pan=mono|c0=0.5*FL+0.5*FR extracts the center-panned audio
    r1 = subprocess.run([
        ffmpeg, "-i", file_path,
        "-af", "pan=mono|c0=0.5*FL+0.5*FR,lowpass=f=8000,highpass=f=80,volume=2.0",
        "-b:a", "192k", "-y", vocals_path
    ], capture_output=True, timeout=120)
    v_ok = r1.returncode == 0 and Path(vocals_path).exists() and Path(vocals_path).stat().st_size > 2048

    if v_ok:
        # Generate music: original - vocals (phase inversion)
        r2 = subprocess.run([
            ffmpeg, "-i", file_path, "-i", vocals_path,
            "-filter_complex",
            "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[orig];"
            "[1:a]aformat=sample_rates=44100:channel_layouts=mono,volume=-1[voc_inv];"
            "[orig][voc_inv]amix=inputs=2:duration=first:dropout_transition=2[music]",
            "-map", "[music]", "-ac", "2", "-b:a", "192k", "-y", music_path
        ], capture_output=True, timeout=120)
        m_ok = r2.returncode == 0 and Path(music_path).exists() and Path(music_path).stat().st_size > 2048
        if m_ok:
            logger.info("Separation OK: center+phase-invert")
            return {"vocals": vocals_path, "music": music_path}

    # Fallback 2: simple band-split for both
    if not v_ok:
        subprocess.run([
            ffmpeg, "-i", file_path,
            "-af", "pan=mono|c0=0.5*FL+0.5*FR,volume=2.0",
            "-b:a", "192k", "-y", vocals_path
        ], capture_output=True, timeout=120)
    if not Path(music_path).exists() or Path(music_path).stat().st_size <= 2048:
        subprocess.run([
            ffmpeg, "-i", file_path,
            "-af", "highpass=f=200,lowpass=f=8000,volume=0.7",
            "-b:a", "192k", "-y", music_path
        ], capture_output=True, timeout=120)
    if Path(vocals_path).exists() and Path(vocals_path).stat().st_size > 2048 and \
       Path(music_path).exists() and Path(music_path).stat().st_size > 2048:
        return {"vocals": vocals_path, "music": music_path}

    return None

def _separate_video(file_path):
    ffmpeg = get_ffmpeg_path()
    sep = _separate(file_path)
    if not sep:
        return None
    stem = Path(file_path).stem
    output_path = str(OUTPUT_DIR / f"{stem}_vocals_only.mp4")
    r = subprocess.run([
        ffmpeg, "-i", file_path, "-i", sep["vocals"],
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", "aresample=async=1",
        "-shortest", "-movflags", "+faststart",
        "-y", output_path
    ], capture_output=True, timeout=180)
    if r.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 4096:
        return output_path
    # Try fallback: re-encode video too (some codecs don't copy well)
    out2 = str(OUTPUT_DIR / f"{stem}_vocals_only_fb.mp4")
    r2 = subprocess.run([
        ffmpeg, "-i", file_path, "-i", sep["vocals"],
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", "aresample=async=1",
        "-shortest", "-movflags", "+faststart",
        "-y", out2
    ], capture_output=True, timeout=300)
    if r2.returncode == 0 and Path(out2).exists() and Path(out2).stat().st_size > 4096:
        return out2
    logger.error(f"Video remux failed:\n  {r.stderr.decode(errors='ignore')[-500:]}")
    return None
