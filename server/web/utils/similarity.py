import json
from typing import (
    Dict,
    List,
    Tuple
)
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)
import google.generativeai as genai
from web.prompts import similarity_prompt

def score_similarity(transcript: str, title: str, snippet: str, api_key: str) -> float:
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