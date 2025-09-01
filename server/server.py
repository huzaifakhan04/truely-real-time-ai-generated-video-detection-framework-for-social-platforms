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
import logging
from pydantic import BaseModel
from typing import (
    Dict,
    Any,
    Optional
)
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Request,
    HTTPException,
    BackgroundTasks,
    status
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

transcribe_audio = None
perform_search = None
judge_content = None
try:
    from web.utils.transcribe import transcribe_audio
    from web.utils.search import perform_search
    from web.utils.judge import judge_content
    has_news_features = True
except ImportError as e:
    has_news_features = False
    raise ImportError(f"Failed to import news features: {e}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.critical(f"Static directory not found: {static_dir}")
    raise FileNotFoundError(f"Static directory not found: {static_dir}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
else:
    logger.critical(f"Templates directory not found: {templates_dir}")
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
                    to_remove.append(result_id)
                except Exception as e:
                    logger.error(f"Failed to delete files for result {result_id}: {str(e)}")
        for result_id in to_remove:
            try:
                del analysis_results[result_id]
                logger.info(f"Cleaned up result {result_id} and associated files")
            except KeyError:
                logger.warning(f"Failed to remove result {result_id} from analysis_results - key not found")
        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_results, daemon=True)
cleanup_thread.start()

@app.get("/view/{result_id}", response_class=HTMLResponse)
async def view_result(result_id: str, request: Request):
    if not result_id or result_id not in analysis_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found or has expired")
    try:
        result = analysis_results[result_id]
        template_data = {
            "fake_score": result.get("fake_score", "N/A"),
            "video_url": f"/video/{result_id}",
            "verdict": result.get("verdict", "Uncertain"),
            "news_score": result.get("news_score", "N/A"),
            "news_summary": result.get("news_summary", "No summary available")
        }
        if "verdict" in template_data and isinstance(template_data["verdict"], str):
            template_data["verdict"] = template_data["verdict"].capitalize()
        news_evidence = result.get("news_evidence", [])
        if news_evidence:
            template_data["news_evidence"] = [
                {
                    "title": evidence.get("title", "Untitled"),
                    "url": evidence.get("url", "#")
                } for evidence in news_evidence
            ]
        return templates.TemplateResponse("view_result.html", {"request": request, **template_data})
    except KeyError as e:
        logger.error(f"Missing key in analysis_results for result_id {result_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Server error while processing result {result_id}")

@app.get("/video/{result_id}")
async def get_video(result_id: str):
    if not result_id or result_id not in analysis_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found or has expired")
    try:
        output_path = analysis_results[result_id]["output_path"]
        if not output_path or not os.path.exists(output_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found")
        return FileResponse(output_path, media_type="video/mp4")
    except KeyError:
        logger.error(f"Missing 'output_path' key in analysis_results for result_id {result_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                            detail="Server error while retrieving video file")

@app.get("/audio/{result_id}")
async def get_audio(result_id: str):
    if not result_id or result_id not in analysis_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found or has expired")
    try:
        audio_path = analysis_results[result_id].get("audio_path")
        if not audio_path or not os.path.exists(audio_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")
        ext = audio_path.split(".")[-1].lower()
        media_type = f"audio/{ext}"
        if ext == "m4a":
            media_type = "audio/mp4"
        return FileResponse(audio_path, media_type=media_type)
    except Exception as e:
        logger.error(f"Error retrieving audio for result_id {result_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error while retrieving audio file")

def get_platform_and_video_id(url: str):
    url_patterns = {
        "youtube": [r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([^&\?\/]+)"],
        "twitter": [r"(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)"],
        "facebook": [r"facebook\.com\/(?:watch\/\?v=|watch\?v=|.+?\/videos\/)(\d+)",r"fb\.watch\/([^\/]+)",r"facebook\.com\/[^\/]+\/videos\/(\d+)"],
        "reddit": [r"reddit\.com\/r\/[^\/]+\/comments\/([^\/]+)",r"redd\.it\/(\w+)"]
    }
    for platforms, patterns in url_patterns.items():
        for p in patterns:
            match = re.search(p, url)
            if match:
                return platforms, match.group(1)
    return None, None

def get_available_formats(url: str):
    if not url:
        logger.error("Empty URL provided to get_available_formats")
        return []
    try:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            url
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        if not result.stdout:
            logger.error(f"Empty response from yt-dlp for URL: {url}")
            return []
        try:
            video_info = json.loads(result.stdout)
            return video_info.get("formats", [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse yt-dlp JSON response for URL {url}: {str(e)}")
            return []
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp command failed for URL {url}: {e.stderr}")
        return []
    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp command timed out for URL {url}")
        return []
    except Exception as e:
        logger.error(f"Failed to get available formats for URL {url}: {str(e)}")
        return []

def select_best_format(formats: list, target_height: int = 360):
    if not formats:
        logger.warning("Empty formats list provided to select_best_format")
        return None
    try:
        video_formats = [f for f in formats if f.get("height") and f.get("vcodec") != "none"]
        if not video_formats:
            logger.warning("No valid video formats found")
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
    except Exception as e:
        logger.error(f"Error selecting best format: {str(e)}")
        return None

@app.get("/download-video")
async def download_video(video_url: Optional[str] = None, quality: str = "360p"):
    if not video_url:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No video URL provided"}
        )
    platform, extracted_id = get_platform_and_video_id(video_url)
    if not platform or not extracted_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Unsupported URL format"}
        )
    video_id = extracted_id
    target_height = 360
    if quality and quality.lower().endswith("p"):
        try:
            requested_height = int(quality[:-1])
            if requested_height > 0:
                target_height = requested_height
        except ValueError:
            logger.warning(f"Invalid quality parameter: {quality}, using default: 360p")
    
    try:
        timestamp = int(time.time())
        video_path = os.path.join(tempfile.gettempdir(), f"ai_detector_video_{video_id}_{timestamp}.mp4")
        url = video_url
        format_option = []
        if platform in ["facebook", "reddit"]:
            formats = get_available_formats(url)
            format_id = select_best_format(formats, target_height)
            if format_id:
                format_option = ["-f", format_id]
            else:
                format_option = ["-f", "best"]
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
        logger.info(f"Downloading video from {url} with options: {' '.join(format_option)}")
        try:
            _ = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            logger.error(f"Video download timed out for URL: {url}")
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"error": "Video download timed out"}
            )
        if not os.path.exists(video_path):
            logger.error(f"Video file not created after download: {video_path}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to download video: File not created"}
            )
        if os.path.getsize(video_path) == 0:
            logger.error(f"Downloaded video file is empty: {video_path}")
            try:
                os.unlink(video_path)
            except OSError:
                pass
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to download video: Empty file created"}
            )
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Downloaded video is corrupted or in unsupported format: {video_path}")
            try:
                os.unlink(video_path)
            except OSError:
                pass
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Downloaded video is corrupted or in an unsupported format"}
            )
        cap.release()
        logger.info(f"Successfully downloaded video to {video_path}")
        return {"videoPath": video_path}
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if hasattr(e, 'stderr') else str(e)
        logger.error(f"yt-dlp command failed: {error_message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to download video: {error_message}"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in download_video: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to download video: {str(e)}"}
        )

