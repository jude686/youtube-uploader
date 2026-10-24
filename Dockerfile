FROM python:3.10-slim

# System FFmpeg (with libass for burned-in subtitles) + fonts for the subtitle styles
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fontconfig fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg \
    HEADLESS=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY src ./src
RUN mkdir -p output credentials assets

# Northflank detects the EXPOSEd port; $PORT overrides it if a host sets one
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.web:app --host 0.0.0.0 --port ${PORT:-8000}"]
