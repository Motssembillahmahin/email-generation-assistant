"""Environment settings and provider access.

Loads ``.env`` once, here, and exposes the resolved settings via ``get_settings()`` so the
rest of the codebase reads configuration from this module rather than touching the
environment directly. ``generate()`` is a thin, uniform wrapper over the Anthropic and
Google SDKs so callers stay provider-agnostic.

Model definitions live in ``models.py``; tunable constants in ``vars.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

from email_assistant.models import MODELS
from email_assistant.vars import DEFAULT_MAX_TOKENS

load_dotenv()  # load .env (ANTHROPIC_API_KEY, GEMINI_API_KEY) once, at the settings boundary


@dataclass(frozen=True)
class Settings:
    """Resolved environment settings."""

    anthropic_api_key: str | None
    gemini_api_key: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the resolved settings, read from the environment after ``.env`` is loaded."""
    import os

    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
    )


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    key = get_settings().anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — add it to .env.")
    return anthropic.Anthropic(api_key=key)


@lru_cache(maxsize=1)
def _gemini_client():
    from google import genai

    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set — add it to .env.")
    return genai.Client(api_key=key)


def generate(model_key: str, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Run one completion against the chosen model and return its raw text.

    Args:
        model_key: A key in ``models.MODELS`` ("claude" or "gemini").
        system: The system prompt (identical across providers).
        user: The user message.
        max_tokens: Maximum output tokens.

    Returns:
        The model's raw text response (unparsed).
    """
    spec = MODELS[model_key]

    if spec.provider == "anthropic":
        resp = _anthropic_client().messages.create(
            model=spec.model_id,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    if spec.provider == "google":
        from google.genai import types

        resp = _gemini_client().models.generate_content(
            model=spec.model_id,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                # Minimize Gemini's internal reasoning so both models rely solely on the
                # prompt's <thinking> CoT — a fair, like-for-like comparison (Claude is
                # called without extended thinking). Also avoids the budget being spent on
                # hidden reasoning and truncating the email/judge JSON.
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
        )
        return resp.text or ""

    raise ValueError(f"unknown provider: {spec.provider!r}")
