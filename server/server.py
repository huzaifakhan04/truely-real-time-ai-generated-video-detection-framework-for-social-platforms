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
import sys
from pydantic import BaseModel
from typing import (
    Optional,
    Dict,
    Any
)
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Request,
    HTTPException,
    BackgroundTasks
)
from fastapi.responses import (
    JSONResponse,
    FileResponse,
    HTMLResponse
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from model import run

load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

current_directory = os.path.dirname(os.path.abspath(__file__))
if current_directory not in sys.path:
    sys.path.append(current_directory)
router = None
extract_audio = None
transcribe_audio = None
perform_search = None
judge_content = None
try:
    from web.routes import router
    from web.utils.audio import extract_audio
    from web.utils.transcribe import transcribe_audio
    from web.utils.search import perform_search
    from web.utils.judge import judge_content
    has_news_features = True
except ImportError as e:
    has_news_features = False
    print(f"News verification features unavailable: {e}")
app = FastAPI()
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    raise FileNotFoundError(f"Static directory not found: {static_dir}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if router and has_news_features:
    try:
        app.include_router(router, prefix="/news", tags=["news"])
    except Exception as e:
        print(f"Failed to include news router: {e}")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
else:
    raise FileNotFoundError(f"Templates directory not found: {templates_dir}")
analysis_results: Dict[str, Dict[str, Any]] = {}

def cleanup_old_results():
    while True:
        current_time = time.time()
        to_remove = []
        for result_id, result in analysis_results.items():
            if current_time - result.get("timestamp", 0) > 3600:
                try:
                    output_path = result.get("output_path")
                    if output_path and os.path.exists(output_path):
                        os.unlink(output_path)
                    audio_path = result.get("audio_path")
                    if audio_path and os.path.exists(audio_path):
                        os.unlink(audio_path)
                except Exception as e:
                    print(f"Failed to cleanup files for result {result_id}: {e}")
                to_remove.append(result_id)
        for result_id in to_remove:
            del analysis_results[result_id]
            if to_remove:
                print(f"Cleaned up result: {result_id}")
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_results, daemon=True)
cleanup_thread.start()

@app.get("/view/{result_id}", response_class=HTMLResponse)
async def view_result(result_id: str, request: Request):
    if result_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Result not found or has expired")
    template_data = {
        "request": request,
        "fake_score": analysis_results[result_id]["fake_score"],
        "video_url": f"/video/{result_id}"
    }
    if "news_score" in analysis_results[result_id]:
        template_data["news_score"] = analysis_results[result_id]["news_score"]
        template_data["news_summary"] = analysis_results[result_id]["news_summary"]
        template_data["news_evidence"] = analysis_results[result_id]["news_evidence"]
    return templates.TemplateResponse("view_result.html", template_data)

@app.get("/video/{result_id}")
async def get_video(result_id: str):
    if result_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Video not found or has expired")
    output_path = analysis_results[result_id]["output_path"]
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(output_path, media_type="video/mp4")

@app.get("/audio/{result_id}")
async def get_audio(result_id: str):
    if result_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Audio not found or has expired")
    audio_path = analysis_results[result_id].get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    ext = audio_path.split(".")[-1].lower()
    media_type = f"audio/{ext}"
    if ext == "m4a":
        media_type = "audio/mp4"
    return FileResponse(audio_path, media_type=media_type)

def get_platform_and_video_id(url):
    youtube_patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([^&\?\/]+)"
    ]
    twitter_patterns = [
        r"(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)"
    ]
    facebook_patterns = [
        r"facebook\.com\/(?:watch\/\?v=|watch\?v=|.+?\/videos\/)(\d+)",
        r"fb\.watch\/([^\/]+)",
        r"facebook\.com\/[^\/]+\/videos\/(\d+)"
    ]
    reddit_patterns = [
        r"reddit\.com\/r\/[^\/]+\/comments\/([^\/]+)",
        r"redd\.it\/(\w+)"
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

@app.get("/download-video")
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

@app.get("/download-audio")
async def download_audio(videoUrl: Optional[str] = None, videoId: Optional[str] = None, format: str = "mp3"):
    if videoUrl:
        platform, extracted_id = get_platform_and_video_id(videoUrl)
        if not platform or not extracted_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Unsupported URL format"}
            )
        audio_id = extracted_id
    elif not videoId:
        return JSONResponse(
            status_code=400,
            content={"error": "No video ID or URL provided"}
        )
    else:
        audio_id = videoId
    try:
        timestamp = int(time.time())
        audio_path = os.path.join(tempfile.gettempdir(), f"ai_detector_audio_{audio_id}_{timestamp}.{format}")
        print(f"Attempting to download audio {audio_id} to {audio_path}")
        if videoUrl:
            url = videoUrl
        else:
            url = f"https://www.youtube.com/watch?v={audio_id}"
        cmd = [
            "yt-dlp",
            "--verbose",
            "--force-overwrites",
            "--no-cache-dir",
            "--no-continue",
            "-x",
            "--audio-format", format,
            "--audio-quality", "0",
            "-o", audio_path,
            url
        ]
        print(f'Running command: {" ".join(cmd)}')
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Download output: {result.stdout}")
        if not os.path.exists(audio_path):
            print(f"Error: File {audio_path} does not exist")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to download audio: File not created"}
            )
        if os.path.getsize(audio_path) == 0:
            print(f"Error: File {audio_path} is empty (0 bytes)")
            os.unlink(audio_path)
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to download audio: Empty file created"}
            )
        file_size = os.path.getsize(audio_path)
        print(f"Downloaded audio file size: {file_size} bytes")
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "audio_path": audio_path,
            "timestamp": time.time()
        }
        return {
            "audioPath": audio_path,
            "resultId": result_id
        }
    except subprocess.CalledProcessError as e:
        print(f"Download command error: {e.stdout} {e.stderr}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download audio: {e.stderr}"}
        )
    except Exception as e:
        print(f"Download error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download audio: {str(e)}"}
        )
    
