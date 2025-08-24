import json
from typing import Any, Dict, List
from config import GEMINI_MODEL
import google.generativeai as genai
from news_authenticity_api.prompts import judge_prompt, search_query_prompt


def judge_with_gemini(transcript: str, sources: List[Dict[str, Any]], api_key: str) -> Dict[str, Any]:
    """
    Judge the authenticity of a news video. Uses Gemini for judgment.

    Args:
        transcript: The transcript of the video
        sources: The list of sources to use for the judgment
        api_key: The API key for the Gemini model

    Returns:
        A dictionary containing the verdict, confidence, reasoning, and sources

    Raises:
        RuntimeError: If the judgment fails
    
    """
    model = GEMINI_MODEL
    if model is None:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
    prompt_text = (
        f"{judge_prompt}\n\nTRANSCRIPT:\n{transcript}\n\n"
        f"SOURCES JSON:\n{json.dumps(sources, ensure_ascii=False)}"
    )
    try:
        response = model.generate_content(
            [prompt_text],
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )
        text = response.text
        return json.loads(text)
    except Exception as e:
        raise RuntimeError(f"Gemini error: {e}") from e


def generate_search_query(transcript: str, api_key: str) -> str:
    """
    Generate a search query for a news video. Uses Gemini for query generation.

    Args:
        transcript: The transcript of the video
        api_key: The API key for the Gemini model

    Returns:
        A string containing the search query

    Raises:
        RuntimeError: If the query generation fails
    """
    model = GEMINI_MODEL
    if model is None:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
    prompt_text = f"{search_query_prompt}\n\nTRANSCRIPT:\n{transcript}"
    try:
        response = model.generate_content(
            [prompt_text],
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )
        text = response.text
        data = json.loads(text)
        q = str(data.get("query", "")).strip()
        if not q:
            raise ValueError("empty query from model")
        return q[:350]
    except Exception as e:
        raise RuntimeError(f"Gemini query generation error: {e}") from e


