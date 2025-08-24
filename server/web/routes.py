import os
import tempfile
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
from web.models import (
    VerifyNewsRequest,
    VerifyNewsResponse,
    Timings
)
from web.utils.processing import (
    download_and_transcribe,
    search_and_filter_sources,
    score_and_filter_similarity,
    analyze_with_gemini,
    prepare_sources,
)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
API_TIMEOUT_LIMIT = 300
TEMPORARY_DIRECTORY = "/tmp"

router = APIRouter()
app = FastAPI(title="Authenticity API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/verify_news", response_model=VerifyNewsResponse)
def verify_news(payload: VerifyNewsRequest) -> VerifyNewsResponse:
    if not GROQ_API_KEY or not TAVILY_API_KEY or not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Server configuration error: Missing API keys")
    tmp_dir = TEMPORARY_DIRECTORY or tempfile.gettempdir()
    audio_path = None
    video_url = str(payload.video_url)
    try:
        transcript, download_time, transcribe_time = download_and_transcribe(
            video_url, tmp_dir, API_TIMEOUT_LIMIT, GROQ_API_KEY
        )
        news_results, search_time = search_and_filter_sources(transcript, TAVILY_API_KEY, GEMINI_API_KEY)
        filtered_results, scored_results = score_and_filter_similarity(
            transcript, news_results, GEMINI_API_KEY
        )
        final_verdict, raw_confidence, reasoning, judge_time = analyze_with_gemini(
            transcript, filtered_results, scored_results, GEMINI_API_KEY
        )
        results_for_analysis = filtered_results if filtered_results else [result for _, result in scored_results[:5]]
        sources = prepare_sources(results_for_analysis, scored_results)
        timings = Timings(
            download_ms=int(download_time * 1000),
            transcribe_ms=int(transcribe_time * 1000), 
            search_ms=int(search_time * 1000),
            judge_ms=int(judge_time * 1000)
        )
        return VerifyNewsResponse(
            transcript=transcript,
            verdict=final_verdict,
            confidence=raw_confidence,
            sources=sources,
            reasoning=reasoning,
            timings=timings,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except Exception:
                pass