"""Unit tests for the evaluation metrics — no live API calls.

The deterministic metric (conciseness & structure) is tested directly. The two LLM-judge
metrics are tested for their deterministic parts — score normalization, partial-credit
mapping, dual-judge averaging, and JSON extraction — by monkeypatching the judge call.
"""

import pytest

from email_assistant import metrics
from email_assistant.metrics import (
    _density_score,
    _is_greeting,
    _is_signoff,
    conciseness_structure,
    fact_coverage,
    tone_alignment,
)

# --------------------------------------------------------------------------- #
# M3 — deterministic: density band
# --------------------------------------------------------------------------- #


def test_density_full_inside_band():
    assert _density_score(50) == 1.0
    assert _density_score(100) == 1.0
    assert _density_score(150) == 1.0


def test_density_zero_at_and_beyond_bounds():
    assert _density_score(20) == 0.0  # floor
    assert _density_score(10) == 0.0  # below floor
    assert _density_score(200) == 0.0  # ceiling
    assert _density_score(300) == 0.0  # above ceiling


def test_density_linear_decay():
    assert _density_score(175) == pytest.approx(0.5)  # halfway 150->200
    assert _density_score(35) == pytest.approx((35 - 20) / (50 - 20))  # decay below band


# --------------------------------------------------------------------------- #
# M3 — greeting / sign-off detection (incl. structural-role cases)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line",
    [
        "Hi [Name],",
        "Hello there,",
        "Dear Dr. Smith,",
        "Hey team,",
        "Good morning,",
        "To whom it may concern,",
        "To the Support Management Team,",  # structural: short line ending in comma
    ],
)
def test_greeting_accepts_valid(line):
    assert _is_greeting(line)


def test_greeting_rejects_prose():
    assert not _is_greeting("I am writing to inform you about the upcoming policy changes.")


@pytest.mark.parametrize(
    "line",
    [
        "Best regards,",
        "Sincerely,",
        "Warmly,",
        "Cheers,",
        "With care,",
        "With sincere appreciation,",  # structural: not in whitelist, short + comma
    ],
)
def test_signoff_accepts_valid(line):
    assert _is_signoff(line)


def test_signoff_rejects_prose():
    assert not _is_signoff("Please let me know if you have any questions about this.")


# --------------------------------------------------------------------------- #
# M3 — full metric
# --------------------------------------------------------------------------- #


def _email(subject="Hi", greeting="Hi [Name],", words=100, signoff="Best regards,"):
    body = "word " * words
    return f"Subject: {subject}\n\n{greeting}\n\n{body}\n\n{signoff}\n[Your name]"


def test_well_formed_email_scores_one():
    r = conciseness_structure(_email())
    assert r.score == 1.0
    assert r.detail["checks"] == {
        "has_subject": 1.0,
        "has_greeting": 1.0,
        "has_signoff": 1.0,
        "density": 1.0,
    }


def test_missing_subject_penalized():
    r = conciseness_structure(_email().split("\n\n", 1)[1])  # drop the Subject line
    assert r.detail["checks"]["has_subject"] == 0.0
    assert r.score == pytest.approx(0.75)


def test_overlong_body_zero_density():
    r = conciseness_structure(_email(words=250))
    assert r.detail["checks"]["density"] == 0.0


# --------------------------------------------------------------------------- #
# M1 — fact coverage: partial-credit mapping + aggregation (judge stubbed)
# --------------------------------------------------------------------------- #


def test_fact_coverage_partial_credit(monkeypatch):
    canned = {"verdicts": [{"coverage": "full"}, {"coverage": "partial"}, {"coverage": "none"}]}
    monkeypatch.setattr(metrics, "_judge_json", lambda *a, **k: canned)
    r = fact_coverage(["f1", "f2", "f3"], "email", judges=("claude",))
    assert r.score == pytest.approx((1.0 + 0.5 + 0.0) / 3)


def test_fact_coverage_missing_verdict_counts_zero(monkeypatch):
    monkeypatch.setattr(metrics, "_judge_json", lambda *a, **k: {"verdicts": [{"coverage": "full"}]})
    r = fact_coverage(["f1", "f2"], "email", judges=("claude",))
    assert r.score == pytest.approx(0.5)  # one full + one missing -> (1+0)/2


def test_fact_coverage_no_facts_is_one():
    assert fact_coverage([], "email").score == 1.0  # vacuously covered; no API call


# --------------------------------------------------------------------------- #
# M2 — tone: 1-10 normalization, clamping, dual-judge averaging (judge stubbed)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("raw,expected", [(10, 1.0), (1, 0.0), (5, (5 - 1) / 9)])
def test_tone_normalization(monkeypatch, raw, expected):
    monkeypatch.setattr(metrics, "_judge_json", lambda *a, **k: {"score": raw})
    assert tone_alignment("formal", "e", judges=("claude",)).score == pytest.approx(expected)


@pytest.mark.parametrize("raw,expected", [(99, 1.0), (0, 0.0)])
def test_tone_clamps_out_of_range(monkeypatch, raw, expected):
    monkeypatch.setattr(metrics, "_judge_json", lambda *a, **k: {"score": raw})
    assert tone_alignment("formal", "e", judges=("claude",)).score == pytest.approx(expected)


def test_dual_judge_averages(monkeypatch):
    per_model = {"claude": {"score": 10}, "gemini": {"score": 1}}
    monkeypatch.setattr(metrics, "_judge_json", lambda model, s, u: per_model[model])
    r = tone_alignment("formal", "e")  # default judges: claude + gemini
    assert r.score == pytest.approx((1.0 + 0.0) / 2)
    assert set(r.detail["per_judge"]) == {"claude", "gemini"}


# --------------------------------------------------------------------------- #
# Judge JSON extraction
# --------------------------------------------------------------------------- #


def test_judge_json_extracts_from_fenced_output(monkeypatch):
    monkeypatch.setattr(metrics.config, "generate", lambda *a, **k: 'ok ```json\n{"score": 7}\n``` !')
    assert metrics._judge_json("claude", "s", "u") == {"score": 7}


def test_judge_json_raises_without_object(monkeypatch):
    monkeypatch.setattr(metrics.config, "generate", lambda *a, **k: "no json here")
    with pytest.raises(ValueError):
        metrics._judge_json("claude", "s", "u")
