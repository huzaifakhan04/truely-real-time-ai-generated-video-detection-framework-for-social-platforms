from typing import Optional

from config import GROQ_CLIENT


def transcribe_with_groq(audio_path: str, api_key: str, language: Optional[str] = None) -> str:
    """
    Transcribe audio using Groq Whisper.

    Args:
        audio_path: The path to the audio file
        api_key: The API key for the Groq API
        language: The language of the audio

    Returns:
        A string containing the transcription

    Raises:
        RuntimeError: If the transcription fails
    """
    client = GROQ_CLIENT
    if client is None:
        raise RuntimeError("Groq client not initialized")
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


