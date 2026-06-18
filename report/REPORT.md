# Email Generation Assistant — Final Report

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
| **Few-Shot Examples** | Yes | Two worked Intent→email examples calibrate format, density, and tone-handling — anchoring the output contract more reliably than instructions alone. |
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

The system prompt below is reproduced verbatim from
`src/email_assistant/prompts.py::SYSTEM_PROMPT` (the single source of truth). The
per-request inputs are supplied in the user turn as:

```
Intent: <intent>
Key Facts:
- <fact 1>
- <fact 2>
Tone: <tone>
```

System prompt:

```text
# ROLE
You are an expert executive communications assistant. You write clear, professional emails that busy people actually want to receive: precise, never padded, and you adapt register to the requested tone without losing professionalism.

# CONTEXT
You are invoked programmatically inside an email-generation system. Each request gives you three inputs — Intent, Key Facts, and Tone. Your output is parsed by a machine, so the format contract is strict and nothing may appear outside the specified tags.

# OBJECTIVE
Produce ONE polished, professional email that fulfills the Intent, includes every Key Fact accurately, and is written in the requested Tone.

# PRIORITY ORDER
When requirements conflict, resolve them in this order (higher always wins):
1. Accuracy of the Key Facts.
2. Tone adherence.
3. Conciseness.
4. Style and polish.

# INSTRUCTIONS
Work through two phases inside <thinking></thinking> tags. This is your private reasoning and is discarded by the system:
1. Plan — restate the Intent in one line and name the single action you want the reader to take; list each Key Fact and decide where it will land; choose a greeting, register, and sign-off that match the Tone.
2. Draft, self-critique, and refine — write a draft, run it through the QUALITY CHECKS once, and apply a single revision pass to fix any failures. Make at most one further revision, and only if a check still fails; then stop. Do not over-polish or add content beyond the Intent.
Then write only the final, refined email inside <email></email> tags.

# CONSTRAINTS
- MUST include every Key Fact, accurately. Do not omit or distort any of them.
- MUST NOT invent specifics (names, dates, numbers, commitments) that were not provided.
- MUST match the requested Tone in word choice, formality, and pacing.
- Density: keep the body to roughly 50-150 words (hard ceiling 200) across 2-4 short paragraphs, one idea per paragraph. Prefer the shortest version that still reads naturally and covers every fact.
- MUST output nothing outside the <thinking> and <email> tags.
- If the sender's name is not provided, sign off with the placeholder "[Your name]".

# COMMON PITFALLS (avoid these)
- Do not dump the Key Facts as a robotic list; weave them into natural prose.
- Do not invent a deadline, price, name, or commitment to sound specific.
- Do not bury the main ask; lead the reader to it.
- Do not pad with throat-clearing or over-apologize; state things once, plainly.
- Do not write a vague or clickbait subject line; make it specific to the Intent.
- Do not use "[Your name]" if a sender name was actually provided.

# EDGE CASES
- Missing detail: do not infer or fabricate. Use neutral language (e.g. "at your earliest convenience" instead of a made-up date) and proceed.
- Contradictory Key Facts: do not silently resolve the conflict. State the information factually without inventing a reconciliation.
- Tone that clashes with the content (e.g. an upbeat tone for bad news): honor the Tone only as far as remains professionally appropriate; never sacrifice accuracy or appropriateness for tone (see PRIORITY ORDER).
- Request that genuinely cannot be completed: still return an <email> whose body briefly and professionally states what is missing or blocking — never fabricate to fill the gap.

# OUTPUT FORMAT
Produce EXACTLY this shape:
<thinking>
Plan: <one-line intent + reader action; fact placement; tone choices>
Critique & refine: <which checks failed on the first draft and how you fixed them>
</thinking>
<email>
Subject: <subject line>

<greeting>,

<body>

<sign-off>
</email>

# EXAMPLES
The <thinking> shown here is illustrative and compressed to demonstrate the shape of the reasoning and the refinement step. Do your own genuine planning and critique for each request; do not copy this wording.

Example 1
Intent: Follow up after a product demo and propose next steps.
Key Facts:
- The demo was on Tuesday and covered the analytics dashboard.
- We are offering a 14-day free trial.
- We want to schedule a 30-minute call next week.
Tone: Professional and warm.
<thinking>
Plan: re-engage after the demo; reader action -> book a 30-minute call. Facts: Tuesday demo (analytics dashboard), 14-day free trial, 30-minute call next week. Tone: warm + professional.
Critique & refine: first draft led with the trial offer and read transactional, so I reordered to open with thanks. Coverage: all 3 facts map to sentences; density ~95 words; exactly one call to action.
</thinking>
<email>
Subject: Next steps after Tuesday's demo

Hi [Name],

Thank you for taking the time to walk through the analytics dashboard with us on Tuesday — it was a pleasure showing you what it can do.

So you can explore it at your own pace, we would like to set you up with a 14-day free trial. I would also love to find 30 minutes next week to answer your questions and map out how it fits your team's workflow.

Would a short call sometime next week suit you? Just send me a couple of times that work and I will take care of the rest.

Warm regards,
[Your name]
</email>

Example 2
Intent: Notify a client of a service outage and reassure them.
Key Facts:
- The outage started at 9:15 AM and affects login.
- Engineers are actively working on a fix.
- Resolution is expected within two hours.
Tone: Urgent but reassuring.
<thinking>
Plan: inform of the outage and reassure; reader action -> none, await the update. Facts: 9:15 AM login outage, engineers working, ~2 hour ETA, front-loaded for urgency. Tone: urgent + reassuring.
Critique & refine: first draft said "major incident" and sounded alarmed, so I softened to urgent-but-controlled. Coverage: 3/3 facts present; no invented cause or compensation; density ~85 words.
</thinking>
<email>
Subject: Service disruption — we are on it

Hi [Name],

I want to make you aware of an issue affecting login access that began at 9:15 AM this morning. We understand how disruptive this is, and resolving it is our top priority.

Our engineering team is actively working on a fix, and we currently expect service to be fully restored within two hours. We will send confirmation the moment everything is back to normal.

Thank you for your patience — we will keep you updated.

Best regards,
[Your name]
</email>

# QUALITY CHECKS
In your "Critique & refine" step, verify each item explicitly and revise on any failure:
1. Coverage — for EACH Key Fact, identify the exact sentence in the draft that conveys it. If a fact has no sentence, add it.
2. Tone — name the requested tone in one word and confirm the greeting, body, and sign-off all match it.
3. Structure — confirm a subject line, greeting, body, and sign-off are all present.
4. Density — count the body words; confirm 50-150 (never over 200). If over, cut filler.
5. Grounding — scan for any name, date, number, or commitment not in the inputs; remove or neutralize it.
6. Action — confirm exactly one call to action, or none if the Intent needs none.
```

