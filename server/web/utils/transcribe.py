from typing import Optional
from groq import Groq
from web.config import GROQ_API_KEY

def transcribe_audio(audio_path: str, language: Optional[str] = None) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    with open(audio_path, "rb") as f:
        try:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=(audio_path, f),
                response_format="json",
                language=language if language else None,
            )
        except Exception as e:
            raise RuntimeError(f"Groq transcription error: {e}") from e
    text = getattr(result, "text", None) if hasattr(result, "text") else None
    if not text and isinstance(result, dict):
        text = result.get("text")
    if not text:
        raise RuntimeError("Empty transcription returned")
    return text