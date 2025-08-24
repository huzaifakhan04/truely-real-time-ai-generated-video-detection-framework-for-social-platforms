import os
import uuid
import subprocess

def download_audio(video_url: str, temporary_directory: str, max_secs: int) -> str:
    audio_id = uuid.uuid4().hex
    out_tpl = os.path.join(temporary_directory, f"auth_{audio_id}.%(ext)s")
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
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=max_secs + 120)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"yt-dlp failed: {e.stderr or e.stdout}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("Audio download timed out")

    mp3_path = out_tpl.replace("%(ext)s", "mp3")
    if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
        raise RuntimeError("Audio file missing or empty after download")
    return mp3_path

def extract_audio(video_path, audio_path):
    try:
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return False
        output_dir = os.path.dirname(audio_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            audio_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            print(f"Audio extracted successfully to {audio_path}")
            return True
        else:
            print(f"Audio extraction failed: Output file empty or missing")
            return False
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error during audio extraction: {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        print(f"Error extracting audio: {str(e)}")
        return False