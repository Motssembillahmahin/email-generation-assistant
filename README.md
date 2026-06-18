# Email Generation Assistant

An LLM-powered assistant that turns three structured inputs — **Intent**, **Key Facts**, and
**Tone** — into a polished, professional email, plus a custom evaluation harness that measures
output quality and compares two models.

This project has three parts:

1. **The assistant** — a documented Role-Play + Few-Shot + Chain-of-Thought prompt with a
   bounded self-refinement loop.
2. **The evaluation** — three custom metrics (LLM-as-judge + deterministic) over 10 scenarios
   with human reference emails.
3. **The comparison** — the same prompt on **Claude Opus 4.8** vs **Gemini 3.5 Flash**, scored
   with a **dual-judge** design to neutralize self-preference bias.

Results live in `results/` and the full write-up — prompt template, metric definitions, raw
data, and the model comparison — is in [`report/REPORT.md`](report/REPORT.md).

## Quickstart

```bash
# 1. Install uv  (https://docs.astral.sh/uv/)
# 2. Install dependencies
make setup

# 3. Configure API keys
cp .env.example .env      # then add ANTHROPIC_API_KEY and GEMINI_API_KEY

# 4. Generate a single email (CLI)
make generate ARGS="--intent 'Follow up after meeting' --tone formal"

# 4b. ...or try it interactively in the browser (optional Streamlit UI)
make app

# 5. Run the full evaluation (10 scenarios x 2 models) -> results/
make eval

# 6. Tests
make test
```

> `make app` launches a small [Streamlit](https://streamlit.io/) page (a thin wrapper over the
> same `EmailGenerator` the CLI uses) for typing in Intent / Key Facts / Tone and seeing the
> generated email. It's an optional convenience — `streamlit` installs only via the `demo` extra.

## Example

A real generated email from the `project-delay` scenario (Claude Opus 4.8), scoring
**fact coverage 1.00 · tone alignment 0.89 · conciseness & structure 1.00**.

**Input**

- **Intent:** Tell a client the project will be delayed, explain why, and reassure them
- **Tone:** apologetic but confident
- **Key facts:**
  - The website redesign will miss its original May 30 launch date
  - The new launch date is June 20
  - The delay is because we chose to add a round of accessibility testing
  - The agreed budget will not increase

**Generated email**

```
Subject: Update on your website redesign timeline

Hi [Name],

I want to be upfront with you: the website redesign will not meet its original
May 30 launch date, and I apologize for the change to our plan.

We have set a new launch date of June 20 to accommodate an additional round of
accessibility testing. This was a deliberate choice on our part — we want the
finished site to work seamlessly for every visitor, and these few extra weeks
will ensure it meets that standard.

Importantly, this does not affect our agreed budget, which remains unchanged.

I am happy to walk you through the revised plan whenever it suits you.

Best regards,
[Your name]
```

Full scores for all 10 scenarios across both models are in `results/` and analyzed in
[`report/REPORT.md`](report/REPORT.md).

## How it works

- **Config** (`src/email_assistant/{vars,models,config}.py`) — `vars.py` holds constants and paths,
  `models.py` the model registry, and `config.py` loads `.env`/settings and wraps both provider SDKs.
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
- **Interfaces** (`cli.py`, `app.py`) — a command-line entry point (`make generate`) and an
  optional Streamlit UI (`make app`), both thin wrappers over `EmailGenerator`.

## Project layout

```
src/email_assistant/   vars · models · config · prompts · generator · metrics · evaluate · cli · app
data/scenarios.json    10 scenarios + human reference emails
results/               committed evaluation outputs (CSV/JSON)
report/REPORT.md       final report
tests/                 pytest suite
```
