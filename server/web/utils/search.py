from typing import (
    Any,
    Dict,
    List,
    Optional
)
import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
REPUTABLE_DOMAINS = [
    "cnn.com",
    "bbc.com", 
    "cbsnews.com",
    "foxnews.com"
    "aljazeera.com",
    "bloomberg.com",
]

def perform_search(
    query: str,
    api_key: str,
    max_results: int = 5,
    include_domains: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False,
    }
    domains = include_domains or REPUTABLE_DOMAINS
    if domains:
        body["include_domains"] = domains
    with httpx.Client(timeout=60) as client:
        resp = client.post(TAVILY_SEARCH_URL, headers=headers, json=body)
    if resp.status_code != 200:
        raise RuntimeError(f"Tavily search error: {resp.text}")
    data = resp.json()
    results = data.get("results", [])
    normalized: List[Dict[str, Any]] = []
    for r in results:
        url = r.get("url", "").lower()
        title = r.get("title", "").lower()
        if any(pattern in url for pattern in ["archive", "/19", "/200", "/201"]) and not any(pattern in url for pattern in ["2024", "2025"]):
            continue
        if any(pattern in title for pattern in ["this week", "looking back", "archives", "television this week"]):
            continue
        normalized.append({
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": r.get("content") or r.get("snippet") or "",
            "score": r.get("score"),
        })
    return normalized