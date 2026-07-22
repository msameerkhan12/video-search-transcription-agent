"""
Tool 2: AudioExtractionTool

Downloads a YouTube video's audio track only (via yt-dlp) and saves it as an
mp3 in a temp directory. Enforces a duration cap up front so we never pull
down more than Groq's free-tier Whisper endpoint can handle later.
"""
import uuid
from pathlib import Path

import yt_dlp

from config import TEMP_AUDIO_DIR, MAX_VIDEO_DURATION_SECONDS


class AudioExtractionError(Exception):
    """Raised on duration-cap violations or yt-dlp failures."""


def extract_audio(video_url: str) -> str:
    """
    Download and extract audio-only from a YouTube URL.

    Returns:
        Absolute path to the extracted mp3 file.

    Raises:
        AudioExtractionError: if the video exceeds the duration cap, or
            extraction otherwise fails.
    """
    job_id = uuid.uuid4().hex[:8]
    output_template = str(TEMP_AUDIO_DIR / f"{job_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",  # keeps files smaller, plenty for ASR
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            duration = info.get("duration") or 0

            if duration > MAX_VIDEO_DURATION_SECONDS:
                raise AudioExtractionError(
                    f"Video is {duration // 60} minutes long, which exceeds the "
                    f"{MAX_VIDEO_DURATION_SECONDS // 60}-minute cap. Choose a shorter video."
                )

            ydl.download([video_url])
    except AudioExtractionError:
        raise
    except Exception as exc:
        raise AudioExtractionError(f"yt-dlp failed to extract audio: {exc}") from exc

    audio_path = TEMP_AUDIO_DIR / f"{job_id}.mp3"
    if not audio_path.exists():
        raise AudioExtractionError("Audio extraction reported success but no file was produced.")

    return str(audio_path)


def cleanup_audio_file(file_path: str) -> None:
    """Delete a temp audio file. Safe to call even if it's already gone."""
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        pass  # cleanup is best-effort; never let it crash the pipeline
