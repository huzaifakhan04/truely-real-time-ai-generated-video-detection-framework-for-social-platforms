import os
import uuid
import subprocess

from news_authenticity_api.utils.logger import get_logger

logger = get_logger(__name__)


def download_audio(video_url: str, tmp_dir: str, max_secs: int) -> str:
    """
    Download the first <= N seconds of audio from a YouTube video.

    Args:
        video_url: The URL of the YouTube video
        tmp_dir: The directory to save the audio file
        max_secs: The maximum number of seconds of audio to download

    Returns:
        The path to the downloaded audio file

    Raises:
        RuntimeError: If the audio download fails
    """
    audio_id = uuid.uuid4().hex
    out_tpl = os.path.join(tmp_dir, f"auth_{audio_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "--ignore-errors",
        "-x",
        "--audio-format", "mp3",
        "--download-sections", f"*0-{max_secs}",
        "-o", out_tpl,
        video_url,
    ]
    logger.info("downloading audio (<=%ss) via yt-dlp", max_secs)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=max_secs + 120)
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp failed: %s", e.stderr or e.stdout)
        raise RuntimeError(f"yt-dlp failed: {e.stderr or e.stdout}") from e
    except subprocess.TimeoutExpired:
        logger.error("audio download timed out")
        raise RuntimeError("Audio download timed out")

    mp3_path = out_tpl.replace("%(ext)s", "mp3")
    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
        raise RuntimeError("Audio file missing or empty after download")
    logger.info("audio downloaded: path=%s size_bytes=%d", mp3_path, os.path.getsize(mp3_path))
    return mp3_path


