# AI-Development Measurement Standard

Last verified: 2026-07-11 · Recheck cadence: quarterly (with the DORA review)
>
> Defines **how to measure portfolio development when AI tools participate** —
> Claude Code and other agentic tooling — as distinct from measuring the AI *products* themselves
> (that is `AI-EVALUATION-STANDARD.md`). Product-AI evaluation and observability
> are the companion track. Solo-adapted projects use telemetry instead of team
> sentiment surveys.

## Sibling standards (reference, don't repeat)
- `QUALITY-AND-METRICS-STANDARD.md` — DORA five, the metrics ledger, the enforcement model.
- `OBSERVABILITY-STANDARD.md` — OTel; the GenAI-semconv section for AI products.
- `AI-EVALUATION-STANDARD.md` — Track B: the AI systems' own evals + the online loop.

## 0. The core principle — outcomes over activity
AI is an **amplifier of the surrounding system**, not an independent source of
gains (DORA 2025). So this standard measures the *system* (delivery discipline,
small batches, quality debt, cost) — not tool-usage vanity counters.

- **Diagnostic signals** explain *how* work changed: sessions, tokens, lines of
  code, acceptance rate, %-AI-generated, cost. Track them; **never gate on them**.
- **Outcome metrics** say whether results improved: lead time, change-fail rate,
  defect escape, review coverage, cost per shipped change. These are what gate,
  once a baseline exists.

Every throughput metric ships with a **quality-debt counterweight** — velocity
gains that degrade quality reduce long-term velocity (DORA 2025; GitClear; Faros).