@app.get("/download-combined")
async def download_combined(videoUrl: Optional[str] = None, videoId: Optional[str] = None, audioFormat: str = "mp3", videoQuality: str = "360p"):
    video_response = await download_video(videoUrl=videoUrl, videoId=videoId, quality=videoQuality)
    if "error" in video_response:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download video: {video_response['error']}"}
        )
    video_path = video_response["videoPath"]
    audio_path = video_path.replace(".mp4", f".{audioFormat}")
    audio_extracted = False
    try:
        print(f"Extracting audio from {video_path} to {audio_path}")
        if has_news_features and extract_audio:
            try:
                audio_extracted = extract_audio(video_path, audio_path)
                if audio_extracted:
                    print(f"Successfully extracted audio to {audio_path}")
                else:
                    print("Internal audio extraction failed, will try alternative method")
            except Exception as e:
                print(f"FFmpeg error during audio extraction: {str(e)}")
        if not audio_extracted or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            print(f"Direct audio extraction failed or not available, downloading audio separately")
            if videoUrl:
                url = videoUrl
            else:
                url = f"https://www.youtube.com/watch?v={videoId}"
            if os.path.exists(audio_path):
                audio_path = video_path.replace(".mp4", f"_download.{audioFormat}")
            cmd = [
                "yt-dlp",
                "--verbose",
                "--force-overwrites",
                "--no-cache-dir",
                "--no-continue",
                "-x",
                "--audio-format", audioFormat,
                "--audio-quality", "0",
                "-o", audio_path,
                url
            ]
            print(f'Running command: {" ".join(cmd)}')
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Audio download output: {result.stdout}")
            audio_extracted = True
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            print(f"Error: Audio file {audio_path} does not exist or is empty")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to download/extract audio after multiple attempts"}
            )
        video_id = str(uuid.uuid4())
        audio_id = str(uuid.uuid4())
        analysis_results[audio_id] = {
            "audio_path": audio_path,
            "timestamp": time.time()
        }
        analysis_results[video_id] = {
            "output_path": video_path,
            "timestamp": time.time()
        }
        return {
            "videoPath": video_path,
            "audioPath": audio_path,
            "videoId": video_id,
            "audioId": audio_id
        }
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if hasattr(e, "stderr") else str(e)
        print(f"Audio download command error: {error_message}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download audio: {error_message}"}
        )
    except Exception as e:
        print(f"Combined download error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to download combined content: {str(e)}"}
        )

