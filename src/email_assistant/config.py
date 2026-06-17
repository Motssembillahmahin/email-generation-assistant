"""Model configuration and provider access for the two compared models.

Model IDs live here (never inline elsewhere). `generate()` is a thin, uniform wrapper
over the Anthropic and Google SDKs so the rest of the codebase is provider-agnostic: it
takes a system prompt + user message and returns the model's raw text.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # load .env (ANTHROPIC_API_KEY, GEMINI_API_KEY) if present

DEFAULT_MAX_TOKENS = 2048


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str  # "anthropic" | "google"
    model_id: str
    label: str


# The two models compared with the SAME prompt (see report/REPORT.md).
MODELS: dict[str, ModelSpec] = {
    "claude": ModelSpec("claude", "anthropic", "claude-opus-4-8", "Claude Opus 4.8"),
    "gemini": ModelSpec("gemini", "google", "gemini-3.5-flash", "Gemini 3.5 Flash"),
}


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


@lru_cache(maxsize=1)
def _gemini_client():
    from google import genai

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set — add it to .env.")
    return genai.Client(api_key=key)


def generate(model_key: str, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Run one completion against the chosen model and return its raw text.

    Args:
        model_key: A key in ``MODELS`` ("claude" or "gemini").
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
            ),
        )
        return resp.text or ""

    raise ValueError(f"unknown provider: {spec.provider!r}")
