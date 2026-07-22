# Dockerfile for deploying the backend to Zeabur.
# Zeabur auto-detects this Dockerfile from the repo and builds/deploys it
# directly. It sets the PORT env var at runtime — the container must bind
# to it rather than a hardcoded port.

FROM python:3.11-slim

# ffmpeg is required by yt-dlp (audio extraction) and pydub (chunking)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ephemeral working directories — wiped on every restart/redeploy, see README
# "Known limitations" for details.
RUN mkdir -p /app/temp_audio /app/knowledge_base

# Default to 8080 for local `docker run` testing; Zeabur overrides PORT at runtime.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080}"]