@app.get("/download-audio")
async def download_audio(video_url: Optional[str] = None, format: str = "mp3"):
    if not video_url:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No video URL provided"}
        )
    allowed_formats = ["mp3", "m4a", "wav", "aac", "flac", "opus"]
    if format not in allowed_formats:
        logger.warning(f"Unsupported audio format requested: {format}, using mp3 instead")
        format = "mp3"
    platform, extracted_id = get_platform_and_video_id(video_url)
    if not platform or not extracted_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Unsupported URL format"}
        )
    audio_id = extracted_id
    try:
        timestamp = int(time.time())
        audio_path = os.path.join(tempfile.gettempdir(), f"ai_detector_audio_{audio_id}_{timestamp}.{format}")
        url = video_url
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
        logger.info(f"Downloading audio from {url} in format: {format}")
        try:
            _ = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            logger.error(f"Audio download timed out for URL: {url}")
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"error": "Audio download timed out"}
            )
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not created after download: {audio_path}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to download audio: File not created"}
            )
        if os.path.getsize(audio_path) == 0:
            logger.error(f"Downloaded audio file is empty: {audio_path}")
            try:
                os.unlink(audio_path)
            except OSError:
                pass
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to download audio: Empty file created"}
            )
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "audio_path": audio_path,
            "timestamp": time.time()
        }
        logger.info(f"Successfully downloaded audio to {audio_path} with result_id {result_id}")
        return {
            "audioPath": audio_path,
            "resultId": result_id
        }
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if hasattr(e, 'stderr') else str(e)
        logger.error(f"yt-dlp command failed: {error_message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to download audio: {error_message}"}
        )
    except Exception as e:
        logger.error(f"Unexpected error in download_audio: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to download audio: {str(e)}"}
        )
    
