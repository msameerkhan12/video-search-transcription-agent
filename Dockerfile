# Dockerfile for deploying the backend to Northflank.
# Northflank does NOT inject a PORT env var automatically — it detects the
# port from this file's EXPOSE line (or you set one manually in the
# service's Networking tab). So, unlike Render/Zeabur, this container
# listens on a fixed port rather than reading $PORT.

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

# Fixed port — make sure this matches the port configured in Northflank's
# Networking tab for this service.
EXPOSE 8080
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]