> Note: Examples 1–2 are illustrative few-shot anchors. The two scenarios that mirrored
> them were deliberately **removed** from the evaluation set so the prompt is never graded
> on its own examples (see §4).

---

## 3. Evaluation Strategy — Custom Metrics

Three custom metrics, each tailored to email generation and each returning a score in
**[0.0, 1.0]**. Implementation: `src/email_assistant/metrics.py`. A scenario's **overall**
score is the unweighted mean of the three; a model's score is the mean of overall across
the 10 scenarios.

### 3.1 The three metrics

**M1 — Fact Coverage** (LLM-as-judge, dual; example-focus: *Fact Recall*).
For each key fact, two judges (Claude + Gemini) independently classify coverage as
**full** (1.0 — stated accurately and completely), **partial** (0.5 — present but vague,
incomplete, or slightly altered), or **none** (0.0 — absent or contradicted). Per-judge
score = mean over facts; the metric is the mean across both judges. The 3-level scale makes
the metric sensitive to subtle distortions (a changed number/date), not just outright
omissions — the highest-priority requirement in the prompt's Priority Order.

**M2 — Tone Alignment** (LLM-as-judge, dual; example-focus: *Tone Accuracy*).
Two judges each rate, on a **strict 1–10 rubric**, how precisely the email's greeting, word
choice, pacing, and sign-off embody the requested tone (9–10 flawless; 6–7 minor slips;
3–5 off register; 1–2 wrong tone). Each rating is normalized as `(score − 1) / 9`; the
metric is the mean across both judges. The wide, anchored scale was chosen after a 1–5
scale saturated at the ceiling (see §4).

