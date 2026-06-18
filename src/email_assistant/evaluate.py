"""Evaluation harness: run the 10 scenarios on both models and score them.

For each (model, scenario) it generates an email, scores it on the three custom metrics
(``metrics.py``), and writes two artifacts to ``results/``:

- ``scores.csv``  — one flat row per (model, scenario): the three metric scores + overall.
- ``results.json`` — metric definitions, full per-scenario detail (incl. the generated
  email and per-judge breakdowns), and per-model averages.

Run with ``make eval`` (``uv run python -m email_assistant.evaluate``). This makes live
API calls to both providers; ``ANTHROPIC_API_KEY`` and ``GEMINI_API_KEY`` must be set.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from email_assistant import metrics
from email_assistant.generator import EmailGenerator
from email_assistant.models import MODELS
from email_assistant.vars import JUDGE_MODELS, RESULTS_DIR, SCENARIOS_PATH

# The metrics, in report order. M3 is deterministic; M1/M2 are dual-judge.
_METRIC_ORDER = ("fact_coverage", "tone_alignment", "conciseness_structure")


def load_scenarios() -> list[dict]:
    """Load the evaluation scenarios from ``data/scenarios.json``."""
    return json.loads(SCENARIOS_PATH.read_text())["scenarios"]


def score_email(scenario: dict, email_text: str) -> dict[str, metrics.MetricResult]:
    """Score one generated email on all three metrics."""
    return {
        "fact_coverage": metrics.fact_coverage(scenario["key_facts"], email_text),
        "tone_alignment": metrics.tone_alignment(scenario["tone"], email_text),
        "conciseness_structure": metrics.conciseness_structure(email_text),
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate_model(model_key: str, scenarios: list[dict]) -> dict:
    """Generate and score every scenario for one model; return its full result block."""
    generator = EmailGenerator(model_key)
    spec = MODELS[model_key]
    rows: list[dict] = []

    for scenario in scenarios:
        print(f"  [{model_key}] {scenario['id']} ...", flush=True)
        generated = generator.generate(scenario["intent"], scenario["key_facts"], scenario["tone"])
        scored = score_email(scenario, generated.email_text)
        metric_scores = {name: scored[name].score for name in _METRIC_ORDER}
        rows.append(
            {
                "scenario_id": scenario["id"],
                "intent": scenario["intent"],
                "tone": scenario["tone"],
                "scores": metric_scores,
                "overall": _mean(list(metric_scores.values())),
                "detail": {name: scored[name].detail for name in _METRIC_ORDER},
                "email_text": generated.email_text,
            }
        )

    averages = {
        name: _mean([r["scores"][name] for r in rows]) for name in _METRIC_ORDER
    }
    averages["overall"] = _mean([r["overall"] for r in rows])

    return {
        "key": model_key,
        "label": spec.label,
        "model_id": spec.model_id,
        "scenarios": rows,
        "averages": averages,
    }


def write_csv(results: list[dict], path: Path) -> None:
    """Write the flat per-(model, scenario) score table."""
    fieldnames = ["model", "scenario_id", "tone", *_METRIC_ORDER, "overall"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for block in results:
            for row in block["scenarios"]:
                writer.writerow(
                    {
                        "model": block["key"],
                        "scenario_id": row["scenario_id"],
                        "tone": row["tone"],
                        **{m: round(row["scores"][m], 4) for m in _METRIC_ORDER},
                        "overall": round(row["overall"], 4),
                    }
                )
        # Trailing average rows, one per model.
        for block in results:
            writer.writerow(
                {
                    "model": block["key"],
                    "scenario_id": "AVERAGE",
                    "tone": "",
                    **{m: round(block["averages"][m], 4) for m in _METRIC_ORDER},
                    "overall": round(block["averages"]["overall"], 4),
                }
            )


def write_json(results: list[dict], path: Path) -> None:
    """Write metric definitions + full per-scenario detail + per-model averages."""
    payload = {
        "metric_definitions": metrics.METRIC_DEFINITIONS,
        "judges": list(JUDGE_MODELS),
        "models": {block["key"]: block for block in results},
    }
    path.write_text(json.dumps(payload, indent=2))


def main() -> None:
    scenarios = load_scenarios()
    RESULTS_DIR.mkdir(exist_ok=True)
    print(f"Evaluating {len(scenarios)} scenarios on {len(MODELS)} models...")

    results = [evaluate_model(model_key, scenarios) for model_key in MODELS]

    write_csv(results, RESULTS_DIR / "scores.csv")
    write_json(results, RESULTS_DIR / "results.json")

    print("\nPer-model averages:")
    for block in results:
        avg = block["averages"]
        print(
            f"  {block['label']:20} "
            f"facts={avg['fact_coverage']:.3f}  "
            f"tone={avg['tone_alignment']:.3f}  "
            f"struct={avg['conciseness_structure']:.3f}  "
            f"overall={avg['overall']:.3f}"
        )
    print(f"\nWrote {RESULTS_DIR / 'scores.csv'} and {RESULTS_DIR / 'results.json'}")


if __name__ == "__main__":
    main()