@app.get("/download-combined")
async def download_combined(video_url: Optional[str] = None, audio_format: str = "mp3", quality: str = "360p"):
    if not video_url:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No video URL provided"}
        )
    allowed_formats = ["mp3", "m4a", "wav", "aac", "flac", "opus"]
    if audio_format not in allowed_formats:
        logger.warning(f"Unsupported audio format requested: {audio_format}, using mp3 instead")
        audio_format = "mp3"
    platform, extracted_id = get_platform_and_video_id(video_url)
    if not platform or not extracted_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Unsupported URL format"}
        )
    timestamp = int(time.time())
    video_id = str(uuid.uuid4())[:8]
    audio_id = str(uuid.uuid4())[:8]
    video_path = os.path.join(tempfile.gettempdir(), f"ai_detector_video_{extracted_id}_{video_id}_{timestamp}.mp4")
    audio_path = os.path.join(tempfile.gettempdir(), f"ai_detector_audio_{extracted_id}_{audio_id}_{timestamp}.{audio_format}")
    try:
        logger.info(f"Downloading video from URL: {video_url} to {video_path}")
        
        target_height = 360
        if quality and quality.lower().endswith("p"):
            try:
                requested_height = int(quality[:-1])
                if requested_height > 0:
                    target_height = requested_height
            except ValueError:
                logger.warning(f"Invalid quality parameter: {quality}, using default: 360p")
        format_option = []
        if platform in ["facebook", "reddit"]:
            formats = get_available_formats(video_url)
            format_id = select_best_format(formats, target_height)
            if format_id:
                format_option = ["-f", format_id]
            else:
                format_option = ["-f", "best"]
        else:
            format_option = ["-f", f"best[height<={target_height}]"]
        video_cmd = [
            "yt-dlp",
            "--verbose",
            "--force-overwrites",
            "--no-cache-dir",
            "--no-continue",
        ] + format_option + [
            "--merge-output-format", "mp4",
            "-o", video_path,
            video_url
        ]
        try:
            video_process = subprocess.run(video_cmd, check=True, capture_output=True, text=True, timeout=180)
            logger.info(f"Video download process completed with: {video_process.stdout[-200:] if video_process.stdout else 'No output'}")
        except subprocess.TimeoutExpired:
            logger.error(f"Video download timed out for URL: {video_url}")
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"error": "Video download timed out"}
            )
        except subprocess.CalledProcessError as e:
            error_message = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            logger.error(f"yt-dlp command for video failed: {error_message}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": f"Failed to download video: {error_message}"}
            )
        if not os.path.exists(video_path):
            logger.error(f"Video path does not exist after download attempt: {video_path}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Downloaded video file does not exist"}
            )
        if os.path.getsize(video_path) == 0:
            logger.error(f"Downloaded video file is empty: {video_path}")
            try:
                os.unlink(video_path)
            except OSError:
                pass
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Downloaded video file is empty"}
            )
        logger.info(f"Downloading audio from URL: {video_url} to {audio_path}")
        audio_cmd = [
            "yt-dlp",
            "--verbose",
            "--force-overwrites",
            "--no-cache-dir",
            "--no-continue",
            "-x",
            "--audio-format", audio_format,
            "--audio-quality", "0",
            "-o", audio_path,
            video_url
        ]
        try:
            audio_process = subprocess.run(audio_cmd, check=True, capture_output=True, text=True, timeout=120)
            logger.info(f"Audio download process completed with: {audio_process.stdout[-200:] if audio_process.stdout else 'No output'}")
        except subprocess.TimeoutExpired:
            logger.error(f"Audio download timed out for URL: {video_url}")
            logger.warning("Proceeding with just video since audio download timed out")
            audio_path = None
        except subprocess.CalledProcessError as e:
            logger.error(f"Audio download failed: {e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)}")
            logger.warning("Proceeding with just video since audio download failed")
            audio_path = None
        if audio_path:
            if not os.path.exists(audio_path):
                logger.warning(f"Audio file not found after download attempt: {audio_path}")
                audio_path = None
            elif os.path.getsize(audio_path) == 0:
                logger.warning(f"Downloaded audio file is empty: {audio_path}")
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass
                audio_path = None
        video_result_id = str(uuid.uuid4())
        analysis_results[video_result_id] = {
            "output_path": video_path,
            "timestamp": time.time()
        }
        audio_result_id = None
        if audio_path and os.path.exists(audio_path):
            audio_result_id = str(uuid.uuid4())
            analysis_results[audio_result_id] = {
                "audio_path": audio_path,
                "timestamp": time.time()
            }
        result = {
            "videoPath": video_path,
            "videoId": video_result_id,
        }
        if audio_path and os.path.exists(audio_path):
            result["audioPath"] = audio_path
            result["audioId"] = audio_result_id
            logger.info(f"Successfully downloaded both video and audio. Video ID: {video_result_id}, Audio ID: {audio_result_id}")
        else:
            logger.info(f"Successfully downloaded video only. Video ID: {video_result_id}")
            result["audioPath"] = None
            result["audioId"] = None
        return result
    except Exception as e:
        logger.error(f"Unexpected error during combined download: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to download combined content: {str(e)}"}
        )