class VideoAnalysisRequest(BaseModel):
    videoPath: str

@app.post("/analyze-video")
async def analyze_video(data: VideoAnalysisRequest, background_tasks: BackgroundTasks):
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
            try:
                if os.path.exists(video_path):
                    os.unlink(video_path)
            except Exception as e:
                print(f"Failed to delete input video: {str(e)}")
        background_tasks.add_task(delete_input_video)
        return {
            "fakeScore": fake_score,
            "resultId": result_id
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to analyze video: {str(e)}"}
        )

class AudioAnalysisRequest(BaseModel):
    audioPath: str

@app.post("/analyze-audio")
async def analyze_audio(data: AudioAnalysisRequest, background_tasks: BackgroundTasks):
    audio_path = data.audioPath
    if not audio_path or not os.path.exists(audio_path):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid audio path"}
        )
    try:
        news_score = 0
        news_summary = "Could not analyze audio content"
        news_evidence = []
        news_result = None
        if has_news_features and transcribe_audio and perform_search and judge_content:
            try:
                print(f"Transcribing audio: {audio_path}")
                transcription = transcribe_audio(audio_path)
                if transcription:
                    print("Generating search query from transcription")
                    from web.utils.judge import generate_search_query
                    search_query = generate_search_query(transcription, GEMINI_API_KEY)
                    print(f"Searching for relevant information with query: {search_query}")
                    search_results = perform_search(search_query, TAVILY_API_KEY)
                    print("Judging content authenticity")
                    news_result = judge_content(transcription, search_results, GEMINI_API_KEY)
                    print(f"News result: {json.dumps(news_result, indent=2)}")
                    if "verdict" in news_result:
                        verdict_scores = {
                            "authentic": 100,
                            "misleading": 50, 
                            "fake": 0,
                            "uncertain": 25
                        }
                        verdict = news_result.get("verdict", "uncertain")
                        news_score = news_result.get("confidence", verdict_scores.get(verdict, 0))
                        news_summary = news_result.get("reasoning", "No reasoning provided")
                        news_evidence = news_result.get("sources", [])
                    else:
                        news_score = news_result.get("score", 0)
                        news_summary = news_result.get("summary", "No summary provided")
                        news_evidence = news_result.get("evidence", [])
            except Exception as e:
                print(f"Audio processing error: {str(e)}")
                news_summary = f"Error analyzing audio: {str(e)}"
        else:
            print("Audio processing skipped - required components not available")
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "audio_path": audio_path,
            "news_score": news_score,
            "news_summary": news_summary,
            "news_evidence": news_evidence,
            "timestamp": time.time()
        }
        response = {
            "newsScore": news_score,
            "newsSummary": news_summary,
            "resultId": result_id
        }
        if "verdict" in news_result:
            response["verdict"] = news_result.get("verdict", "uncertain")
            response["confidence"] = news_result.get("confidence", 0)
        if news_evidence:
            response["evidence"] = [
                {
                    "title": source.get("title", ""),
                    "url": source.get("url", "")
                } for source in news_evidence[:3]
            ]
        return response
    except Exception as e:
        print(f"Audio analysis error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to analyze audio: {str(e)}"}
        )
    
class CombinedAnalysisRequest(BaseModel):
    videoPath: str
    audioPath: str

