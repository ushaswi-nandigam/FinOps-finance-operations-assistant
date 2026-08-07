"""Shared Gemini client. One place that talks to the LLM provider so every
caller (triage's L3 router, Fraud Agent's memo writer, and the real Verifier
Agent once it lands) gets the same client reuse, JSON-mode handling, and
token/cost accounting — instead of each reimplementing it slightly
differently.
"""

from google import genai
from google.genai import types

from services.common.config import settings

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def generate_text(model: str, prompt: str) -> tuple[str, int, int]:
    """Returns (text, tokens_in, tokens_out)."""
    response = get_client().models.generate_content(model=model, contents=prompt)
    usage = response.usage_metadata
    tokens_in = usage.prompt_token_count if usage else 0
    tokens_out = usage.candidates_token_count if usage else 0
    return response.text, tokens_in, tokens_out


def generate_json(model: str, prompt: str) -> tuple[dict, int, int]:
    """Returns (parsed_json, tokens_in, tokens_out)."""
    import json

    response = get_client().models.generate_content(
        model=model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    usage = response.usage_metadata
    tokens_in = usage.prompt_token_count if usage else 0
    tokens_out = usage.candidates_token_count if usage else 0
    return json.loads(response.text), tokens_in, tokens_out
