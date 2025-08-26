FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by OpenCV, ffmpeg and common audio/video libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    wget \
    git \
    ca-certificates \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency list first for better caching
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip
RUN pip install -r /app/requirements.txt
# yt-dlp used by the app for downloads
RUN pip install yt-dlp

# Copy project
COPY . /app

EXPOSE 5001

# Default command: run uvicorn on port 5001
CMD ["uvicorn", "server.server:app", "--host", "0.0.0.0", "--port", "5001"]
