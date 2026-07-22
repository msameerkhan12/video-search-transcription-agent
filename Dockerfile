# Dockerfile for deploying the backend to SnapDeploy.
# SnapDeploy auto-detects the port from this file's EXPOSE line, similar
# to Northflank — it does not inject a PORT env var automatically, so
# this container listens on a fixed port rather than reading $PORT.

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

# Fixed port — make sure this matches the port SnapDeploy detects/configures
# for this service.
EXPOSE 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]