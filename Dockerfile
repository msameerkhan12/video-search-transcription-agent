# Dockerfile for deploying the backend to SnapDeploy.
# SnapDeploy auto-detects the port from this file's EXPOSE line, but for
# FastAPI apps it defaults its own expectation to port 8000 if no base
# config is found — so this container listens on 8000 to match, rather
# than fighting the platform's auto-detection.

FROM python:3.11-slim

# ffmpeg is required by yt-dlp (audio extraction) and pydub (chunking)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ephemeral working directories — wiped on every redeploy/auto-sleep cycle,
# see README "Known limitations" for details.
RUN mkdir -p /app/temp_audio /app/knowledge_base

# Fixed port — matches SnapDeploy's default FastAPI port expectation (8000).
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]