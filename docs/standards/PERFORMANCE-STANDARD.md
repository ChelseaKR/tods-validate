# Performance Standard

The canonical performance-enforcement mechanics for the portfolio. `QUALITY-AND-METRICS-STANDARD.md §2` owns the *targets* (they are restated below only as the interface); this document owns *how those targets become merge-blocking gates*: the k6 latency check, the Lighthouse-CI score + bundle budgets, the committed baseline artifact, and the ">10% regression fails" rule. It exists because performance was the only Definition-of-Done stage whose gates were two prose lines with no reference implementation — every repo wiring it would have reinvented it.

Repos override the *values* (a static personal site has no LLM routes; a RAG service has no bundle) but not the *structure*: the same script shape, the same config shape, the same baseline schema, the same update ritual.

**Adoption is two files.** Copy `perf/k6-smoke.js` and `perf/lighthouserc.json`, edit the marked values, run them once, commit the resulting `perf/baseline.json`. That is the entire onboarding cost; see §5.

---

## 0. Scope and relationship to sibling standards

| Concern | Owner | This document's interface to it |
|---|---|---|
| Target *values* (p95, Lighthouse score, bundle size) | `QUALITY-AND-METRICS-STANDARD.md §2` | Restated in §1 verbatim; a value change happens there, not here |
| DoD performance stage ("k6/Lighthouse budgets, ≤10% regress") | `QUALITY-AND-METRICS-STANDARD.md` DoD stage 10 | Implemented here — the stage cites this standard |
| Core Web Vitals lab gate + field RUM | `OBSERVABILITY-STANDARD.md §8` | **One envelope.** The Lighthouse-CI run defined here is the same run that asserts the §8 CWV lab budgets — one `lighthouserc.json` per repo, never two configs with drifting numbers. Field p75 RUM stays owned by §8; it is a tripwire review signal, not a merge gate |
| SLO latency alerting (prod, rolling window) | `OBSERVABILITY-STANDARD.md §4` | Same numeric budgets; SLOs alert on prod, this standard blocks merges pre-prod |

**Applicability:** hosted services and frontends (DoD stage 10). Pure libraries/CLIs with no hosted route and no shipped HTML declare **N/A-with-reason** in their `ROADMAP.md` per the scoping rule in `QUALITY-AND-METRICS-STANDARD.md` — a silent skip is a defect. A library with a documented hot path should still consider a benchmark regression check (e.g. `pytest-benchmark`), recorded as its project-specific value.

---

## 1. Budgets (the interface, from QUALITY-AND-METRICS §2)

| Budget | Value | Applies to | Asserted by |
|---|---|---|---|
| p95 server response (non-LLM routes) | < 500 ms | hosted services | k6 `http_req_duration` threshold |
| p95 first-token (LLM routes) | < 1.5 s | LLM/RAG services | k6 custom `Trend` on streaming first byte |
| p95 full response (LLM routes) | < 6 s | LLM/RAG services | k6 `http_req_duration` on the LLM route tag |
| Lighthouse Performance score | ≥ 90 (0.9) | frontends | Lighthouse-CI `categories:performance` assertion |
| Critical-path JS | < 200 KB gzip (204 800 B transfer) | frontends | Lighthouse-CI `resource-summary:script:size` assertion |
| Regression vs committed baseline | ≤ 10% on every baseline metric | everything above | baseline comparison (§2) |

Both layers gate independently: an absolute budget miss fails even with a stale-slow baseline, and a >10% regression fails even while still inside the absolute budget. The ratchet only moves one way without sign-off.

---

## 2. The committed baseline — `perf/baseline.json`

The ">10% regression fails" rule is meaningless without a defined comparand. The comparand is **`perf/baseline.json`, committed at the repo root's `perf/` dir** — not a dashboard, not the previous CI run, not memory. Its required schema is:

- `meta` — provenance: the `commit` the numbers were measured at, `date`, `environment`, and pinned `tools` versions (k6, Lighthouse-CI, Node). Numbers without provenance cannot be re-verified and do not count.
- `metrics` — flat map of measured values: `p95_ms`, `llm_first_token_ms`, `llm_full_response_ms`, `lighthouse_performance`, `js_kb_gzip`. Inapplicable metrics are `null` (the declared N/A, never silently absent).
- `direction` — per-metric `lower_is_better` / `higher_is_better`, so the comparison is mechanical and direction-aware.

