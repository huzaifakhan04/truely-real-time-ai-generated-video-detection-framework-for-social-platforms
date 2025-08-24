import json
from typing import (
    Any,
    Dict,
    List
)
import google.generativeai as genai
from web.prompts import (
    judge_prompt,
    search_query_prompt
)

def judge_content(transcript: str, sources: List[Dict[str, Any]], api_key: str) -> Dict[str, Any]:
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