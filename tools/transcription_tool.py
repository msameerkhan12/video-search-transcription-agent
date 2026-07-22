"""
Tool 3: TranscriptionTool

Transcribes an audio file using Groq's hosted Whisper-large-v3. Groq's free
tier rejects uploads over 25MB with no server-side chunking (see
console.groq.com/docs/speech-to-text), so if our extracted file is too big
we split it into fixed-length chunks locally with pydub, transcribe each,
and stitch the text back together in order.
"""
from pathlib import Path
from typing import TypedDict

from groq import Groq
from pydub import AudioSegment

from config import GROQ_API_KEY, GROQ_FREE_TIER_MAX_BYTES, CHUNK_LENGTH_SECONDS, WHISPER_MODEL


class TranscriptionResult(TypedDict):
    text: str
    language: str
    duration_seconds: float


class TranscriptionError(Exception):
    """Raised when Groq's API can't produce a transcript, even after chunking."""


def _get_client() -> Groq:
    if not GROQ_API_KEY:
        raise TranscriptionError("GROQ_API_KEY is not set. Add it to your .env file.")
    return Groq(api_key=GROQ_API_KEY)


def _transcribe_single_file(client: Groq, file_path: str) -> dict:
    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            file=(Path(file_path).name, audio_file.read()),
            model=WHISPER_MODEL,
            response_format="verbose_json",
        )
    # groq SDK returns a pydantic-like object; normalize to a plain dict
    return response.model_dump() if hasattr(response, "model_dump") else dict(response)


def _split_into_chunks(file_path: str) -> list[str]:
    """Split an oversized audio file into CHUNK_LENGTH_SECONDS-long mp3 chunks."""
    audio = AudioSegment.from_file(file_path)
    chunk_ms = CHUNK_LENGTH_SECONDS * 1000
    chunk_paths = []

    src = Path(file_path)
    for i, start_ms in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start_ms : start_ms + chunk_ms]
        chunk_path = src.with_name(f"{src.stem}_chunk{i}.mp3")
        chunk.export(chunk_path, format="mp3", bitrate="128k")
        chunk_paths.append(str(chunk_path))

    return chunk_paths


def transcribe_audio(file_path: str) -> TranscriptionResult:
    """
    Transcribe an audio file, chunking automatically if it's too large for
    Groq's free-tier upload limit.

    Raises:
        TranscriptionError: if Groq's API fails outright (e.g. auth error,
            rate limit, unreadable audio).
    """
    client = _get_client()
    file_size = Path(file_path).stat().st_size

    if file_size <= GROQ_FREE_TIER_MAX_BYTES:
        try:
            result = _transcribe_single_file(client, file_path)
        except Exception as exc:
            raise TranscriptionError(f"Groq transcription failed: {exc}") from exc

        return TranscriptionResult(
            text=result.get("text", "").strip(),
            language=result.get("language", "unknown"),
            duration_seconds=result.get("duration", 0.0),
        )

    # File too large for a single request — chunk it.
    chunk_paths = _split_into_chunks(file_path)
    full_text_parts = []
    detected_language = "unknown"
    total_duration = 0.0

    try:
        for chunk_path in chunk_paths:
            try:
                result = _transcribe_single_file(client, chunk_path)
            except Exception as exc:
                raise TranscriptionError(
                    f"Groq transcription failed on a chunk of the audio: {exc}"
                ) from exc

            full_text_parts.append(result.get("text", "").strip())
            detected_language = result.get("language", detected_language)
            total_duration += result.get("duration", 0.0)
    finally:
        for chunk_path in chunk_paths:
            Path(chunk_path).unlink(missing_ok=True)

    return TranscriptionResult(
        text=" ".join(part for part in full_text_parts if part),
        language=detected_language,
        duration_seconds=total_duration,
    )