## 1. The gate states — AUTO-GATE, REVIEW-GATE, BASELINE (this standard adds the third)
`QUALITY-AND-METRICS-STANDARD.md` allows only AUTO-GATE or REVIEW-GATE ("never
aspirational"). Track A metrics are new and gaming-prone, so this standard adds a
third, **time-boxed** state so nothing is aspirational:

| State | Meaning |
|---|---|
| **AUTO-GATE** [ADM-11] | merge-blocking in CI |
| **REVIEW-GATE** [ADM-11] | committed, dated artifact reviewed on a cadence |
| **BASELINE** | observe-only, **with a dated graduation-decision date** (default: +1 quarter). At that date the metric graduates to AUTO/REVIEW-GATE or is retired — it may not sit in BASELINE indefinitely. |

A BASELINE row without a graduation date is a conformance failure, same as an
aspirational row.

## 2. The never-gate list (evidence-backed)
These are **diagnostic only** — track, never gate, never rank a person by:

| Metric | Why not |
|---|---|
| AI-suggestion **acceptance rate** | Correlates with perceived productivity at only Pearson r≈0.24; confounded by time-of-week/language; saturates 20%→60% as adoption grows while quality degrades. |
| **Lines of code** / diff size | Classic vanity metric; AI inflates it. |
| **%-AI-generated code** | An adoption diagnostic, not an outcome. |
| **PR merge rate** | High rate can mean rubber-stamped machine code, not health (DX). Valid as a *system* flow signal, noisy for individuals. |
| **Self-reported speedup** | METR RCT: devs felt +20% while measured −19%. Perception ≠ outcome. |

## 3. Track A metric set (per repo + portfolio rollup)
Mined automatically by `automation/delivery_metrics.py` and
`automation/ai_usage_report.py`; emitted to `metrics/PORTFOLIO-METRICS.md` and
`metrics/AI-USAGE.md` on the weekly launchd cadence.

### 3.1 Delivery (DORA five — the implementation of QUALITY-AND-METRICS §DORA)
| Metric [ADM-01..05] | Measured by | State |
|---|---|---|
| Deployment frequency | releases (or merges-to-main fallback) / week | BASELINE → REVIEW quarterly |
| Change lead time (p50/p90) | PR createdAt → mergedAt | BASELINE → REVIEW quarterly |
| Change-fail rate | reverts / changes shipped (proxy) | BASELINE → REVIEW quarterly |
| Failed-deploy recovery time | `incident`-labelled issue open→close | REVIEW quarterly (N/A until labels adopted) |
| Rework rate | churn-within-14d (below) | BASELINE → REVIEW quarterly |

### 3.2 Quality-debt leading indicators (the counterweights)
| Metric [ADM-06..10] | Definition | State |
|---|---|---|
| Churn ratio | deletions / additions over window (Faros def) | BASELINE |
| Short-term churn (14d) | share of file-edits re-touching code <14 days old (GitClear) | BASELINE |
| **Unreviewed-merge rate** | PRs merged with zero review (human or agentic) | BASELINE → **AUTO-GATE candidate 2026-10** (esp. AI-authored PRs) |
| Revert rate | revert commits / merges | BASELINE |
| Code duplication | `jscpd` % (opt-in run) | BASELINE → AUTO-GATE candidate (ceiling) |

### 3.3 AI-tool usage (diagnostic; Claude Code native OTel + ccusage)
Cost, tokens, per-model mix, cache-hit rate, accept/reject decisions, active
time, PR/commit/LOC counts. **All diagnostic — none gate.** Cost is an estimate
(Claude Code's own caveat), reconciled against the provider console.

## 4. Telemetry & privacy (AUTO for the config; REVIEW for the audit)
- Claude Code OTel telemetry is **local-only**: exports to a localhost collector
  (`automation/telemetry/`); nothing leaves the machine.
- **Content is redacted by default** (Claude Code default + OTel GenAI default).
  Prompt/response content capture is a per-repo, documented opt-in — default off.
- Prompt IDs are kept out of metrics (cardinality); session-id inclusion is the
  only identifier, toggleable.
- The enabling `env` block lives in `~/.claude/settings.json` (not committed).

## 5. AI-segmented DORA (closes the DORA 2025 capabilities checklist item 7)
Claude-Code-authored commits/PRs carry a trailer (`Co-Authored-By: Claude …`);
`delivery_metrics.py` can segment DORA and quality-debt metrics by
AI-authored vs human-authored using that trailer, so "AI-generated code
segmented in DORA metrics" becomes computable rather than aspirational.

## 6. DORA AI Capabilities — quarterly self-assessment (REVIEW-GATE, solo-adapted)
For a qualifying solo-maintained repository or portfolio rollup, team-survey
frameworks such as SPACE/DevEx are not representative. The **DORA AI
Capabilities Model** (2025-11-25) is behavior-anchored and self-assessable. Each
quarter, the qualifying scope answers the seven published capabilities and
commits the result to `metrics/AI-CAPABILITIES-<year>-Q<n>.md`:

1. Clear, communicated AI stance · 2. Healthy data ecosystems · 3. AI-accessible
internal data · 4. **Strong version control** (including AI prompts, commands,
and skills) · 5.
**Working in small batches** (measured by changes-per-deploy, lines-per-commit
from §3.1 — telemetry substitutes for the survey item) · 6. User-centric focus ·
7. Quality internal platform.

## 7. Anti-patterns (documented, to be avoided)
- **Checkpoint-only measurement** — metrics that change nothing. Every quarterly
  review must produce at least one action or an explicit "no action, because…".
- **Gaming** — optimizing a diagnostic (LOC, acceptance) instead of an outcome
  (malicious compliance, DX). The never-gate list (§2) is the guard.
- **Over-gating small projects** — deterministic/weekend repos declare N/A; do
  not impose the full set where it doesn't earn its keep.
- **Survey fatigue** — there are no surveys here by design.
- **Measuring activity instead of outcomes** — §0.

## 8. Scope & N/A declaration
Every repo carries one line in its `docs/ROADMAP.md` metrics ledger:
`AI-DEV-MEASUREMENT: APPLIES` or `N/A — <reason, dated>`. Track A delivery and
quality-debt metrics apply whenever AI tools participate in development; the
AI-tool cost/usage rollup is portfolio-level rather than a person-ranking
metric. A repository with no AI-assisted development may declare N/A with dated
evidence and a re-entry trigger.

## What gets committed
- `metrics/PORTFOLIO-METRICS.md` + `metrics/AI-USAGE.md` (weekly, regenerated).
- `metrics/AI-CAPABILITIES-<year>-Q<n>.md` (quarterly REVIEW-GATE).
- The BASELINE graduation decisions (dated) in this file's changelog when they land.