class VideoAnalysisRequest(BaseModel):
    videoPath: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "videoPath": "/tmp/video_123456.mp4"
            }
        }

@app.post("/analyze-video")
async def analyze_video(data: VideoAnalysisRequest, background_tasks: BackgroundTasks):
    video_path = data.videoPath
    if not video_path:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing video path"}
        )
    if not os.path.exists(video_path):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Video file not found at specified path"}
        )
    if not os.path.isfile(video_path):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Provided path is not a file"}
        )
    if os.path.getsize(video_path) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Video file is empty"}
        )
    try:
        output_path = video_path.replace(".mp4", "_output.mp4")
        
        logger.info(f"Starting video analysis for {video_path}")
        fake_score = run(video_path, output_path)
        if not os.path.exists(output_path):
            logger.error(f"Analysis completed but no output video was generated at {output_path}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Video analysis failed: No output video generated"}
            )
        if os.path.getsize(output_path) == 0:
            logger.error(f"Analysis completed but output video is empty: {output_path}")
            try:
                os.unlink(output_path)
            except OSError:
                pass
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Video analysis failed: Empty output video generated"}
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
                    logger.info(f"Deleted input video: {video_path}")
            except Exception as e:
                logger.error(f"Failed to delete input video {video_path}: {str(e)}")
        background_tasks.add_task(delete_input_video)
        logger.info(f"Video analysis completed with fake_score: {fake_score}, result_id: {result_id}")
        return {
            "fakeScore": fake_score,
            "resultId": result_id
        }
    except Exception as e:
        logger.error(f"Error during video analysis: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to analyze video: {str(e)}"}
        )

class AudioAnalysisRequest(BaseModel):
    audioPath: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "audioPath": "/tmp/audio_123456.mp3"
            }
        }

