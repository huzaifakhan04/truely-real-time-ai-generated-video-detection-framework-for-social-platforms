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
        text = text.strip()
        if text.startswith("```json"):
            text = text.replace("```json", "", 1).strip()
        elif text.startswith("```"):
            text = text.replace("```", "", 1).strip()
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0].strip()
        text = text.strip()
        if not text.startswith("{"):
            text = "{" + text
        if not text.endswith("}"):
            text = text + "}"
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            return {
                "verdict": "uncertain",
                "confidence": 0,
                "reasoning": f"Error parsing model response: {str(e)}",
                "sources": []
            }
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
        
        # Clean up the response text to ensure it's valid JSON
        text = text.strip()
        # Handle markdown code blocks
        if text.startswith('```json'):
            text = text.replace('```json', '', 1).strip()
        elif text.startswith('```'):
            text = text.replace('```', '', 1).strip()
        
        if text.endswith('```'):
            text = text.rsplit('```', 1)[0].strip()
            
        # Ensure we have proper JSON braces
        text = text.strip()
        if not text.startswith('{'):
            text = '{' + text
        if not text.endswith('}'):
            text = text + '}'
            
        try:
            data = json.loads(text)
            q = str(data.get("query", "")).strip()
            if not q:
                # If query is empty, extract directly from transcript
                words = transcript.split()[:30]  # First 30 words
                q = " ".join(words)
        except json.JSONDecodeError:
            # Fallback: use the first part of transcript as the search query
            words = transcript.split()[:30]  # First 30 words
            q = " ".join(words)
            
        return q[:350]
    except Exception as e:
        raise RuntimeError(f"Gemini query generation error: {e}") from e