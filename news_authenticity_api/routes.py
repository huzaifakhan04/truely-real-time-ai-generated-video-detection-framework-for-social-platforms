import os
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import (
    GROQ_API_KEY,
    TAVILY_API_KEY,
    GEMINI_API_KEY,
    AUTH_MAX_DURATION_SECONDS,
    AUTH_TMP_DIR,
)
from news_authenticity_api.models import VerifyNewsRequest, VerifyNewsResponse, Timings
from news_authenticity_api.utils.logger import get_logger
from news_authenticity_api.utils.processing import (
    download_and_transcribe,
    search_and_filter_sources,
    score_and_filter_similarity,
    analyze_with_gemini,
    prepare_sources,
)


logger = get_logger(__name__)

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
    """Verify the authenticity of a news video.
    
    Args:
        payload: VerifyNewsRequest

    Returns: VerifyNewsResponse

    Raises:
        HTTPException: If the server is misconfigured or the request fails
        Exception: If the verification process fails    
    """
    if not GROQ_API_KEY or not TAVILY_API_KEY or not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: missing API keys")

    tmp_dir = AUTH_TMP_DIR or tempfile.gettempdir()
    audio_path = None
    video_url = str(payload.video_url)
    logger.info("verify_news request: video_url=%s", video_url)

    try:
        # Download and transcribe
        transcript, download_time, transcribe_time = download_and_transcribe(
            video_url, tmp_dir, AUTH_MAX_DURATION_SECONDS, GROQ_API_KEY
        )

        # Search and filter sources
        news_results, search_time = search_and_filter_sources(transcript, TAVILY_API_KEY, GEMINI_API_KEY)

        # Score similarity and filter
        filtered_results, scored_results = score_and_filter_similarity(
            transcript, news_results, GEMINI_API_KEY
        )

        # Analyze with Gemini
        final_verdict, raw_confidence, reasoning, judge_time = analyze_with_gemini(
            transcript, filtered_results, scored_results, GEMINI_API_KEY
        )

        # Prepare response
        results_for_analysis = filtered_results if filtered_results else [result for _, result in scored_results[:5]]
        sources = prepare_sources(results_for_analysis, scored_results)
        
        timings = Timings(
            download_ms=int(download_time * 1000),
            transcribe_ms=int(transcribe_time * 1000), 
            search_ms=int(search_time * 1000),
            judge_ms=int(judge_time * 1000)
        )

        logger.info(
            "verdict=%s confidence=%d timings_ms download=%d transcribe=%d search=%d judge=%d",
            final_verdict, raw_confidence, timings.download_ms, 
            timings.transcribe_ms, timings.search_ms, timings.judge_ms
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
        logger.exception("verify_news failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except Exception:
                logger.debug("failed to cleanup audio temp file: %s", audio_path)