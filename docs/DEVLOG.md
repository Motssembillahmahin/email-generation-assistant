# Development Log

A running record of how the Email Generation Assistant was built — decisions, rationale,
and what each step verified. Complements `report/REPORT.md` (the graded deliverable) by
capturing the *engineering* narrative. Newest entries at the bottom.

---

## Baseline (pre-existing commits)

Three commits scaffolded the project before this log began:

- `chore:` project scaffolding — `uv` + `pyproject.toml`, `Makefile`, package skeleton,
  `.env.example`, ruff config, pytest setup.
- `feat:` advanced prompt template — `src/email_assistant/prompts.py`: Role-Play +
  Chain-of-Thought + bounded self-refinement, in 11 gradeable sections, with a
  `<thinking>` / `<email>` output contract.
- `feat:` model config, email generator, demo CLI — `config.py` (provider-agnostic
  `generate()` over Anthropic + Google SDKs), `generator.py` (`parse_email` + 4 offline
  parser tests), `cli.py` (`make generate`).

`report/REPORT.md` sections 1–2 (overview + prompt engineering) were written; sections
3–5 left as stubs to fill from real evaluation data.

---

## Planning session — scope of remaining work

Reviewed the assessment PDF against the codebase and locked two decisions before coding:

1. **Comparison axis (§3): two models** — Claude Opus 4.8 vs Gemini 3.5 Flash, same
   prompt. Chosen over "advanced vs naive prompt on one model" for a stronger,
   cross-provider comparison.
2. **Three custom metrics:** Fact Coverage (LLM-judge, dual), Tone Alignment (LLM-judge,
   dual), Conciseness & Structure (deterministic). One per assessment example-focus area
   (fact recall / tone accuracy / conciseness).

Verified model IDs against current provider docs (per CLAUDE.md): `claude-opus-4-8` and
`gemini-3.5-flash` are both current, and `config.py`'s SDK calls match. No changes needed.

Remaining build order: scenarios → metrics → eval harness → results → report.

---

## Step 1 — `data/scenarios.json` (10 scenarios + reference emails)

Created 10 scenarios, each a distinct intent paired with a **distinct tone** (all 10 tones
differ), 3 concrete key facts apiece, and a hand-written human reference email.

Design choices:

- **Concrete, checkable facts** (dates, dollar amounts, invoice #, percentages) so the
  Fact Coverage judge has unambiguous targets.
- **Reference bodies all land in the 82–100 word band** — inside the prompt's 50–150
  target — so the gold standard is itself "ideal" under the M3 metric.
- **`[Name]` / `[Your name]` placeholders** match the prompt's convention (scenarios give
  no real names), keeping generated-vs-reference comparison fair.
- **Known risk, flagged:** two scenarios (`demo-followup`, `service-outage`) mirror the
  examples baked into the prompt. Kept as a self-reproduction sanity check; to be noted in
  the report, with the option to swap one out.

Verified: JSON parses, 10 unique ids, all 10 tones distinct, every scenario has facts +
a `Subject:`-prefixed reference, reference bodies ~82–100 words.

---

## Step 2 — `src/email_assistant/metrics.py` (3 custom metrics)

Implemented the three metrics, each returning a `MetricResult(name, score∈[0,1], detail)`
with a transparent breakdown, plus a `METRIC_DEFINITIONS` map surfaced into the report
(assessment §2C requires definitions in the output).

- **M1 Fact Coverage** — for each key fact, two judges (Claude + Gemini) decide
  present-and-accurate; per-judge score = covered/total; metric = mean of the two.
- **M2 Tone Alignment** — two judges rate 1–5 against the requested tone; normalized
  `(score-1)/4`; metric = mean of the two.
- **M3 Conciseness & Structure** — deterministic; mean of four equal checks: subject
  present, greeting present, sign-off present, and a density score (1.0 in [50,150] words,
  linear decay to 0 at ≤20 or ≥200).

**Bias control:** the two LLM-judge metrics run the *same* rubric through judges from
*different providers* and average. Every email is scored by the other provider's judge as
well as its own, so provider self-preference is diluted rather than baked in. M3 is
provider-free.

Verified (no API calls): all 10 reference emails score M3 = 1.00; density curve checks out
(10w→0.0, 40w→0.67, 100w→1.0, 175w→0.5, 210w→0.0); `ruff check` clean. M1/M2 require live
API calls — exercised when the eval harness runs.