@app.post("/analyze-audio")
async def analyze_audio(data: AudioAnalysisRequest, background_tasks: BackgroundTasks):
    audio_path = data.audioPath
    if not audio_path:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing audio path"}
        )
    if not os.path.exists(audio_path):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Audio file not found at specified path"}
        )
    if not os.path.isfile(audio_path):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Provided path is not a file"}
        )
    if os.path.getsize(audio_path) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Audio file is empty"}
        )
    try:
        news_score = 0
        news_summary = "Could not analyze audio content"
        news_evidence = []
        news_result = {}
        if has_news_features and transcribe_audio and perform_search and judge_content:
            try:
                logger.info(f"Starting transcription of audio: {audio_path}")
                transcription = transcribe_audio(audio_path)
                if transcription:
                    from web.utils.judge import generate_search_query
                    if not GEMINI_API_KEY:
                        return JSONResponse(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "Gemini API key not configured"}
                        )
                    if not TAVILY_API_KEY:
                        return JSONResponse(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={"error": "Tavily API key not configured"}
                        )
                    logger.info("Generating search query from transcription")
                    try:
                        search_query = generate_search_query(transcription, GEMINI_API_KEY)
                        if not search_query:
                            words = transcription.split()[:30]
                            search_query = " ".join(words)
                            search_query = search_query[:350]
                            logger.warning(f"Generated fallback search query: {search_query}")
                    except Exception as e:
                        logger.warning(f"Failed to generate search query: {str(e)}")
                        words = transcription.split()[:30]
                        search_query = " ".join(words)
                        search_query = search_query[:350]
                        logger.warning(f"Generated fallback search query: {search_query}")
                    logger.info(f"Searching for related content with query: {search_query}")
                    search_results = perform_search(search_query, TAVILY_API_KEY)
                    if not search_results:
                        logger.warning("No search results returned")
                        news_result = {
                            "verdict": "Uncertain",
                            "confidence": 25,
                            "reasoning": "Could not find relevant information to verify content",
                            "sources": []
                        }
                    else:
                        try:
                            logger.info("Analyzing content credibility")
                            news_result = judge_content(transcription, search_results, GEMINI_API_KEY)
                        except Exception as e:
                            logger.error(f"Content credibility analysis failed: {str(e)}")
                            news_result = {
                                "verdict": "Uncertain",
                                "confidence": 0,
                                "reasoning": f"Analysis error: {str(e)[:100]}",
                                "sources": []
                            }
                    if "verdict" in news_result:
                        verdict_scores = {
                            "Authentic": 100,
                            "Misleading": 50, 
                            "Fake": 0,
                            "Uncertain": 25
                        }
                        verdict = news_result.get("verdict", "Uncertain")
                        news_score = news_result.get("confidence", verdict_scores.get(verdict, 0))
                        news_summary = news_result.get("reasoning", "No reasoning provided")
                        news_evidence = news_result.get("sources", [])
                    else:
                        news_score = news_result.get("score", 0)
                        news_summary = news_result.get("summary", "No summary provided")
                        news_evidence = news_result.get("evidence", [])
                else:
                    logger.warning(f"Failed to transcribe audio: {audio_path}")
            except Exception as e:
                logger.error(f"Audio processing failed: {str(e)}")
                news_summary = f"Audio analysis error: {str(e)}"
        else:
            logger.warning("News features not available for audio analysis")
            news_summary = "News analysis features not available"
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "audio_path": audio_path,
            "news_score": news_score,
            "news_summary": news_summary,
            "news_evidence": news_evidence,
            "verdict": news_result.get("verdict", "Uncertain"),
            "timestamp": time.time()
        }
        response = {
            "newsScore": news_score,
            "newsSummary": news_summary,
            "resultId": result_id
        }
        if news_result and "verdict" in news_result:
            response["verdict"] = news_result.get("verdict", "Uncertain")
            response["confidence"] = news_result.get("confidence", 0)
        if news_evidence:
            response["evidence"] = [
                {
                    "title": source.get("title", ""),
                    "url": source.get("url", "")
                } for source in news_evidence[:3]
            ]
        logger.info(f"Audio analysis completed with news_score: {news_score}, result_id: {result_id}")
        return response
    except Exception as e:
        logger.error(f"Error during audio analysis: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to analyze audio: {str(e)}"}
        )

class CombinedAnalysisRequest(BaseModel):
    videoPath: str
    audioPath: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "videoPath": "/tmp/video_123456.mp4",
                "audioPath": "/tmp/audio_123456.mp3"
            }
        }

