# Backend container for Render (Docker environment).
# Installs ffmpeg because both yt-dlp (audio extraction) and pydub (chunking)
# shell out to it — Render's native Python runtime doesn't ship it, so Docker
# is the simplest way to guarantee it's on PATH.

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects PORT at runtime and routes traffic to it — don't hardcode 8000 here.
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]