---

## Step 3 — `src/email_assistant/evaluate.py` (evaluation harness)

Implemented the harness: for each (model, scenario) it generates an email, scores it on
all three metrics, and writes two artifacts to `results/`:

- `scores.csv` — flat per-(model, scenario) rows (three metric scores + overall), plus a
  trailing `AVERAGE` row per model.
- `results.json` — metric definitions, the judge list, full per-scenario detail (generated
  email + per-judge breakdowns), and per-model averages.

`overall` per scenario = mean of the three metric scores; per-model `overall` = mean of
those. Run via `make eval`; makes live API calls to both providers.

Verified the non-API plumbing with a stubbed run (generation + the two LLM-judge metrics
stubbed, `conciseness_structure` real): aggregation, CSV layout, and JSON shape all
correct; `ruff check` clean.

**Blocker for the live run:** no `.env` present — both `ANTHROPIC_API_KEY` and
`GEMINI_API_KEY` are unset. The real 10×2 evaluation (and the committed `results/`) is
pending those keys.

---

## Step 3b — first live run + fixing Gemini's reasoning regime

Set up `.env` from the provided keys (gitignored; verified with `git check-ignore`).
Smoke-tested both providers: Claude returned text immediately; **Gemini 3.5 Flash returned
empty** at a small token budget because its *internal* thinking consumed the budget.

Fix (config.py): set `thinking_config=ThinkingConfig(thinking_level="minimal")` for Gemini.
Rationale — Claude is called without extended thinking, so for a fair, like-for-like
comparison both models should rely solely on the prompt's `<thinking>` CoT, not provider-
internal reasoning. (`thinking_budget` is replaced by `thinking_level` on 3.5 Flash;
"minimal" is the closest to off — verified against current Google docs.) This also stops
the budget being spent on hidden reasoning and truncating the email/judge JSON.

First real run revealed a **ceiling effect**: every metric ≈ 1.0 for both models. Reading
the outputs confirmed it was genuine quality (the emails were excellent), not lenient
judging — the tasks were simply too easy and the rubrics too coarse to discriminate.

## Step 3c — harder scenarios + sharper rubrics (the metrics, iterated)

Acted on the ceiling effect (chosen direction: make it discriminate):

- **Rewrote `data/scenarios.json`** — 10 demanding scenarios, 4–5 concrete facts each,
  harder/“characterful” tones, and three edge cases that stress no-fabrication discipline
  (`contradictory-pricing`, `role-elimination`, and `final-interview-invite` which supplies
  no date). Dropping the old set also removed the two scenarios that mirrored the prompt's
  baked-in examples (the “teaching to the test” risk flagged in Step 1).
- **Sharpened the judges** — Fact Coverage now uses 3-level partial credit (full=1.0 /
  partial=0.5 / none=0.0) so subtle distortions register; Tone moved to a strict 1–10 scale
  with an explicit deduction rubric (normalized `(score-1)/9`).

Re-run surfaced two *structure* deductions — which on inspection were **metric artifacts,
not email defects**: the deterministic structure check used a phrase whitelist and so
missed a valid sign-off ("With sincere appreciation,") and a valid greeting ("To the
Support Management Team,"). Fixed by detecting greeting/sign-off by **structural role** (a
short salutation line at the top; a short valediction line ending in a comma near the end)
instead of enumerating phrases — integrity over manufactured spread. Verified offline on
the two emails and all 10 references before re-running.

**Final results** (`results/scores.csv`, `results/results.json`):

| Model | Fact Coverage | Tone | Structure | Overall |
|---|---|---|---|---|
| Claude Opus 4.8  | 1.000 | 0.917 | 1.000 | **0.972** |
| Gemini 3.5 Flash | 1.000 | 0.878 | 1.000 | **0.959** |

Findings for the report:
- Facts + structure saturate at 1.0 — both models reliably ground every fact and produce
  well-formed emails; these are *not* differentiators for two strong models (honest result).
- **Tone is the discriminator.** Gemini's lowest tone scores are on the most distinctive
  registers — `team-offsite-invite` (casual/upbeat, 0.72), `partnership-pitch`
  (confident/persuasive, 0.78), `support-escalation` (firm/urgent, 0.83). Its failure mode
  is **flattening characterful tones toward a generic professional register**; it nails
  standard formal/professional tones.
