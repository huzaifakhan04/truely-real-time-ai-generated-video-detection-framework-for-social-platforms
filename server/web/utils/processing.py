import time
from typing import (
    Dict,
    List,
    Tuple
)
from web.utils.audio import download_audio
from web.utils.transcribe import transcribe_audio
from web.utils.search import perform_search
from web.utils.similarity import score_similarity_batch
from web.utils.judge import (
    judge_content,
    generate_search_query
)
from web.models import Source

MINIMUM_SIMILARITY = 0.3
CONFIDENCE_THRESHOLD = 70
MINIMUM_CONFIDENCE = 40

def download_and_transcribe(video_url: str, tmp_dir: str, max_duration: int, groq_api_key: str) -> Tuple[str, float, float]:
    t0 = time.monotonic()
    audio_path = download_audio(video_url, tmp_dir, max_duration)
    t1 = time.monotonic()
    transcript = transcribe_audio(audio_path, groq_api_key, None)
    t2 = time.monotonic()
    return transcript, t1 - t0, t2 - t1


def search_and_filter_sources(transcript: str, tavily_api_key: str, gemini_api_key: str) -> Tuple[List[Dict], float]:
    t0 = time.monotonic()
    try:
        query_text = generate_search_query(transcript, gemini_api_key)
    except Exception as e:
        query_text = transcript.strip()[:350]

    tavily_results = perform_search(
        query=query_text,
        api_key=tavily_api_key,
        max_results=8,
    )
    news_results = []
    for result in tavily_results:
        url = result.get("url", "").lower()
        title = result.get("title", "").lower()
        if any(pattern in url for pattern in [".pdf", ".xml", "sitemap", "/sitemap"]):
            continue
        if any(pattern in title for pattern in ["television this week", "tv this week", "looking back"]):
            continue
        if any(pattern in url for pattern in ["/19", "/200", "/201"]) and not any(pattern in url for pattern in ["2024", "2025"]):
            continue
        news_results.append(result)
    t1 = time.monotonic()
    return news_results, t1 - t0

def score_and_filter_similarity(transcript: str, news_results: List[Dict], gemini_api_key: str) -> Tuple[List[Dict], List[Tuple[float, Dict]]]:
    try:
        scored_results = score_similarity_batch(transcript, news_results, gemini_api_key, max_workers=5)
    except Exception as e:
        scored_results = [(0.1, result) for result in news_results]
    if scored_results:
        scored_results.sort(key=lambda x: x[0], reverse=True)
        filtered_results = [result for similarity, result in scored_results if similarity >= MINIMUM_SIMILARITY]
    else:
        filtered_results = news_results
        scored_results = [(0.1, result) for result in news_results]
    return filtered_results, scored_results


def analyze_with_gemini(transcript: str, filtered_results: List[Dict], scored_results: List[Tuple[float, Dict]], gemini_api_key: str) -> Tuple[str, int, str, float]:
    t0 = time.monotonic()
    results_for_analysis = filtered_results if filtered_results else [result for _, result in scored_results[:5]]
    judgment = judge_content(transcript, results_for_analysis, gemini_api_key)
    raw_verdict = str(judgment.get("verdict", "uncertain")).lower()
    raw_confidence = int(judgment.get("confidence", 50))
    reasoning = judgment.get("reasoning", "")
    if raw_confidence >= CONFIDENCE_THRESHOLD:
        final_verdict = "authentic"
    elif raw_confidence >= MINIMUM_CONFIDENCE:
        final_verdict = "uncertain"
    else:
        final_verdict = "fake"
    if raw_verdict == "fake" and raw_confidence >= 80:
        final_verdict = "fake"
    t1 = time.monotonic()
    return final_verdict, raw_confidence, reasoning, t1 - t0

def prepare_sources(results_for_analysis: List[Dict], scored_results: List[Tuple[float, Dict]]) -> List[Source]:
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