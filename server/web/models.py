from typing import (
    List,
    Optional
)
from pydantic import (
    BaseModel,
    HttpUrl
)

class VerifyNewsRequest(BaseModel):
    video_url: HttpUrl

class Source(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    score: Optional[float] = None

class Timings(BaseModel):
    download_ms: int
    transcribe_ms: int
    search_ms: int
    judge_ms: int

class VerifyNewsResponse(BaseModel):
    transcript: str
    verdict: str
    confidence: int
    sources: List[Source]
    reasoning: str
    timings: Optional[Timings] = None