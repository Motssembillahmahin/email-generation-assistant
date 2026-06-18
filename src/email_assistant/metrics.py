"""Three custom evaluation metrics for the Email Generation Assistant.

Each metric scores one generated email in [0.0, 1.0] and carries a human-readable
``definition`` (emitted into the evaluation report, per assessment §2C).

| Metric | Focus | Technique |
|---|---|---|
| M1 Fact Coverage        | Are all key facts present and accurate? | LLM-as-judge (dual) |
| M2 Tone Alignment       | Does the email match the requested tone? | LLM-as-judge (dual) |
| M3 Conciseness & Structure | Subject/greeting/sign-off + length band | Deterministic Python |

Bias control: the two LLM-judge metrics run the SAME rubric through two judges from
different providers (Claude + Gemini) and average the result. Because every email is
scored by a judge from the *other* provider as well as its own, provider self-preference
is diluted rather than baked into the score. M3 is fully deterministic and provider-free.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from email_assistant import config
from email_assistant.vars import (
    DENSITY_BAND_HIGH,
    DENSITY_BAND_LOW,
    DENSITY_CEILING,
    DENSITY_FLOOR,
    JUDGE_MAX_TOKENS,
    JUDGE_MODELS,
)

# Human-readable definitions + logic for each metric, surfaced in results/report.
METRIC_DEFINITIONS: dict[str, str] = {
    "fact_coverage": (
        "Fact Coverage (LLM-as-judge, dual). For each key fact, two judges (Claude + "
        "Gemini) independently classify coverage as full (1.0 — stated accurately and "
        "completely), partial (0.5 — present but vague, incomplete, or slightly altered), "
        "or none (0.0 — absent or contradicted). Per-judge score = mean over facts; the "
        "metric is the mean across both judges. Partial credit makes the metric sensitive "
        "to subtle distortions, not just omissions. Range 0.0-1.0."
    ),
    "tone_alignment": (
        "Tone Alignment (LLM-as-judge, dual). Two judges (Claude + Gemini) each rate, on "
        "a strict 1-10 rubric, how precisely the email's greeting, word choice, pacing, "
        "and sign-off embody the requested tone (9-10 flawless; 6-7 minor slips; 3-5 off "
        "register; 1-2 wrong tone). Each rating is normalized as (score - 1) / 9 and the "
        "metric is the mean across both judges. Range 0.0-1.0."
    ),
    "conciseness_structure": (
        "Conciseness & Structure (deterministic Python). Mean of four equally weighted "
        "checks: (1) a non-empty subject line is present; (2) a greeting opens the body; "
        "(3) a sign-off closes the body; (4) a density score for body length — 1.0 inside "
        "the 50-150 word target band, decaying linearly to 0.0 at <=20 words (too thin) "
        "or >=200 words (the hard ceiling). No LLM is used. Range 0.0-1.0."
    ),
}


@dataclass
class MetricResult:
    """One metric's score for one email, with a transparent breakdown."""

    name: str
    score: float  # normalized to [0.0, 1.0]
    detail: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# LLM-judge plumbing
# --------------------------------------------------------------------------- #

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _judge_json(model_key: str, system: str, user: str) -> dict:
    """Run a judge model and parse the first JSON object out of its response.

    Judges are instructed to emit a single JSON object; we extract the first ``{...}``
    span to tolerate stray prose or code fences. Raises on unparseable output so the
    caller can record the failure rather than silently scoring it.
    """
    raw = config.generate(model_key, system, user, max_tokens=JUDGE_MAX_TOKENS)
    match = _JSON_RE.search(raw)
    if not match:
        raise ValueError(f"judge {model_key} returned no JSON object: {raw!r}")
    return json.loads(match.group(0))


_FACT_JUDGE_SYSTEM = (
    "You are a strict, literal fact-checker for emails. For each fact you are given, "
    "classify how the email covers it as exactly one of: 'full' (stated accurately and "
    "completely), 'partial' (present but vague, incomplete, or slightly altered), or "
    "'none' (absent or contradicted). Be demanding: rephrasing is fine, but any changed "
    "number, date, name, or weakened meaning is at most 'partial'. Reply with a single "
    'JSON object and nothing else: {"verdicts": [{"coverage": "full|partial|none"}, ...]} '
    "with one entry per fact, in the order given."
)

_TONE_JUDGE_SYSTEM = (
    "You are a demanding evaluator of email tone. Rate, on an integer scale of 1 to 10, "
    "how precisely the email's greeting, word choice, pacing, and sign-off embody the "
    "REQUESTED tone. Use the full range and be critical: reserve 9-10 for a flawless "
    "match; give 6-7 for a generally correct tone with minor slips (e.g. a missing "
    "contraction in a casual email, mild over-formality); 3-5 for a noticeably off "
    "register; 1-2 for the wrong tone. Judge tone only, not factual content. Reply with a "
    'single JSON object and nothing else: {"score": <1-10>}.'
)

_COVERAGE_SCORE = {"full": 1.0, "partial": 0.5, "none": 0.0}


