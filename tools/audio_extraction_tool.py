"""
Tool 2: AudioExtractionTool

Downloads a YouTube video's audio track only (via yt-dlp) and saves it as an
mp3 in a temp directory. Enforces a duration cap up front so we never pull
down more than Groq's free-tier Whisper endpoint can handle later.
"""
import uuid
from pathlib import Path

import yt_dlp

from config import TEMP_AUDIO_DIR, MAX_VIDEO_DURATION_SECONDS, YOUTUBE_COOKIES_FILE


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
        "format": "bestaudio[protocol^=http]/bestaudio/best",
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
        # Cloud-hosted IPs (Railway, HF Spaces, etc.) get flagged by YouTube's
        # bot detection far more often than home connections. Cookies (added
        # below) handle most of that now, so we prefer the web client first —
        # it needs a JS runtime to solve YouTube's PO token / SABR challenges,
        # which the Dockerfile installs nodejs for. Android is kept as a
        # fallback for videos where the web client still comes up short.
        # "formats: missing_pot" stops yt-dlp from silently hiding formats
        # that require a PO token instead of erroring out entirely.
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"],
                "formats": ["missing_pot"],
            }
        },
    }

    # Cookies are the most reliable fix for YouTube's bot detection on
    # cloud-hosted IPs. Only attached if YOUTUBE_COOKIES_B64 was set and
    # decoded successfully at startup (see config.py) — safe to skip
    # otherwise, yt-dlp just falls back to the client-spoofing above.
    if YOUTUBE_COOKIES_FILE.exists():
        ydl_opts["cookiefile"] = str(YOUTUBE_COOKIES_FILE)

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