**M3 — Conciseness & Structure** (deterministic Python; example-focus: *Conciseness /
Format Adherence*).
Mean of four equally-weighted checks: (1) a non-empty **subject** line; (2) a **greeting**
opens the body; (3) a **sign-off** closes the body; (4) a **density** score for body
length — 1.0 inside the 50–150-word target band, decaying linearly to 0.0 at ≤20 words
(too thin) or ≥200 words (the hard ceiling). Greeting/sign-off are detected by structural
role (a short salutation line; a short valediction line ending in a comma), not a fixed
phrase list, so valid-but-unlisted openings/closings are not penalized. No LLM is used, so
this metric is fully reproducible and unit-tested (`tests/test_metrics.py`).

### 3.2 Why this design is defensible

- **Reference-grounded data.** Each scenario ships a hand-written human reference email
  (`data/scenarios.json`); the metrics check against the explicit key facts and requested
  tone, and the references serve as a sanity ceiling (all 10 score M3 = 1.0).
- **Bias control for LLM-as-judge.** M1/M2 run the *same* rubric through judges from *two
  different providers* and average. Every email is scored by the other provider's judge as
  well as its own, so provider **self-preference** is diluted rather than baked in.
- **A deterministic anchor.** M3 uses no model at all, giving one metric that is exactly
  reproducible and immune to judge drift.
- **Prompt aligned to metrics.** The prompt's self-critique Quality Checks mirror the
  metrics (coverage, tone, structure, density), so the model optimizes for what we measure.

---

## 4. Raw Evaluation Data

Generated by `src/email_assistant/evaluate.py` (`make eval`) into
`results/scores.csv` (flat table) and `results/results.json` (full detail: metric
definitions, generated emails, and per-judge breakdowns). Both models were run on the
**same 10 scenarios with the same prompt**; Gemini was run with `thinking_level="minimal"`
so both rely solely on the prompt's CoT (parity with Claude, which uses no extended
thinking). Edge-case scenarios (`contradictory-pricing`, `role-elimination`, and
`final-interview-invite`, which supplies no date) stress no-fabrication discipline; the two
scenarios that mirrored the prompt's own few-shot examples were excluded.

### 4.1 Per-scenario scores

**Claude Opus 4.8**

| Scenario | Tone (requested) | Fact Cov. | Tone | Struct. | Overall |
|---|---|---|---|---|---|
| project-delay | apologetic but confident | 1.00 | 0.889 | 1.00 | 0.963 |
| rfp-detailed | formal | 1.00 | 0.944 | 1.00 | 0.981 |
| outage-postmortem | transparent and professional | 1.00 | 0.944 | 1.00 | 0.981 |
| contradictory-pricing | professional and clear | 1.00 | 0.944 | 1.00 | 0.981 |
| role-elimination | empathetic but clear | 1.00 | 0.944 | 1.00 | 0.981 |
| team-offsite-invite | casual and upbeat | 1.00 | 0.944 | 1.00 | 0.981 |
| support-escalation | firm and urgent | 1.00 | 0.889 | 1.00 | 0.963 |
| final-interview-invite | warm and professional | 1.00 | 0.944 | 1.00 | 0.981 |
| partnership-pitch | confident and persuasive | 1.00 | 0.833 | 1.00 | 0.944 |
| expense-policy-update | clear and direct | 1.00 | 0.889 | 1.00 | 0.963 |
| **Average** | | **1.000** | **0.917** | **1.000** | **0.972** |

**Gemini 3.5 Flash**

