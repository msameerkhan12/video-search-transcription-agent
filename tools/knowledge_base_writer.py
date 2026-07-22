"""
Knowledge Base Writer

Saves a transcript + its video metadata as a structured JSON file under
/knowledge_base/, named by a slugified video title.

Note: on Hugging Face Spaces' free tier, /knowledge_base is ephemeral —
anything written here is lost on container restart unless a persistent
volume or external storage is wired up. See README "Known limitations".
"""
import json
import re
import time
from pathlib import Path
from typing import TypedDict

from config import KNOWLEDGE_BASE_DIR


class KBEntry(TypedDict):
    file_path: str
    file_name: str


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return slug[:60] if slug else "untitled"


def save_transcript(video_meta: dict, transcript: dict) -> KBEntry:
    """Write transcript + metadata to /knowledge_base/<slug>-<timestamp>.json"""
    slug = _slugify(video_meta.get("title", "untitled"))
    file_name = f"{slug}-{int(time.time())}.json"
    file_path = KNOWLEDGE_BASE_DIR / file_name

    record = {
        "video": video_meta,
        "transcript": transcript,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    return KBEntry(file_path=str(file_path), file_name=file_name)
