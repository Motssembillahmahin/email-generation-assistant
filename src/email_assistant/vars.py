"""Application-wide constants, tunable knobs, and filesystem paths.

Single source of truth for the magic numbers and locations used across the package, so a
value is defined once here and imported where needed (never duplicated inline).

Note: this module is named ``vars`` and intentionally shadows nothing — always import its
names explicitly (``from email_assistant.vars import DEFAULT_MAX_TOKENS``); do not bind it
as ``import ... as vars`` (which would shadow the ``vars()`` builtin in that scope).
"""

from __future__ import annotations

from pathlib import Path

# --- Filesystem paths (repo root is two levels above this file: src/email_assistant/) ---
ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = ROOT / "data" / "scenarios.json"
RESULTS_DIR = ROOT / "results"

# --- Generation ---
DEFAULT_MAX_TOKENS = 2048

# --- Evaluation / LLM-as-judge ---
JUDGE_MODELS: tuple[str, ...] = ("claude", "gemini")  # dual judges, one per provider
JUDGE_MAX_TOKENS = 600

# --- Conciseness & Structure metric: body-length scoring band (words) ---
DENSITY_BAND_LOW = 50
DENSITY_BAND_HIGH = 150
DENSITY_FLOOR = 20
DENSITY_CEILING = 200
