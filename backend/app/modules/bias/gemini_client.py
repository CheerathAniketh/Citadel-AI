import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from google import genai
from config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY or "")

GEMINI_TIMEOUT_SECONDS = 15
GEMINI_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _is_api_error(e: Exception) -> bool:
    err = str(e)
    return any(code in err for code in [
        "429", "RESOURCE_EXHAUSTED", "400", "INVALID_ARGUMENT",
        "API_KEY_INVALID", "API Key not found", "GEMINI_TIMEOUT", "TIMEOUT", "timed out"
    ])


def _generate_content_with_timeout(prompt: str, timeout_seconds: int = GEMINI_TIMEOUT_SECONDS):
    future = GEMINI_EXECUTOR.submit(
        client.models.generate_content,
        model="gemini-3.6-flash",
        contents=prompt,
    )
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise TimeoutError("GEMINI_TIMEOUT") from exc


def generate_explanation(prompt: str) -> str:
    """Returns Gemini's text response, raises on failure so caller can fall back."""
    response = _generate_content_with_timeout(prompt)
    return response.text