- **Judge-calibration note:** Gemini-as-judge is lenient (often 10/10), Claude-as-judge is
  stricter — uniformly across both models' emails. The dual-judge averaging balances this,
  and both models are scored by the same judge pair, so the comparison stays fair.

---

## Step 4 — `tests/test_metrics.py` (metric unit tests, no API)

Added 32 tests for the metrics (36 total with the existing parser tests). The deterministic
metric is tested directly; the two LLM-judge metrics have their deterministic parts tested
by monkeypatching the judge call:

- M3: density band (full inside [50,150]; zero at/beyond 20 and 200; linear decay), greeting
  and sign-off detection including the structural-role cases that broke the old whitelist
  ("To the Support Management Team,", "With sincere appreciation,"), and full-metric scoring
  (well-formed = 1.0; missing subject = 0.75; over-long body → density 0).
- M1: 3-level partial-credit mapping, missing-verdict-counts-zero, empty-facts vacuous 1.0.
- M2: 1-10 normalization, out-of-range clamping, dual-judge averaging.
- `_judge_json`: extraction from fenced output; raises when no JSON object is present.

Verified: `make test` → 36 passed in ~0.05s, no network; `ruff check` clean.

---

## Step 5 — Final report + doc reconciliation

Filled `report/REPORT.md` from the committed results:

- §2.2 — added the **Few-Shot** row to the technique table (the prompt genuinely ships two
  worked examples; the table had omitted it).
- §2.5 — reproduced the **full prompt template verbatim** from `prompts.py` (deliverable
  requirement), with a note that the two example-mirroring scenarios were excluded.
- §3 — the **three metric definitions + logic** and the defensibility rationale (reference
  grounding, dual cross-provider judges for self-preference, deterministic anchor, prompt↔
  metric alignment).
- §4 — **raw per-scenario tables** for both models + the summary, with the run's fairness
  conditions stated (same prompt; Gemini `thinking_level="minimal"`; edge cases; examples
  excluded).
- §5 — the **comparative analysis**: Claude wins overall (0.972 vs 0.959); the difference is
  entirely Tone (facts + structure tie at 1.0); Gemini's failure mode is flattening
  distinctive tones (biggest gap: casual/upbeat −0.222); production recommendation (Opus for
  general-purpose, Flash for cost-sensitive formal-only, or route by tone); and an honest
  limitations paragraph (n=10, single run, ceiling on facts/structure, judge-calibration
  asymmetry mitigated by dual judging).

Also reconciled the README (technique wording now matches REPORT; removed the "scaffolding"
status; pointed to results/ and the report).

**Status: all assessment deliverables complete** — working assistant, advanced documented
prompt, 10 scenarios + references, 3 custom metrics, structured results (CSV+JSON),
two-model comparison, and the final report. Remaining is the user's call on committing and
publishing the GitHub repo (intentionally left uncommitted per instruction).

---

## Step 6 — module separation (cohesion refactor)

Code-review feedback: `config.py` was doing too much (env loading + model registry +
constants + provider access). Split by responsibility, single source of truth per concern:

- **`vars.py`** — constants/knobs + paths (`DEFAULT_MAX_TOKENS`, `JUDGE_MODELS`,
  `JUDGE_MAX_TOKENS`, the density-band constants, and `SCENARIOS_PATH`/`RESULTS_DIR`).
- **`models.py`** — `ModelSpec` + the `MODELS` registry (model IDs).
- **`config.py`** — now the settings + provider-access layer only: loads `.env` once and
  exposes a `Settings`/`get_settings()`; clients now read keys from settings and pass them
  explicitly (`Anthropic(api_key=...)`, `genai.Client(api_key=...)`), so the environment is
  read in exactly one place. `generate()` stays here as the provider wrapper.

Callers updated to import `MODELS` from `models`, constants/paths from `vars`. Docs brought
back in sync: CLAUDE.md ("Model IDs live in `models.py`…" + layout), README (layout + a
config bullet). Note: `vars.py` shadows the `vars()` builtin, so it is only ever imported
via `from email_assistant.vars import ...`, never `import ... as vars`.

Verified: import smoke test resolves all modules; settings load both keys; live generation
works for both providers through the explicit-key client path; `make test` → 36 passed;
`ruff check` clean.
- Step 5 — fill `report/REPORT.md` §3–5 from real data; reconcile README/REPORT technique
  wording ("Few-Shot" vs "Refinement").