def _fact_coverage_one_judge(model_key: str, key_facts: Sequence[str], email_text: str) -> float:
    if not key_facts:
        return 1.0
    facts_block = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(key_facts))
    user = f"FACTS:\n{facts_block}\n\nEMAIL:\n{email_text}"
    data = _judge_json(model_key, _FACT_JUDGE_SYSTEM, user)
    verdicts = data.get("verdicts", [])
    # Score the first len(key_facts) verdicts; any fact the judge omits scores 0.0.
    total = sum(
        _COVERAGE_SCORE.get(str(v.get("coverage", "none")).lower(), 0.0)
        for v in verdicts[: len(key_facts)]
    )
    return total / len(key_facts)


def _tone_one_judge(model_key: str, tone: str, email_text: str) -> float:
    user = f"REQUESTED TONE: {tone}\n\nEMAIL:\n{email_text}"
    data = _judge_json(model_key, _TONE_JUDGE_SYSTEM, user)
    score = max(1, min(10, int(round(float(data["score"])))))  # clamp to rubric range
    return (score - 1) / 9.0  # normalize 1-10 -> 0.0-1.0


def fact_coverage(
    key_facts: Sequence[str], email_text: str, judges: Sequence[str] = JUDGE_MODELS
) -> MetricResult:
    """M1 — fraction of key facts accurately present, averaged over dual judges."""
    per_judge = {m: _fact_coverage_one_judge(m, key_facts, email_text) for m in judges}
    score = sum(per_judge.values()) / len(per_judge)
    return MetricResult("fact_coverage", score, {"per_judge": per_judge, "n_facts": len(key_facts)})


def tone_alignment(
    tone: str, email_text: str, judges: Sequence[str] = JUDGE_MODELS
) -> MetricResult:
    """M2 — normalized 1-5 tone-match rating, averaged over dual judges."""
    per_judge = {m: _tone_one_judge(m, tone, email_text) for m in judges}
    score = sum(per_judge.values()) / len(per_judge)
    return MetricResult("tone_alignment", score, {"per_judge": per_judge})


# --------------------------------------------------------------------------- #
# M3 — deterministic conciseness & structure
# --------------------------------------------------------------------------- #

_SUBJECT_RE = re.compile(r"^\s*Subject:\s*(.+)$", re.MULTILINE)
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|dear|greetings|good (morning|afternoon|evening)|to whom)\b", re.IGNORECASE
)
_SIGNOFF_RE = re.compile(
    r"\b(best regards|kind regards|warm regards|warmly|best wishes|all the best|regards|"
    r"sincerely|cheers|thank you|thanks|respectfully|with (care|appreciation|gratitude|"
    r"sympathy)|take care|yours (sincerely|truly|faithfully)|best)\b",
    re.IGNORECASE,
)

def _density_score(word_count: int) -> float:
    """1.0 inside [50, 150]; linear decay to 0.0 at <=20 (thin) or >=200 (ceiling)."""
    if DENSITY_BAND_LOW <= word_count <= DENSITY_BAND_HIGH:
        return 1.0
    if word_count < DENSITY_BAND_LOW:
        return max(0.0, (word_count - DENSITY_FLOOR) / (DENSITY_BAND_LOW - DENSITY_FLOOR))
    return max(0.0, (DENSITY_CEILING - word_count) / (DENSITY_CEILING - DENSITY_BAND_HIGH))


def _split_subject_body(email_text: str) -> tuple[str, str]:
    match = _SUBJECT_RE.search(email_text)
    if not match:
        return "", email_text.strip()
    return match.group(1).strip(), email_text[match.end() :].strip()


def _is_greeting(line: str) -> bool:
    """A salutation: a known opener, or a short line ending in ',' or ':' at the top."""
    if _GREETING_RE.match(line):
        return True
    return len(line.split()) <= 8 and line.rstrip().endswith((",", ":"))


def _is_signoff(line: str) -> bool:
    """A valediction: a known closing phrase, or a short line ending in a comma."""
    if _SIGNOFF_RE.search(line):
        return True
    return len(line.split()) <= 5 and line.rstrip().endswith(",")


def conciseness_structure(email_text: str) -> MetricResult:
    """M3 — deterministic structure + length quality, mean of four [0,1] checks.

    Greeting/sign-off are detected by structural role (a short salutation line at the top;
    a short valediction line near the end), not a fixed phrase whitelist, so valid but
    unlisted openers/closings (e.g. "To the team,", "With sincere appreciation,") are not
    penalized.
    """
    subject, body = _split_subject_body(email_text)
    body_lines = [ln.strip() for ln in body.splitlines() if ln.strip()]

    has_subject = 1.0 if subject else 0.0
    has_greeting = 1.0 if body_lines and _is_greeting(body_lines[0]) else 0.0
    # Sign-off: look in the last few non-empty lines (closing phrase + name).
    has_signoff = 1.0 if any(_is_signoff(ln) for ln in body_lines[-3:]) else 0.0

    word_count = len(body.split())
    density = _density_score(word_count)

    checks = {
        "has_subject": has_subject,
        "has_greeting": has_greeting,
        "has_signoff": has_signoff,
        "density": density,
    }
    score = sum(checks.values()) / len(checks)
    return MetricResult(
        "conciseness_structure", score, {"checks": checks, "word_count": word_count}
    )
