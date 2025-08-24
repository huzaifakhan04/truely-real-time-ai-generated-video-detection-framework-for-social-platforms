import json
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import google.generativeai as genai

from config import GEMINI_MODEL
from news_authenticity_api.prompts import similarity_prompt


def score_similarity(transcript: str, title: str, snippet: str, api_key: str) -> float:
    """Score similarity between transcript and source using Gemini.

    Args:
        transcript: The transcript of the news video
        title: The title of the news article
        snippet: The snippet of the news article
        api_key: The API key for the Gemini model

    Returns:
        A float between 0 and 1 indicating the similarity between the transcript and the source
    
    Raises:
        Exception: If the similarity score cannot be calculated
    """
    model = GEMINI_MODEL
    if model is None:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt_text = (
        f"{similarity_prompt}\n\n"
        f"transcript:\n{transcript}\n\n"
        f"title:\n{title}\n\n"
        f"snippet:\n{snippet}"
    )
    
    try:
        response = model.generate_content(
            [prompt_text],
            generation_config={
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        )
        
        text = response.text
        data: Dict = json.loads(text)
        val = float(data.get("similarity", 0.0))
        return max(0.0, min(1.0, val))
    except Exception as e:
        return 0.0


def score_similarity_batch(transcript: str, results: List[Dict], api_key: str, max_workers: int = 5) -> List[Tuple[float, Dict]]:
    """Score similarity for multiple results in parallel.
    
    Args:
        transcript: The transcript to compare against
        results: List of search results to score
        api_key: API key for Gemini
        max_workers: Maximum number of parallel threads
        
    Returns:
        List of (similarity_score, result) tuples
    """
    def score_single_result(result: Dict) -> Tuple[float, Dict]:
        similarity = score_similarity(
            transcript,
            result.get("title", ""),
            result.get("snippet", ""),
            api_key
        )
        return (similarity, result)
    
    scored_results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_result = {executor.submit(score_single_result, result): result for result in results}
        
        for future in as_completed(future_to_result):
            try:
                similarity, result = future.result()
                scored_results.append((similarity, result))
            except Exception as e:
                result = future_to_result[future]
                scored_results.append((0.0, result))
    
    return scored_results