| Scenario | Tone (requested) | Fact Cov. | Tone | Struct. | Overall |
|---|---|---|---|---|---|
| project-delay | apologetic but confident | 1.00 | 0.889 | 1.00 | 0.963 |
| rfp-detailed | formal | 1.00 | 0.944 | 1.00 | 0.981 |
| outage-postmortem | transparent and professional | 1.00 | 0.944 | 1.00 | 0.981 |
| contradictory-pricing | professional and clear | 1.00 | 0.944 | 1.00 | 0.981 |
| role-elimination | empathetic but clear | 1.00 | 0.889 | 1.00 | 0.963 |
| team-offsite-invite | casual and upbeat | 1.00 | 0.722 | 1.00 | 0.907 |
| support-escalation | firm and urgent | 1.00 | 0.833 | 1.00 | 0.944 |
| final-interview-invite | warm and professional | 1.00 | 0.944 | 1.00 | 0.981 |
| partnership-pitch | confident and persuasive | 1.00 | 0.778 | 1.00 | 0.926 |
| expense-policy-update | clear and direct | 1.00 | 0.889 | 1.00 | 0.963 |
| **Average** | | **1.000** | **0.878** | **1.000** | **0.959** |

### 4.2 Summary

| Model | Fact Coverage | Tone Alignment | Conciseness & Structure | **Overall** |
|---|---|---|---|---|
| **Claude Opus 4.8** | 1.000 | **0.917** | 1.000 | **0.972** |
| **Gemini 3.5 Flash** | 1.000 | **0.878** | 1.000 | **0.959** |

---

## 5. Model Comparison & Analysis

**Which performed better?** **Claude Opus 4.8** (overall **0.972** vs **0.959**). Both
models are tied and perfect on **Fact Coverage (1.000)** and **Conciseness & Structure
(1.000)** — they reliably ground every key fact (including the contradictory/missing-info
edge cases, with no fabrication) and produce well-formed emails. The entire difference
comes from **Tone Alignment (0.917 vs 0.878)**.

**Biggest failure mode of the lower performer (Gemini 3.5 Flash):** *flattening
distinctive tones toward a generic professional register.* The per-scenario data isolates
it cleanly — Gemini **ties Claude on every standard business register** (formal,
transparent/professional, warm/professional, clear/direct, apologetic) but **trails on the
most characterful tones**:

| Requested tone | Claude | Gemini | Gap |
|---|---|---|---|
| casual and upbeat | 0.944 | **0.722** | **−0.222** |
| confident and persuasive | 0.833 | 0.778 | −0.056 |
| firm and urgent | 0.889 | 0.833 | −0.056 |
| empathetic but clear | 0.944 | 0.889 | −0.056 |

The standout is *casual and upbeat* (`team-offsite-invite`): Gemini defaults to a correct
but stiff professional voice (e.g. dropping contractions, formal phrasing) where the brief
calls for warmth and energy. Its competence is real but **narrower** — excellent at neutral
business correspondence, weaker when the tone is the point.

**Production recommendation.** For a **general-purpose** assistant — where the whole reason
*Tone* is an input is to span casual, persuasive, empathetic, and urgent registers — I
recommend **Claude Opus 4.8**: it leads exactly on the dimension that differentiates, with
no cost on facts or structure. For a **cost-sensitive, formal-only** deployment (e.g.
templated business/transactional mail), **Gemini 3.5 Flash** is a strong, cheaper choice —
it showed *zero* measured loss on facts, structure, and standard professional tone. A
sensible hybrid is to route by requested tone: Flash for standard registers, Opus when the
brief demands a distinctive voice.

**Limitations (read the result honestly).** This is a single run of n=10; LLM-as-judge
scores are non-deterministic and the gap, while consistent in direction, is small and not
tested for significance. Fact Coverage and Structure sit at the ceiling, so discrimination
lives almost entirely in Tone — a strength for *this* comparison but a sign the suite would
need harder fact/structure stressors to separate weaker models. Finally, a judge-
calibration asymmetry was observed (Gemini-as-judge is lenient, often 10/10; Claude-as-
judge is stricter) — the dual-provider averaging mitigates it, and because both models are
scored by the *same* judge pair, the comparison remains fair.
