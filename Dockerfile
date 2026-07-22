# Dockerfile for deploying the backend to Render (Environment: Docker).
# Render injects the PORT env var at runtime and routes traffic to it,
# so the container must bind to $PORT rather than a hardcoded port.

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

# Render sets PORT dynamically; default to 10000 for local `docker run` testing.
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}"]