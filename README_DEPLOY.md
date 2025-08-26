Deployment notes

This repository contains a FastAPI app located in the `server/` folder. The app uses OpenCV, PyTorch and related packages and may require a machine with enough resources (CPU/CUDA if using GPU).

Quick local run (Python environment):

1. Create and activate a virtualenv (macOS/Linux):

   python3 -m venv .venv
   source .venv/bin/activate

2. Install requirements:

   pip install -r requirements.txt

3. Copy `.env.example` to `.env` and fill keys if needed.

4. Start the server:

   uvicorn server.server:app --reload --host 0.0.0.0 --port 8000

Run with Docker (recommended for reproducible env):

1. Build and run with docker-compose:

   docker-compose up --build

This exposes the app on http://localhost:8000

Notes:
- The Docker image installs system dependencies required by OpenCV and ffmpeg and then installs Python packages in `requirements.txt`.
- The project uses `yt-dlp` at runtime (installed in Dockerfile). Ensure your runtime environment has network access and appropriate legal rights to download content.
- For production hosting (Heroku/GCP/AWS), use the `Procfile` or adapt the Dockerfile to your platform.