@app.post("/analyze-combined")
async def analyze_combined(data: CombinedAnalysisRequest, background_tasks: BackgroundTasks):
    video_path = data.videoPath
    if not video_path or not os.path.exists(video_path):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid video path"}
        )
    audio_path = data.audioPath
    if audio_path and not os.path.exists(audio_path):
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid audio path"}
        )
    try:
        output_path = video_path.replace(".mp4", "_output.mp4")
        fake_score = run(video_path, output_path)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return JSONResponse(
                status_code=500,
                content={"error": "Video analysis failed: No output video generated"}
            )
        news_score = 0
        news_summary = "Could not analyze audio content"
        news_evidence = []
        news_result = None
        if has_news_features and transcribe_audio and perform_search and judge_content:
            try:
                if not audio_path:
                    audio_path = video_path.replace(".mp4", ".wav")
                    audio_extracted = extract_audio(video_path, audio_path) if extract_audio else False
                else:
                    audio_extracted = True
                if audio_extracted or os.path.exists(audio_path):
                    print(f"Transcribing audio: {audio_path}")
                    transcription = transcribe_audio(audio_path)
                    if transcription:
                        print("Generating search query from transcription")
                        from web.utils.judge import generate_search_query
                        search_query = generate_search_query(transcription, GEMINI_API_KEY)
                        print(f"Searching for relevant information with query: {search_query}")
                        search_results = perform_search(search_query, TAVILY_API_KEY)
                        print("Judging content authenticity")
                        news_result = judge_content(transcription, search_results, GEMINI_API_KEY)
                        print(f"News result: {json.dumps(news_result, indent=2)}")
                        if "verdict" in news_result:
                            verdict_scores = {
                                "authentic": 100,
                                "misleading": 50, 
                                "fake": 0,
                                "uncertain": 25
                            }
                            verdict = news_result.get("verdict", "uncertain")
                            news_score = news_result.get("confidence", verdict_scores.get(verdict, 0))
                            news_summary = news_result.get("reasoning", "No reasoning provided")
                            news_evidence = news_result.get("sources", [])
                        else:
                            news_score = news_result.get("score", 0)
                            news_summary = news_result.get("summary", "No summary provided")
                            news_evidence = news_result.get("evidence", [])
            except Exception as e:
                print(f"Audio processing error: {str(e)}")
                news_summary = f"Error analyzing audio: {str(e)}"
        else:
            print("Audio processing skipped - required components not available")
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "output_path": output_path,
            "audio_path": audio_path if (("audio_extracted" in locals() and audio_extracted) or data.audioPath) else None,
            "fake_score": fake_score,
            "news_score": news_score,
            "news_summary": news_summary,
            "news_evidence": news_evidence,
            "timestamp": time.time()
        }
        def delete_input_video():
            try:
                if os.path.exists(video_path):
                    os.unlink(video_path)
            except Exception as e:
                print(f"Failed to delete input video: {str(e)}")
            
        background_tasks.add_task(delete_input_video)
        response = {
            "fakeScore": fake_score,
            "newsScore": news_score,
            "newsSummary": news_summary,
            "resultId": result_id
        }
        if news_result and "verdict" in news_result:
            response["verdict"] = news_result.get("verdict", "uncertain")
            response["confidence"] = news_result.get("confidence", 0)
        
        if news_evidence:
            response["evidence"] = [
                {
                    "title": source.get("title", ""),
                    "url": source.get("url", "")
                } for source in news_evidence[:3]
            ]
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to analyze content: {str(e)}"}
        )

@app.get("/")
async def root():
    """Root endpoint returning API information"""
    return {
        "name": "AI-Generated Video Detection Tool API",
        "version": "1.0.0",
        "endpoints": [
            "/download-video - Download video from URL",
            "/download-audio - Download audio from URL",
            "/analyze - Analyze video for AI manipulation",
            "/analyze-audio - Analyze audio content for authenticity",
            "/analyze-combined - Analyze video and audio content",
            "/view/{result_id} - View analysis results",
            "/video/{result_id} - Stream processed video",
            "/audio/{result_id} - Stream processed audio",
            "/news/* - News verification endpoints" if has_news_features else "News verification not available"
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)