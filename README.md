# Email Generation Assistant

An LLM-powered assistant that turns three structured inputs — **Intent**, **Key Facts**, and
**Tone** — into a polished, professional email, plus a custom evaluation harness that measures
output quality and compares two models.

This project is built around three things a senior LLM/prompt engineer is judged on:

1. **Advanced prompt engineering** — a documented Role-Play + Few-Shot + Chain-of-Thought template.
2. **A defensible evaluation strategy** — three custom metrics (LLM-as-judge + deterministic),
   scored over 10 scenarios with human reference emails.
3. **A model comparison** — the same prompt run on **Claude Opus 4.8** and **Gemini 3.5 Flash**,
   scored with a **dual-judge** design to neutralize LLM-as-judge self-preference bias.

> Status: scaffolding. Implementation lands incrementally — see the commit history.

## Quickstart

```bash
# 1. Install uv  (https://docs.astral.sh/uv/)
# 2. Install dependencies
make setup

# 3. Configure API keys
cp .env.example .env      # then add ANTHROPIC_API_KEY and GEMINI_API_KEY

# 4. Generate a single email
make generate ARGS="--intent 'Follow up after meeting' --tone formal"

# 5. Run the full evaluation (10 scenarios x 2 models) -> results/
make eval

# 6. Tests
make test
```

## How it works

- **Generator** (`src/email_assistant/generator.py`) — sends the structured inputs through the
  advanced prompt and parses the final email out of the model's response.
- **Prompt** (`src/email_assistant/prompts.py`) — the documented advanced-prompting template.
- **Metrics** (`src/email_assistant/metrics.py`):
  | Metric | Focus | Technique |
  |---|---|---|
  | Fact Coverage | Are all key facts accurately included? | LLM-as-judge (dual) |
  | Tone Alignment | Does the email match the requested tone? | LLM-as-judge (dual) |
  | Conciseness & Structure | Subject, greeting, sign-off, length band | Deterministic (Python) |
- **Evaluation** (`src/email_assistant/evaluate.py`) — runs all scenarios on both models, writes
  raw scores and averages to `results/` (CSV + JSON).

## Project layout

```
src/email_assistant/   config · prompts · generator · metrics · evaluate
data/scenarios.json    10 scenarios + human reference emails
results/               committed evaluation outputs (CSV/JSON)
report/REPORT.md       final report
tests/                 pytest suite
```
