"""
api.py — FastAPI app that wraps the LangGraph agent pipeline over HTTP.

Run locally with: uvicorn api:app --reload --port 8000
"""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_pipeline
from config import ALLOWED_ORIGINS, KNOWLEDGE_BASE_DIR

app = FastAPI(title="Video Search & Transcription Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    query: str


class RunResponse(BaseModel):
    success: bool
    video_meta: dict | None = None
    transcript_path: str | None = None
    transcript_preview: str | None = None
    transcript_full: str | None = None
    steps_log: list = []
    error: str | None = None
    failed_step: str | None = None


class KBListEntry(BaseModel):
    file_name: str
    title: str
    channel: str | None = None
    duration: str | None = None
    saved_at: str | None = None
    video_url: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest) -> RunResponse:
    if not request.query.strip():
        return RunResponse(success=False, error="Query cannot be empty.", steps_log=[])

    state = run_pipeline(request.query)

    if state.get("error"):
        return RunResponse(
            success=False,
            error=state["error"],
            failed_step=state.get("failed_step"),
            steps_log=state.get("steps_log", []),
        )

    transcript_text = state["transcript"]["text"]
    preview = transcript_text[:300] + ("..." if len(transcript_text) > 300 else "")

    return RunResponse(
        success=True,
        video_meta=state["video_meta"],
        transcript_path=state["kb_entry"]["file_path"],
        transcript_preview=preview,
        transcript_full=transcript_text,
        steps_log=state.get("steps_log", []),
    )


@app.get("/knowledge_base", response_model=list[KBListEntry])
def list_knowledge_base() -> list[KBListEntry]:
    """List saved transcripts, newest first."""
    entries = []
    if not KNOWLEDGE_BASE_DIR.exists():
        return entries

    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        video = record.get("video", {})
        entries.append(KBListEntry(
            file_name=path.name,
            title=video.get("title", path.stem),
            channel=video.get("channel"),
            duration=video.get("duration"),
            saved_at=record.get("saved_at"),
            video_url=video.get("video_url"),
        ))
    return entries


@app.get("/knowledge_base/{file_name}")
def get_knowledge_base_entry(file_name: str) -> dict:
    """Fetch one saved transcript by file name."""
    safe_name = Path(file_name).name  # blocks path traversal like "../../etc"
    path = KNOWLEDGE_BASE_DIR / safe_name
    if not path.is_file() or path.parent != KNOWLEDGE_BASE_DIR:
        return {"error": "not found"}
    return json.loads(path.read_text(encoding="utf-8"))