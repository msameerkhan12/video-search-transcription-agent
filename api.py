"""
api.py — FastAPI app that wraps the LangGraph agent pipeline over HTTP.

Run locally with: uvicorn api:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_pipeline
from config import ALLOWED_ORIGINS

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