@app.post("/analyze-combined")
async def analyze_combined(data: CombinedAnalysisRequest, background_tasks: BackgroundTasks):
    video_path = data.videoPath
    audio_path = data.audioPath
    if not video_path:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing video path"}
        )
    if not os.path.exists(video_path):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Video file not found at specified path"}
        )
    if not os.path.isfile(video_path):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Video path is not a file"}
        )
    if os.path.getsize(video_path) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Video file is empty"}
        )
    if audio_path:
        if not os.path.exists(audio_path):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Audio file not found at specified path"}
            )
        if not os.path.isfile(audio_path):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Audio path is not a file"}
            )
        if os.path.getsize(audio_path) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Audio file is empty"}
            )
    try:
        output_path = video_path.replace(".mp4", "_output.mp4")
        logger.info(f"Starting video analysis for {video_path}")
        try:
            fake_score = run(video_path, output_path)
        except Exception as e:
            logger.error(f"Video analysis failed: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": f"Video analysis failed: {str(e)}"}
            )
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            logger.error(f"No output video generated at {output_path}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Video analysis failed: No output video generated"}
            )
        news_score = 0
        news_summary = "Could not analyze audio content"
        news_evidence = []
        news_result = {}
        audio_used_path = None
        if has_news_features and transcribe_audio and perform_search and judge_content and audio_path:
            try:
                audio_used_path = audio_path
                logger.info(f"Transcribing audio from {audio_path}")
                transcription = transcribe_audio(audio_path)
                if transcription:
                    if not GEMINI_API_KEY:
                        logger.warning("Gemini API key not configured")
                        news_summary = "News analysis unavailable: Gemini API key not configured"
                    elif not TAVILY_API_KEY:
                        logger.warning("Tavily API key not configured")
                        news_summary = "News analysis unavailable: Tavily API key not configured"
                    else:
                        from web.utils.judge import generate_search_query
                        logger.info("Generating search query from transcription")
                        search_query = generate_search_query(transcription, GEMINI_API_KEY)
                        if search_query:
                            logger.info(f"Performing search with query: {search_query}")
                            search_results = perform_search(search_query, TAVILY_API_KEY)
                            if search_results:
                                logger.info("Analyzing content credibility")
                                news_result = judge_content(transcription, search_results, GEMINI_API_KEY)
                                if "verdict" in news_result:
                                    verdict_scores = {
                                        "Authentic": 100,
                                        "Misleading": 50, 
                                        "Fake": 0,
                                        "Uncertain": 25
                                    }
                                    verdict = news_result.get("verdict", "Uncertain")
                                    news_score = news_result.get("confidence", verdict_scores.get(verdict, 0))
                                    news_summary = news_result.get("reasoning", "No reasoning provided")
                                    news_evidence = news_result.get("sources", [])
                                else:
                                    news_score = news_result.get("score", 0)
                                    news_summary = news_result.get("summary", "No summary provided")
                                    news_evidence = news_result.get("evidence", [])
                            else:
                                logger.warning("No search results returned")
                                news_summary = "Could not find relevant information to verify content"
                        else:
                            logger.warning("Failed to generate search query")
                            news_summary = "Could not analyze content: Failed to generate search query"
                else:
                    logger.warning(f"Failed to transcribe audio from {audio_path}")
                    news_summary = "Could not transcribe audio content"
            except Exception as e:
                logger.error(f"Audio processing error: {str(e)}")
                news_summary = f"Audio analysis error: {str(e)}"
        elif not audio_path:
            logger.warning("No audio path provided for news analysis")
            news_summary = "No audio content provided for analysis"
        else:
            logger.warning("News features not available")
            news_summary = "News analysis features not available"
        result_id = str(uuid.uuid4())
        analysis_results[result_id] = {
            "output_path": output_path,
            "audio_path": audio_used_path if audio_used_path and os.path.exists(audio_used_path) else None,
            "fake_score": fake_score,
            "news_score": news_score,
            "news_summary": news_summary,
            "news_evidence": news_evidence,
            "verdict": news_result.get("verdict", "Uncertain"),
            "timestamp": time.time()
        }

        def delete_input_video():
            try:
                if os.path.exists(video_path):
                    os.unlink(video_path)
                    logger.info(f"Deleted input video: {video_path}")
            except Exception as e:
                logger.error(f"Failed to delete input video {video_path}: {str(e)}")
        
        background_tasks.add_task(delete_input_video)
        response = {
            "fakeScore": fake_score,
            "newsScore": news_score,
            "newsSummary": news_summary,
            "resultId": result_id
        }
        if news_result and "verdict" in news_result:
            response["verdict"] = news_result.get("verdict", "Uncertain")
            response["confidence"] = news_result.get("confidence", 0)
        if news_evidence:
            response["evidence"] = [
                {
                    "title": source.get("title", ""),
                    "url": source.get("url", "")
                } for source in news_evidence[:3]
            ]
        logger.info(f"Combined analysis completed with fake_score: {fake_score}, news_score: {news_score}, result_id: {result_id}")
        return response
    except Exception as e:
        logger.error(f"Error during combined analysis: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to analyze content: {str(e)}"}
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)