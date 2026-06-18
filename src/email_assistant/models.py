"""Model registry: the two models compared with the same prompt.

Model IDs are configuration and live here (never hardcoded inline elsewhere). Verify model
IDs and pricing against current provider docs rather than relying on memory.
"""

from __future__ import annotations

from dataclasses import dataclass


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
