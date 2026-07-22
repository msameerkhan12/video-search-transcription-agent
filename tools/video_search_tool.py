"""
Tool 1: VideoSearchTool

Given a natural-language query, finds the single best-matching YouTube video
using SerpApi's YouTube search engine (serpapi.com — free tier: 250 searches/month).
"""
from typing import TypedDict
from serpapi import GoogleSearch
from config import SERPAPI_KEY


class VideoResult(TypedDict):
    video_url: str
    title: str
    channel: str
    duration: str
    duration_seconds: int


class VideoSearchError(Exception):
    """Raised when no usable video is found, so the agent can report it cleanly."""


def _duration_to_seconds(duration_str: str) -> int:
    """Convert 'HH:MM:SS' or 'MM:SS' into total seconds. Returns 0 if unparsable."""
    if not duration_str:
        return 0
    parts = duration_str.strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def search_video(query: str) -> VideoResult:
    """
    Search YouTube via SerpApi and return metadata for the top result.

    Raises:
        VideoSearchError: if the API key is missing, the request fails, or
            no video results are returned.
    """
    if not SERPAPI_KEY:
        raise VideoSearchError("SERPAPI_KEY is not set. Add it to your .env file.")

    params = {
        "engine": "youtube",
        "search_query": query,
        "api_key": SERPAPI_KEY,
    }

    try:
        results = GoogleSearch(params).get_dict()
    except Exception as exc:
        raise VideoSearchError(f"SerpApi request failed: {exc}") from exc

    if "error" in results:
        raise VideoSearchError(f"SerpApi returned an error: {results['error']}")

    video_results = results.get("video_results", [])
    if not video_results:
        raise VideoSearchError(f"No YouTube results found for query: '{query}'")

    top = video_results[0]
    duration_str = top.get("length", "")

    return VideoResult(
        video_url=top.get("link", ""),
        title=top.get("title", "Untitled"),
        channel=top.get("channel", {}).get("name", "Unknown channel"),
        duration=duration_str,
        duration_seconds=_duration_to_seconds(duration_str),
    )
