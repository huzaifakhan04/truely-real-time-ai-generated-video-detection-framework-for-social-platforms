import time
from typing import Dict, List, Tuple

from news_authenticity_api.utils.audio import download_audio
from news_authenticity_api.utils.transcribe import transcribe_with_groq
from news_authenticity_api.utils.search import search_tavily
from news_authenticity_api.utils.similarity import score_similarity_batch
from news_authenticity_api.utils.judge import judge_with_gemini, generate_search_query
from news_authenticity_api.utils.logger import get_logger
from news_authenticity_api.models import Source, Timings
from config import (
    AUTH_SIMILARITY_MIN,
    AUTH_CONFIDENCE_REAL_THRESHOLD,
    AUTH_CONFIDENCE_UNCERTAIN_MIN,
)

logger = get_logger(__name__)


def download_and_transcribe(video_url: str, tmp_dir: str, max_duration: int, groq_api_key: str) -> Tuple[str, float, float]:
    """Download audio and transcribe it.
    Args:
        video_url: The URL of the video to download
        tmp_dir: The directory to save the audio file
        max_duration: The maximum duration of the audio to download
        groq_api_key: The API key for the Groq model

    Returns:
        A tuple containing the transcript, the time taken to download the audio, and the time taken to transcribe the audio

    Raises:
        Exception: If the download or transcription fails
    """
    t0 = time.monotonic()
    audio_path = download_audio(video_url, tmp_dir, max_duration)
    t1 = time.monotonic()
    
    transcript = transcribe_with_groq(audio_path, groq_api_key, None)
    logger.info("transcription complete: chars=%d", len(transcript))
    t2 = time.monotonic()
    
    return transcript, t1 - t0, t2 - t1


def search_and_filter_sources(transcript: str, tavily_api_key: str, gemini_api_key: str) -> Tuple[List[Dict], float]:
    """Generate search query and get filtered news sources
    Args:
        transcript: The transcript of the video
        tavily_api_key: The API key for the Tavily model
        gemini_api_key: The API key for the Gemini model

    Returns:
        A tuple containing the filtered news sources and the time taken to search and filter the sources

    Raises:
        Exception: If the search or filtering fails
    """
    t0 = time.monotonic()
    
    try:
        query_text = generate_search_query(transcript, gemini_api_key)
        logger.info("generated search query: len=%d", len(query_text))
    except Exception as e:
        logger.warning("query generation failed: %s; falling back to transcript slice", e)
        query_text = transcript.strip()[:350]

    tavily_results = search_tavily(
        query=query_text,
        api_key=tavily_api_key,
        max_results=8,
    )
    
    # Filter out non-news URLs and old/irrelevant content
    news_results = []
    for result in tavily_results:
        url = result.get("url", "").lower()
        title = result.get("title", "").lower()
        
        # Skip non-news formats
        if any(pattern in url for pattern in [".pdf", ".xml", "sitemap", "/sitemap"]):
            continue
            
        # Skip clearly irrelevant old content
        if any(pattern in title for pattern in ["television this week", "tv this week", "looking back"]):
            continue
            
        # Skip very old articles (pre-2020)
        if any(pattern in url for pattern in ["/19", "/200", "/201"]) and not any(pattern in url for pattern in ["2024", "2025"]):
            continue
            
        news_results.append(result)
    
    logger.info("tavily search complete: results=%d (filtered to %d news sources)", 
               len(tavily_results), len(news_results))
    
    t1 = time.monotonic()
    return news_results, t1 - t0


def score_and_filter_similarity(transcript: str, news_results: List[Dict], gemini_api_key: str) -> Tuple[List[Dict], List[Tuple[float, Dict]]]:
    """Score similarity in parallel and filter results.
    Args:
        transcript: The transcript of the video
        news_results: The news results to score
        gemini_api_key: The API key for the Gemini model

    Returns:
        A tuple containing the filtered news sources and the time taken to score and filter the sources
    """
    similarity_start = time.monotonic()
    
    try:
        logger.info("Starting parallel similarity scoring for %d results", len(news_results))
        scored_results = score_similarity_batch(transcript, news_results, gemini_api_key, max_workers=5)
        similarity_time = time.monotonic() - similarity_start
        logger.info("Parallel similarity scoring completed in %.2fs", similarity_time)
    except Exception as e:
        logger.error("Parallel similarity scoring failed: %s", e)
        scored_results = [(0.1, result) for result in news_results]
    
    # Sort by similarity and filter by threshold
    if scored_results:
        scored_results.sort(key=lambda x: x[0], reverse=True)
        filtered_results = [result for similarity, result in scored_results if similarity >= AUTH_SIMILARITY_MIN]
        logger.info("similarity filter: kept=%d of %d (min=%.2f)", 
                   len(filtered_results), len(scored_results), AUTH_SIMILARITY_MIN)
    else:
        logger.warning("Similarity scoring failed, using all news results")
        filtered_results = news_results
        scored_results = [(0.1, result) for result in news_results]
    
    return filtered_results, scored_results


def analyze_with_gemini(transcript: str, filtered_results: List[Dict], scored_results: List[Tuple[float, Dict]], gemini_api_key: str) -> Tuple[str, int, str, float]:
    """Analyze content with Gemini and determine verdict.
    Args:
        transcript: The transcript of the video
        filtered_results: The filtered news results
        scored_results: The scored news results
        gemini_api_key: The API key for the Gemini model

    Returns:
        A tuple containing the final verdict, the raw confidence, the reasoning, and the time taken to analyze the content

    Raises:
        Exception: If the analysis fails
    """
    t0 = time.monotonic()
    
    results_for_analysis = filtered_results if filtered_results else [result for _, result in scored_results[:5]]
    judgment = judge_with_gemini(transcript, results_for_analysis, gemini_api_key)
    
    raw_verdict = str(judgment.get("verdict", "uncertain")).lower()
    raw_confidence = int(judgment.get("confidence", 50))
    reasoning = judgment.get("reasoning", "")
    
    # Some rule based stuff to override the verdict cuz agent wildin sometimes
    if raw_confidence >= AUTH_CONFIDENCE_REAL_THRESHOLD:
        final_verdict = "authentic"
    elif raw_confidence >= AUTH_CONFIDENCE_UNCERTAIN_MIN:
        final_verdict = "uncertain"
    else:
        final_verdict = "fake"

    if raw_verdict == "fake" and raw_confidence >= 80:
        final_verdict = "fake"
    
    t1 = time.monotonic()
    return final_verdict, raw_confidence, reasoning, t1 - t0


def prepare_sources(results_for_analysis: List[Dict], scored_results: List[Tuple[float, Dict]]) -> List[Source]:
    """Prepare sources for response.
    Args:
        results_for_analysis: The results to analyze
        scored_results: The scored results

    Returns:
        A list of sources
    """
    sources = []
    sources_to_include = results_for_analysis if results_for_analysis else [result for _, result in scored_results[:5]]
    
    for result in sources_to_include:
        try:
            sources.append(Source(
                title=result.get("title") or "",
                url=result.get("url") or "",
                snippet=(result.get("snippet") or "")[:500],
                score=result.get("score"),
            ))
        except Exception:
            continue
    
    return sources



