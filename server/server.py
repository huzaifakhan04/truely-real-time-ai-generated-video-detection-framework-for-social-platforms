import os
import tempfile
import uuid
import subprocess
import threading
import time
import cv2
import re
import json
import uvicorn
from pydantic import BaseModel
from typing import Optional
from model import run
from fastapi import (
    FastAPI,
    Request,
    HTTPException
)
from fastapi.responses import (
    JSONResponse,
    FileResponse,
    HTMLResponse
)
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
analysis_results = {}

def cleanup_old_results():
    while True:
        current_time = time.time()
        to_remove = []
        for result_id, result in analysis_results.items():
            if current_time - result["timestamp"] > 3600:
                try:
                    os.unlink(result["output_path"])
                except:
                    pass
                to_remove.append(result_id)
        for result_id in to_remove:
            del analysis_results[result_id]
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_results, daemon=True)
cleanup_thread.start()

@app.get("/view/{result_id}", response_class=HTMLResponse)
async def view_result(result_id: str, request: Request):
    if result_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Result not found or has expired")
    return templates.TemplateResponse(
        "view_result.html", 
        {
            "request": request,
            "fake_score": analysis_results[result_id]["fake_score"],
            "video_url": f"/video/{result_id}"
        }
    )

@app.get("/video/{result_id}")
async def get_video(result_id: str):
    if result_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Video not found or has expired")
    return FileResponse(
        analysis_results[result_id]["output_path"], 
        media_type="video/mp4"
    )

def get_platform_and_video_id(url):
    youtube_patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([^&\?\/]+)'
    ]
    twitter_patterns = [
        r'(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)'
    ]
    facebook_patterns = [
        r'facebook\.com\/(?:watch\/\?v=|watch\?v=|.+?\/videos\/)(\d+)',
        r'fb\.watch\/([^\/]+)',
        r'facebook\.com\/[^\/]+\/videos\/(\d+)'
    ]
    reddit_patterns = [
        r'reddit\.com\/r\/[^\/]+\/comments\/([^\/]+)',
        r'redd\.it\/(\w+)'
    ]
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            return "youtube", match.group(1)
    for pattern in twitter_patterns:
        match = re.search(pattern, url)
        if match:
            return "twitter", match.group(1)
    for pattern in facebook_patterns:
        match = re.search(pattern, url)
        if match:
            return "facebook", match.group(1)
    for pattern in reddit_patterns:
        match = re.search(pattern, url)
        if match:
            return "reddit", match.group(1)
    return None, None

def get_available_formats(url):
    try:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            url
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        video_info = json.loads(result.stdout)
        return video_info.get("formats", [])
    except Exception as e:
        print(f"Error getting formats: {str(e)}")
        return []

def select_best_format(formats, target_height=360):
    video_formats = [f for f in formats if f.get("height") and f.get("vcodec") != "none"]
    if not video_formats:
        return None
    valid_formats = sorted(video_formats, key=lambda x: x.get("height", 0))
    best_format = None
    for fmt in valid_formats:
        if fmt.get("height", 0) <= target_height:
            best_format = fmt
        else:
            break
    if not best_format and valid_formats:
        best_format = valid_formats[0]
    return best_format.get("format_id") if best_format else None

@app.get("/download")
async def download_video(videoUrl: Optional[str] = None, videoId: Optional[str] = None, quality: str = "360p"):
    target_height = 360
    if videoUrl:
        platform, extracted_id = get_platform_and_video_id(videoUrl)
        if not platform or not extracted_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Unsupported URL format"}
            )
        video_id = extracted_id
    elif not videoId:
        return JSONResponse(
            status_code=400,
            content={"error": "No video ID or URL provided"}
        )
    else:
        video_id = videoId
        
    try:
        timestamp = int(time.time())
        video_path = os.path.join(tempfile.gettempdir(), f"ai_detector_video_{video_id}_{timestamp}.mp4")
        print(f"Attempting to download video {video_id} to {video_path}")
        if videoUrl:
            url = videoUrl
        else:
            url = f"https://www.youtube.com/watch?v={video_id}"
        format_option = []
        if platform in ["facebook", "reddit"]:
            print(f"{platform.capitalize()} video detected, analyzing available formats...")
            formats = get_available_formats(url)
            format_id = select_best_format(formats, target_height)
            if format_id:
                format_option = ["-f", format_id]
                print(f"Selected format ID: {format_id}")
            else:
                format_option = ["-f", "best"]
                print("Using default format selection")
        else:
            format_option = ["-f", f"best[height<={target_height}]"]
        cmd = [
            "yt-dlp",
            "--verbose",
            "--force-overwrites",
            "--no-cache-dir",
            "--no-continue",
        ] + format_option + [
            "--merge-output-format", "mp4",
            "-o", video_path,
            url
        ]
        print(f'Running command: {" ".join(cmd)}')
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Download output: {result.stdout}")
        if not os.path.exists(video_path):
            print(f"Error: File {video_path} does not exist")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to download video: File not created"}
            )
        if os.path.getsize(video_path) == 0:
            print(f"Error: File {video_path} is empty (0 bytes)")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to download video: Empty file created"}
            )
        file_size = os.path.getsize(video_path)
        print(f"Downloaded file size: {file_size} bytes")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f'Error: OpenCV couldn\'t open {video_path}')
            os.unlink(video_path)
            return JSONResponse(
                status_code=500,
                content={"error": "Downloaded video is corrupted or in an unsupported format"}
            )
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"Video info: {width}x{height}, {fps} fps, {frame_count} frames")
        cap.release()
        return {"videoPath": video_path}
    except subprocess.CalledProcessError as e:
        print(f"Download command error: {e.stdout} {e.stderr}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download video: {e.stderr}"}
        )
    except Exception as e:
        print(f"Download error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download video: {str(e)}"}
        )

class VideoAnalysisRequest(BaseModel):
    videoPath: str

@app.post("/analyze")
async def analyze_video(data: VideoAnalysisRequest):
    video_path = data.videoPath
    if not video_path or not os.path.exists(video_path):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid video path"}
        )
    try:
        output_path = video_path.replace(".mp4", "_output.mp4")
        fake_score = run(video_path, output_path)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return JSONResponse(
                status_code=500,
                content={"error": "Video analysis failed: No output video generated"}
            )
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "output_path": output_path,
            "fake_score": fake_score,
            "timestamp": time.time()
        }
        def delete_input_video():
            time.sleep(60)
            try:
                os.unlink(video_path)
            except:
                pass
        delete_thread = threading.Thread(target=delete_input_video)
        delete_thread.start()
        return {
            "fakeScore": fake_score,
            "resultId": result_id
        }
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to analyze video: {str(e)}"}
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)