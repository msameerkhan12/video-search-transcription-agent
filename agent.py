"""
agent.py — orchestrates the four-tool pipeline as a LangGraph state graph.

Why LangGraph over plain LangChain agent executors:
This pipeline is a fixed, linear chain of *dependent* steps (search -> extract
-> transcribe -> save) where each step's output is the next step's required
input, and any failure should stop the pipeline and surface a clear error
rather than let an LLM "decide" to retry or skip a step. LangGraph's explicit
state graph models that directly — one typed state object threaded through
named nodes with deterministic edges — which is easier to log, test, and
reason about than a ReAct-style tool-calling loop, while still being able to
report which step it's on at each point (the "reasoning step-by-step" the
brief asks for). We keep tool-calling *dispatch* logic in each node rather
than delegating tool choice to an LLM, since the tool order is fixed by the
task itself, not something that benefits from being re-decided per query.
"""
import logging
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, END

from tools.video_search_tool import search_video, VideoSearchError
from tools.audio_extraction_tool import extract_audio, cleanup_audio_file, AudioExtractionError
from tools.transcription_tool import transcribe_audio, TranscriptionError
from tools.knowledge_base_writer import save_transcript

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("agent")


class PipelineState(TypedDict, total=False):
    query: str
    video_meta: Optional[dict]
    audio_path: Optional[str]
    transcript: Optional[dict]
    kb_entry: Optional[dict]
    error: Optional[str]
    failed_step: Optional[str]
    steps_log: list


def _log_step(state: PipelineState, tool_name: str, input_summary: str, output_summary: str) -> None:
    entry = {"tool": tool_name, "input": input_summary, "output": output_summary}
    state.setdefault("steps_log", []).append(entry)
    logger.info("%s | input=%s | output=%s", tool_name, input_summary, output_summary)


def search_node(state: PipelineState) -> PipelineState:
    try:
        video_meta = search_video(state["query"])
        _log_step(state, "VideoSearchTool", state["query"], video_meta["title"])
        state["video_meta"] = video_meta
    except VideoSearchError as exc:
        state["error"] = str(exc)
        state["failed_step"] = "search"
        _log_step(state, "VideoSearchTool", state["query"], f"FAILED: {exc}")
    return state


def extract_node(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    try:
        video_url = state["video_meta"]["video_url"]
        audio_path = extract_audio(video_url)
        _log_step(state, "AudioExtractionTool", video_url, audio_path)
        state["audio_path"] = audio_path
    except AudioExtractionError as exc:
        state["error"] = str(exc)
        state["failed_step"] = "extract"
        _log_step(state, "AudioExtractionTool", state["video_meta"]["video_url"], f"FAILED: {exc}")
    return state


def transcribe_node(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    try:
        transcript = transcribe_audio(state["audio_path"])
        preview = transcript["text"][:80] + ("..." if len(transcript["text"]) > 80 else "")
        _log_step(state, "TranscriptionTool", state["audio_path"], preview)
        state["transcript"] = transcript
    except TranscriptionError as exc:
        state["error"] = str(exc)
        state["failed_step"] = "transcribe"
        _log_step(state, "TranscriptionTool", state["audio_path"], f"FAILED: {exc}")
    finally:
        # Clean up the temp audio file regardless of outcome — disk is
        # precious and ephemeral on Hugging Face Spaces' free tier.
        if state.get("audio_path"):
            cleanup_audio_file(state["audio_path"])
    return state


def save_node(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    try:
        kb_entry = save_transcript(state["video_meta"], state["transcript"])
        _log_step(state, "KnowledgeBaseWriter", state["video_meta"]["title"], kb_entry["file_name"])
        state["kb_entry"] = kb_entry
    except Exception as exc:
        state["error"] = f"Failed to save transcript: {exc}"
        state["failed_step"] = "save"
        _log_step(state, "KnowledgeBaseWriter", state["video_meta"]["title"], f"FAILED: {exc}")
    return state


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("search", search_node)
    graph.add_node("extract", extract_node)
    graph.add_node("transcribe", transcribe_node)
    graph.add_node("save", save_node)

    graph.set_entry_point("search")
    graph.add_edge("search", "extract")
    graph.add_edge("extract", "transcribe")
    graph.add_edge("transcribe", "save")
    graph.add_edge("save", END)

    return graph.compile()


_compiled_graph = build_graph()


def run_pipeline(query: str) -> PipelineState:
    """Run the full search -> extract -> transcribe -> save pipeline for a query."""
    initial_state: PipelineState = {"query": query, "steps_log": []}
    final_state = _compiled_graph.invoke(initial_state)
    return final_state
