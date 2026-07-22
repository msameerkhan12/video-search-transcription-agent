"""
Central configuration. Everything that would otherwise be a magic number
lives here so the tools/agent stay readable.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# --- Audio / Groq constraints ---
# Groq's free-tier Whisper endpoint rejects uploads over 25MB and does not
# chunk for you (checked against console.groq.com/docs/speech-to-text, Jul 2026).
# We stay well under that by capping source video length and re-checking the
# extracted file size before upload, chunking if needed.
MAX_VIDEO_DURATION_SECONDS = 60 * 60  # reject videos longer than 60 minutes
GROQ_FREE_TIER_MAX_BYTES = 25 * 1024 * 1024  # 25MB
CHUNK_LENGTH_SECONDS = 600  # 10-minute chunks when a file needs splitting
WHISPER_MODEL = "whisper-large-v3"

# --- Storage ---
BASE_DIR = Path(__file__).resolve().parent
TEMP_AUDIO_DIR = BASE_DIR / "temp_audio"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

TEMP_AUDIO_DIR.mkdir(exist_ok=True)
KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)
