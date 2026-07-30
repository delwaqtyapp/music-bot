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
    if os.sys.platform == "linux":
        try:
            subprocess.run(["apt-get", "update", "-qq"], capture_output=True, timeout=60)
            subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], capture_output=True, timeout=120)
            if shutil.which("ffmpeg"):
                logger.info("Installed ffmpeg via apt")
                return
        except Exception as e:
            logger.warning(f"apt install ffmpeg failed: {e}")
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        if shutil.which("ffmpeg"):
            logger.info("Added ffmpeg via static_ffmpeg")
            return
    except ImportError:
        pass
    logger.warning("FFmpeg not available")

def _run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            logger.debug(f"FFmpeg error: {r.stderr.decode(errors='ignore')[-200:]}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning(f"FFmpeg timed out: {' '.join(cmd[-4:])}")
        return False
    except Exception as e:
        logger.error(f"FFmpeg exec error: {e}")
        return False

def _audio_channels(file_path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 2
    r = subprocess.run([
        ffprobe, "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=channels",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ], capture_output=True, timeout=30)
    try:
        return int(r.stdout.decode(errors='ignore').strip())
    except (ValueError, TypeError):
        return 2

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
    music_path = f"{out_base}_music.mp3"

    is_mono = _audio_channels(file_path) == 1

    # Strategy 1: Center channel extraction
    if is_mono:
        r1 = _run([
            ffmpeg, "-i", file_path,
            "-af", "lowpass=f=8000,highpass=f=85,volume=2.0",
            "-b:a", "192k", "-y", vocals_path
        ])
    else:
        r1 = _run([
            ffmpeg, "-i", file_path,
            "-af", "pan=mono|c0=0.5*FL+0.5*FR,lowpass=f=8000,highpass=f=85,volume=2.5",
            "-b:a", "192k", "-y", vocals_path
        ])
    v_ok = r1 and Path(vocals_path).exists() and Path(vocals_path).stat().st_size > 2048

    # Strategy 2: Phase inversion for music
    m_ok = False
    if v_ok:
        m_ok = _run([
            ffmpeg, "-i", file_path, "-i", vocals_path,
            "-filter_complex",
            "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[orig];"
            "[1:a]aformat=sample_rates=44100:channel_layouts=mono,volume=-1[voc_inv];"
            "[orig][voc_inv]amix=inputs=2:duration=first:dropout_transition=2[music]",
            "-map", "[music]", "-ac", "2", "-b:a", "192k", "-y", music_path
        ])
        m_ok = m_ok and Path(music_path).exists() and Path(music_path).stat().st_size > 2048
        if m_ok:
            logger.info("Separation: center+phase-invert")
            return {"vocals": vocals_path, "music": music_path}

    # Fallback: frequency-split
    if not v_ok:
        if is_mono:
            v_ok = _run([
                ffmpeg, "-i", file_path,
                "-af", "lowpass=f=8000,highpass=f=85,volume=2.0",
                "-b:a", "192k", "-y", vocals_path
            ])
        else:
            v_ok = _run([
                ffmpeg, "-i", file_path,
                "-af", "pan=mono|c0=0.5*FL+0.5*FR,volume=2.0",
                "-b:a", "192k", "-y", vocals_path
            ])
        v_ok = v_ok and Path(vocals_path).exists() and Path(vocals_path).stat().st_size > 2048

    if not m_ok:
        m_ok = _run([
            ffmpeg, "-i", file_path,
            "-af", "pan=stereo|FL=FL-FR|FR=FR-FL,volume=0.7",
            "-b:a", "192k", "-y", music_path
        ])
        m_ok = m_ok and Path(music_path).exists() and Path(music_path).stat().st_size > 2048

    if v_ok and m_ok:
        logger.info("Separation: frequency-split")
        return {"vocals": vocals_path, "music": music_path}

    # Final fallback: basic highpass/lowpass
    if not v_ok:
        _run([ffmpeg, "-i", file_path, "-af", "lowpass=f=4000,highpass=f=85,volume=1.5",
              "-b:a", "192k", "-y", vocals_path])
    if not m_ok:
        _run([ffmpeg, "-i", file_path, "-af", "highpass=f=200,lowpass=f=8000,volume=0.5",
              "-b:a", "192k", "-y", music_path])

    if Path(vocals_path).exists() and Path(vocals_path).stat().st_size > 2048 and \
       Path(music_path).exists() and Path(music_path).stat().st_size > 2048:
        return {"vocals": vocals_path, "music": music_path}

    if Path(vocals_path).exists() and Path(vocals_path).stat().st_size > 2048:
        logger.warning("Music fallback failed, returning vocals only")
        return {"vocals": vocals_path, "music": vocals_path}

    return None

def _separate_video(file_path):
    ffmpeg = get_ffmpeg_path()
    sep = _separate(file_path)
    if not sep:
        return None
    stem = Path(file_path).stem
    output_path = str(OUTPUT_DIR / f"{stem}_vocals_only.mp4")

    def try_mux(out, reencode=False):
        cmd = [
            ffmpeg, "-i", file_path, "-i", sep["vocals"],
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "aac", "-b:a", "192k",
            "-af", "aresample=async=1",
            "-shortest", "-movflags", "+faststart",
            "-y", out
        ]
        if reencode:
            cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
        else:
            cmd += ["-c:v", "copy"]
        return _run(cmd, timeout=300) and Path(out).exists() and Path(out).stat().st_size > 4096

    if try_mux(output_path):
        return output_path
    out2 = str(OUTPUT_DIR / f"{stem}_vocals_only_fb.mp4")
    if try_mux(out2, reencode=True):
        return out2
    logger.error("Video remux failed entirely")
    return None
