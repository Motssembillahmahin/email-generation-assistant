# Email Generation Assistant — Final Report

> Living document. The prompt-engineering section is complete; the evaluation,
> raw-data, and comparison sections are filled once the eval harness runs.

## 1. Overview

An LLM assistant that turns three structured inputs — **Intent**, **Key Facts**, and
**Tone** — into a polished, professional email, evaluated with three custom metrics and
compared across two models (**Claude Opus 4.8** vs **Gemini 3.5 Flash**) using the same
prompt, with a dual-judge design to neutralize LLM-as-judge self-preference bias.

---

## 2. Prompt Engineering

The canonical prompt is `src/email_assistant/prompts.py::SYSTEM_PROMPT`. The per-request
Intent / Key Facts / Tone are supplied in the user turn via `build_user_message(...)`.

### 2.1 Architecture — 11 explicit, gradeable sections

`Role · Context · Objective · Priority Order · Instructions · Constraints ·
Common Pitfalls · Edge Cases · Output Format · Examples · Quality Checks`

Each section is independently inspectable, so the prompt can be reviewed as a structured
artifact rather than a wall of text.

### 2.2 Technique selection

Techniques are deployed by *fit*, not by buzzword count — the senior signal is knowing
*when* a technique helps and when it would be cargo-cult.

| Technique | Applied? | Why |
|---|---|---|
| **Persona / Role-Play** | Yes | An expert-communications identity lifts register and professionalism without a long list of style rules. |
| **Chain-of-Thought** | Yes | A `<thinking>` plan enumerates every Key Fact and maps the requested Tone *before* composing. |
| **Refinement Loop** | Yes (core) | Draft → self-critique against the Quality Checks → revise, bounded to ≤2 passes. The highest-leverage lever for email quality. |
| **Chain of Density** | No | A *summarization* densifier; an email is not a summary, so it does not apply. |
| **Tree of Thoughts** | No | For branching/backtracking reasoning; email drafting does not need it, and ToT raises single-prompt fabrication risk. |

### 2.3 Robustness features

- **Priority Order** (Accuracy ▶ Tone ▶ Conciseness ▶ Style) resolves conflicting
  requirements deterministically instead of leaving trade-offs to chance.
- **Bounded refinement loop** (one critique + up to one further revision) prevents
  infinite revision and over-engineering.
- **Common Pitfalls** encode known failure patterns as explicit negative constraints.
- **Edge-case protocol** handles contradictory facts, impossible tone, and missing
  details without fabrication; if a request truly cannot be completed, the assistant
  still returns an `<email>` whose body states the blocker (the parsing contract always
  holds).
- **Measurable density constraint** (body ~50–150 words, hard ceiling 200) replaces the
  subjective "be concise"; metric 3 is aligned to the same band.
- **Actionable Quality Checks** — the model verifies each Key Fact against a real
  sentence in its draft, rather than self-attesting to vague categories.

### 2.4 Output contract

The model reasons inside `<thinking>...</thinking>` (parsed out and discarded) and emits
the deliverable inside `<email>...</email>` (parsed and scored). XML-style tags make the
output machine-parseable and behave consistently across both providers. The Quality
Checks the model self-critiques against are deliberately aligned with the evaluation
metrics, so the model optimizes for exactly what we measure.

### 2.5 Prompt template

The full prompt template is reproduced from `src/email_assistant/prompts.py::SYSTEM_PROMPT`
at report-finalization time (kept in code as the single source of truth to avoid drift).

---

## 3. Evaluation Strategy — Custom Metrics

_Forthcoming — defined and implemented in `src/email_assistant/metrics.py`._

## 4. Raw Evaluation Data

_Forthcoming — generated into `results/` (CSV + JSON) by `src/email_assistant/evaluate.py`._

## 5. Model Comparison & Analysis

_Forthcoming — Claude Opus 4.8 vs Gemini 3.5 Flash on the three custom metrics._