**The regression rule, precisely:** for each non-null metric, CI compares the current run against `baseline.json`. A run **fails** when any metric is more than 10% worse in its declared direction: `current > baseline × 1.10` for `lower_is_better`, `current < baseline × 0.90` for `higher_is_better`. Comparison is per-metric; one regressed metric fails the run.

### Baseline update ritual (who / when / how)

| Case | Who | How |
|---|---|---|
| **Improvement** (metrics got better) | PR author | Update `baseline.json` in the same PR that improved them — ratchet forward. No sign-off needed. |
| **Intentional regression** (a feature is worth the cost) | PR author + **product owner** | Product-owner sign-off recorded **in the PR** (review approval on a PR that names the regression, or an explicit sign-off comment), and `baseline.json` updated **in the same PR** as the regressing change. The diff is the audit trail. |
| **Unintentional regression** | — | Not an update case. Fix the code; the baseline does not move to make red turn green. |
| **Environment/tool change** (new CI runner class, k6/Lighthouse major) | PR author | Re-measure, update `meta.tools`/`meta.environment` and metrics together in one PR titled as a re-baseline, with before/after numbers in the description. |

A baseline edit outside these cases — or in a separate "fix CI" PR after the regressing merge — is a defect. Since the baseline is a committed file, branch protection and CODEOWNERS give the sign-off teeth: route `perf/baseline.json` to code owners. The normal profile requires an eligible reviewer; bounded solo mode uses the authenticated owner disposition in `CODE-QUALITY-STANDARD.md` §7.1 without calling it independent review.

---

## 3. Gates

| Control | Target | Measured by | Gate |
|---|---|---|---|
| k6 latency thresholds [PERF-01] | §1 p95 budgets, per route class | `k6 run perf/k6-smoke.js` in CI against the preview/staging URL; `thresholds` block fails the process | AUTO-GATE |
| Lighthouse score + bundle budgets [PERF-02] | Perf ≥ 0.9; script transfer < 204 800 B | `lhci autorun` with committed `perf/lighthouserc.json` | AUTO-GATE |
| Baseline regression check [PERF-03] | ≤ 10% vs `perf/baseline.json`, direction-aware | comparison step in CI (jq/python one-liner or lhci assertion), per §2 | AUTO-GATE |
| Baseline currency [PERF-04] | `baseline.json` updated in any PR touching latency-sensitive paths | PR checklist + diff inspection | REVIEW-GATE |
| Intentional-regression sign-off [PERF-05] | product-owner approval recorded in the regressing PR | CODEOWNERS route on `perf/baseline.json` | REVIEW-GATE |

No `|| true`, no `continue-on-error`, per the portfolio enforcement model. A perf job that cannot yet run against a real URL (no preview environment) is declared N/A-with-reason until the environment exists — not wired in advisory mode.

---

## 4. Reference file contract — `perf/`

| File | What it is |
|---|---|
| `perf/k6-smoke.js` | k6 script: `BASE_URL`/`VUS`/`DURATION` via `__ENV`, thresholds block asserting `p(95)<500`, and per-route checks |
| `perf/lighthouserc.json` | Lighthouse-CI config: performance ≥ 0.9 assertion, script resource budget 204 800 B, and the collect URL |
| `perf/baseline.json` | The baseline schema and repository-specific measured values |
| `perf/README.md` | Repository-local field documentation and adoption instructions |

---

## 5. Adoption recipe (the excellence bar: two files)

1. Create `perf/k6-smoke.js` and `perf/lighthouserc.json` in your repo's `perf/` from the contract above.
2. Edit the `// EDIT:` markers: `BASE_URL` default, the `ROUTES` list, the collect URL, and (LLM repos) enable the first-token trend.
3. Run both once against a representative environment; write the measured numbers into a new `perf/baseline.json` (copy the schema file, replace values, fill `meta`).
4. Commit all three; wire the two commands + the comparison step as required status checks.

---

Last verified: 2026-07-02 · Recheck cadence: per k6 or Lighthouse-CI major release, Core Web Vitals threshold revision, or any change to the §2 targets in `QUALITY-AND-METRICS-STANDARD.md` — and at minimum annually. Confirm tool versions at build time.
