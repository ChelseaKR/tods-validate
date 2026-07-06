# Quality & Metrics Standard

This is the canonical definition of the quality attributes every project targets and the mechanism by which their metrics are **enforced** rather than merely measured. It is the **spine** of `STANDARDS/`: it owns the vocabulary (ISO/IEC 25010:2023), the delivery-health backbone (DORA), and the merge-gate model. The cross-cutting depth for each domain lives in a dedicated sibling standard — this document **points to** them and does not restate them.

Projects override the *values* (a hobby logger needs less than a public benefits tool) but not the *structure*.

> **On "100% enforcement."** A metric is enforced when failing it **blocks the merge** — not when a dashboard shows it red after the fact. The honest ceiling: everything mechanically checkable is a hard CI gate; everything requiring judgment (genuine bias, accessibility-of-experience, ethical edge cases) is a *required human sign-off gate* with a checklist and a committed artifact. We enforce 100% of the checkable set automatically and 100% of the judgment set via blocking review. We never pretend a judgment call is fully automatable, and there is **no third "aspirational" category**.

## Sibling standards (reference, don't repeat)

This document is the index. Each row below is enforced **in** the named standard; the cell here states only the one-line interface this spine depends on.

| Domain | Owning standard | Interface this spine depends on |
|--------|-----------------|---------------------------------|
| Code quality / toolchain | `CODE-QUALITY-STANDARD.md` | ruff ≥0.15.x, mypy `--strict`, branch coverage ≥85% (libs ≥90%), single `pyproject.toml`, `uv sync --frozen`, `make verify` byte-equal to CI |
| CI/CD hardening | `CI-CD-STANDARD.md` | top-level `permissions: contents: read`, OIDC-only cloud creds, `zizmor` on workflow PRs, concurrency groups, committed CODEOWNERS + branch ruleset |
| Security & supply chain | `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | ASVS 5.0 L2; SHA-pinned actions; Semgrep/CodeQL/gitleaks/pip-audit/Trivy blocking on HIGH+CRITICAL; SBOM + cosign + SLSA L2 |
| Release & versioning | `RELEASE-AND-VERSIONING-STANDARD.md` | SemVer 2.0.0; signed tags; CHANGELOG entry per release; tag-triggered `make verify` re-run; Trusted Publishing (OIDC, no stored tokens); version-consistency gate |
| Observability | `OBSERVABILITY-STANDARD.md` | structured JSON logs, OTel spans, `/livez` + `/readyz`, SLOs + burn-rate alerts (tiered by deployment shape) |
| Accessibility | `ACCESSIBILITY-STANDARD.md` | WCAG 2.2 AA floor; axe zero critical/serious/moderate; pa11y **blocking**; screen-reader walkthrough + ACR per release |
| Internationalization | `INTERNATIONALIZATION-STANDARD.md` | portable catalogs (gettext `.po` / MF2-ICU); EN/ES key-parity + placeholder-parity + pseudolocale gates |
| AI evaluation | `AI-EVALUATION-STANDARD.md` | RAGAS faithfulness ≥0.80; hallucination ≤5%; Garak/Promptfoo OWASP-LLM red-team; judge-calibration agreement ≥0.80 / κ ≥0.60 |

**Rule:** a repo records project-specific *values and findings* (its measured coverage, its ACR rows, its red-team results) in its own `ROADMAP.md` / audit artifacts. It does **not** restate the rigor — it cites the standard.

---

## The enforcement model (binary, no exceptions)

Every control in every standard is exactly one of:

- **AUTO-GATE** — mechanically checkable, **merge-blocking in CI**, required status check under branch protection. Example: `pytest --cov-fail-under=85`.
- **REVIEW-GATE** — requires human judgment, paired with **(a)** a checklist item in the PR template and **(b)** a committed artifact (signed walkthrough, ACR, threat model, risk register). The transition is blocked until the box is checked and the artifact is in the diff or linked.

A control that is "run but `|| true`," "advisory," or "on the roadmap" is a **defect**. The portfolio has live instances of this defect (`pip-audit || true` in `ledger`/`nearmiss`; `continue-on-error` pa11y in the eval harnesses; `tracesSampleRate: 0` in `davis`); the owning standards close each one.

---

## Quality-attribute taxonomy — ISO/IEC 25010:2023

**Updated to the 2023 second edition** (replaces 2011). Nine top-level product-quality characteristics; the deltas from 2011 are load-bearing and called out. Each feature/story **must** map to ≥1 measurable acceptance criterion under ≥1 characteristic; an untested characteristic is an **out-of-scope violation** and must be declared N/A-with-reason (see *Scoping*). **Recheck the standard version at build time.**

> 2023 deltas you must use the new vocabulary for: *Usability* → **Interaction Capability** (adds inclusivity, self-descriptiveness, user-engagement); *Portability* → **Flexibility** (adds **scalability**); Security adds **resistance**; and **Safety** is a brand-new ninth characteristic. ISO 25010:2023 also defines a *Quality-in-Use* model (Effectiveness, Efficiency, Satisfaction, Freedom-from-Risk, Context-Coverage) — used in REVIEW-GATE acceptance criteria for civic/public-facing repos.

### 1. Functional Suitability *(completeness, correctness, appropriateness)*
- **Targets:** all acceptance criteria pass; no `P0`/`P1` open at release; acceptance tests mapped 1:1 to roadmap features.
- **Gate (AUTO):** full suite green; mapping checked in CI.

### 2. Performance Efficiency *(time behaviour, resource utilization, capacity)*
- **Targets (web/API default):** p95 server response <500 ms (non-LLM routes); p95 first-token <1.5 s and full-response <6 s (LLM routes); Lighthouse Performance ≥90; critical-path JS <200 KB gzip. Regression budget: no numeric regression >10% vs committed baseline without product-owner sign-off.
- **Gate (AUTO):** k6/Locust asserts p95 budgets; Lighthouse CI asserts score + bundle budgets; baseline artifact committed per PR touching latency-sensitive paths.

### 3. Compatibility *(co-existence, interoperability)*
- **Targets:** two latest versions of Chrome/Firefox/Safari/Edge; documented minimum Node/Python runtimes; no undeclared global state; declared, versioned API contracts.
- **Gate (AUTO):** Playwright cross-browser smoke; runtime/dependency matrix in CI.

### 4. Interaction Capability *(recognizability, learnability, operability, user-error protection, engagement, inclusivity, self-descriptiveness, user assistance)* — *formerly Usability*
- **Targets:** **WCAG 2.2 AA** floor (AAA where already achieved, e.g. `personal-site`); keyboard-only completion of every primary task; visible focus; `prefers-reduced-motion` respected; readable at 200% zoom / 320 px; 2.5.8 target-size ≥24×24 CSS px; real EN/ES where civic.
- **Gate:** **see `ACCESSIBILITY-STANDARD.md` and `INTERNATIONALIZATION-STANDARD.md`.** AUTO: axe zero critical/serious/moderate; pa11y-ci **blocking**; Lighthouse a11y ≥0.9 (≥95 where self-declared, e.g. `gtfs-scorecard` MUST wire it). REVIEW: screen-reader walkthrough + ACR per release.

### 5. Reliability *(faultlessness, availability, fault tolerance, recoverability)*
- **Targets:** declared SLO (default 99.5% monthly for hosted services); graceful degradation on dependency failure; no data loss on crash; idempotent writes; MTTR clock starts at alert-fire, not customer report.
- **Gate:** AUTO: chaos/fault-injection test for top dependency failure; restart-recovery test; `/livez` + `/readyz` (**see `OBSERVABILITY-STANDARD.md`**). REVIEW: error-budget burn reviewed at release.

### 6. Security *(confidentiality, integrity, non-repudiation, accountability, authenticity, **resistance**)* — *`resistance` new in 2023*
- **Targets:** ASVS 5.0 **L2** for anything touching sensitive PII (`fare-assistant` transit PII, civic RAG), L1 floor elsewhere; no HIGH/CRITICAL SAST/SCA findings; secrets never in source; least-privilege tokens; signed commits + signed releases.
- **Gate:** **see `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` + `CI-CD-STANDARD.md`.** AUTO: Semgrep/CodeQL, gitleaks (pre-commit **and** CI, **no `|| true`**), pip-audit/OSV/Trivy blocking on **CRITICAL,HIGH**, SHA-pinned `uses:`, SBOM+cosign+SLSA L2. REVIEW: threat model per new attack surface; Scorecard ≥8/10 with critical checks 10/10.

### 7. Maintainability *(modularity, reusability, analysability, modifiability, testability)*
- **Targets:** branch coverage ≥85% (libraries ≥90%); cyclomatic complexity ≤10 (`ruff C90`); typed (TS strict / `mypy --strict` or `pyright`); lint/format clean; duplication ≤3% on new code; no `TODO` without a linked issue.
- **Gate:** **see `CODE-QUALITY-STANDARD.md`.** AUTO: coverage/complexity/type/lint all merge-blocking via `make verify` (byte-equal to CI).

### 8. Flexibility *(adaptability, **scalability**, installability, replaceability)* — *formerly Portability; adds scalability*
- **Targets:** one-command local bring-up; containerized; IaC where hosted; documented teardown; horizontal-scale path documented for hosted services; no machine-specific assumptions.
- **Gate (AUTO):** CI builds container + runs from-scratch bring-up; IaC `plan` validates.

### 9. Safety — **NEW in 2023** *(operational constraint, risk identification, fail-safe, hazard warning, safe integration)*
- **Definition:** "acceptable levels of risk to human life, health, property, or environment." For our **non-safety-critical-but-high-stakes** repos (civic benefits, transit, OSINT, identity), Safety applies via **fail-safe** and **safe-integration** sub-characteristics. This is where the portfolio's signature responsible-tech guards live.
- **Targets / measured-by per repo (illustrative, values live in-repo):**
  - `ledger`: no-outing guarantee — injected sentinel identities never surface (isolated CI job). **AUTO.**
  - `women-artist-discovery`: "no identity inference ever" via AST-level static test. **AUTO.**
  - civic RAG / `fare-assistant`: no ungrounded code path; citation/grounding guards. **AUTO** (see `AI-EVALUATION-STANDARD.md`).
  - `nearmiss`: reproducibility tamper-tripwire. **AUTO.**
  - `self-osint-monitor`: consent gate sequenced before any feature. **AUTO** gate + **REVIEW** consent artifact.
- **Gate:** AUTO where the guard is code-enforced (the above); REVIEW: residual-risk register + fail-safe walkthrough per release. For genuinely safety-critical features, the acceptance criteria must address all five Safety sub-characteristics explicitly.

### 10. Data quality & lineage *(portfolio addendum — civic/transit ingest)*
- **Targets:** every record traceable to source + fetch timestamp; schema-validated on ingest; staleness alarms; per-source freshness SLA. Applies to `gtfs-scorecard`, `tods-validate`, `davis-bike-hazard-map`, `jobradar`, civic RAG.
- **Gate (AUTO):** ingest-validation tests; a committed **data card** per source (license, refresh cadence). Untrusted external zips/subprocess paths (`gtfs-scorecard` fetches external GTFS + runs a Java subprocess) carry a Safety + Security note.

---

## DORA — portfolio-level delivery-health signal

ISO 25010 says *what* quality is; DORA says *how fast and safely* it ships. This is a **portfolio-level health signal**, not a per-PR gate — measured automatically from CI/CD + incident events, reviewed quarterly. Manual tracking is prohibited for any repo claiming a performance tier.

**Five-metric model (2024, supersedes the original four keys):**

| DORA metric | Portfolio floor (alert if breached) | Elite reference | Measured by | Gate |
|-------------|-------------------------------------|-----------------|-------------|------|
| Deployment Frequency | ≥ weekly per active repo; alert if < deploy for 14 d | on-demand / multiple per day | release/deploy events from GH Actions | health signal (REVIEW quarterly) |
| Change Lead Time (commit→prod) | P90 < 1 day; alert if > 1 day | < 1 hour | commit→deploy timestamps | health signal |
| Change Fail Rate | < 15%; alert if > 10% (14-d rolling) | ≤ 5% | failed-deploy / incident events | health signal |
| Failed-Deployment Recovery Time | < 1 day; alert if any incident > 4 h | < 1 hour | incident open→resolve | health signal |
| Deployment Rework Rate *(new 2024)* | < 10%; alert if > 5% (30-d) | low | unplanned-fix deploy ratio | health signal |

**Reference implementation:** `dora-team/fourkeys` (Google OSS) ingesting GH Actions deploy events; incidents from GitHub issues labelled `incident`. Hosted repos with Lambdas (`personal-site`, `jobradar`, `fare-assistant`) feed real deploy events; library/CLI repos report DF/LT only.

**2024/2025 findings we act on (not survey trivia):**
- AI adoption is **positively** associated with throughput but **negatively** with stability — so automated safety nets (coverage gate, SAST, merge queue, red-team) are **prerequisite infrastructure**, not optional hygiene. This directly justifies the AUTO-GATE-everything stance.
- **DORA 2025 AI Capabilities Model** is a REVIEW-GATE governance checklist before expanding AI tooling scope in any AI/RAG repo: (1) written AI policy acknowledged, (2) AI grounded in internal context, (3) foundational CI/CD at elite tier, (4) safety nets operational, (5) internal-platform health scored, (6) user-centric metrics defined, (7) **AI-generated code segmented in DORA metrics**. Do not expand scope until all seven hold.
- High-performance tier shrank (31%→22%) and AI amplifies existing gaps → the standard sets **minimum floors**, not just elite targets (above).

---

## Definition of Done (per-repo `DEFINITION_OF_DONE.md`)

Every repo ships a checked-in `DEFINITION_OF_DONE.md` at root, CODEOWNER-protected (engineering-leadership approval to modify), reviewed quarterly. Three tiers:

**AUTO-GATE (CI on every PR — required status checks under branch protection):**

```
1. format + lint            → ruff/eslint, zero errors            [CODE-QUALITY]
2. type-check               → mypy --strict / tsc strict, zero    [CODE-QUALITY]
3. unit + integration       → coverage branch ≥85% (libs ≥90%),   [CODE-QUALITY]
                              complexity ≤10, --cov-fail-under
4. security                 → semgrep+codeql+gitleaks+pip-audit/   [SECURITY]
                              osv+trivy, blocking HIGH+CRITICAL,
                              SHA-pinned uses:, SBOM+cosign+SLSA
5. workflow SAST            → zizmor on any .github/workflows/ PR  [CI-CD]
6. accessibility            → axe 0 crit/serious/mod; pa11y BLOCK; [ACCESSIBILITY]
                              Lighthouse a11y ≥0.9 / ≥95 declared
7. i18n (bilingual repos)   → key-parity + placeholder-parity +   [I18N]
                              msgfmt --check + pseudolocale
8. ai-eval (prompt/retr.)   → faithfulness ≥0.80, hallucination   [AI-EVALUATION]
                              ≤5%, red-team, judge κ ≥0.60
9. observability            → structured-JSON log shape (jq test), [OBSERVABILITY]
                              secret-in-logs SAST rule
10. performance             → k6/Lighthouse budgets, ≤10% regress  [this doc §2]
11. build + container + IaC plan
```

`make verify` runs stages 1–4 (and 6–9 where applicable) locally, **byte-for-byte identical to CI** — the portfolio's drift-killing discipline; propagate it to every Python repo.

**REVIEW-GATE (human sign-off committed as PR attestation + artifact):**
- PR template checklist: acceptance criteria linked to issue; observability added (OTel spans on new paths); docs updated; rollback plan for schema/infra changes; ISO 25010 characteristic(s) named.
- New external attack surface → threat-model sign-off (`SECURITY`).
- New custom interactive component → ARIA APG audit; screen-reader walkthrough (`ACCESSIBILITY`).
- New AI feature → NIST AI RMF risk register + EU AI Act / ISO 42001 impact assessment (`AI-EVALUATION`).

**RELEASE-GATE:** performance baseline regression passed; runbook updated; ACR + SBOM + provenance regenerated ("audit-as-artifact"); rollback documented.

**Branch protection (per `CI-CD-STANDARD.md`, org rulesets preferred):** PR required (≥1 approval, ≥2 for Safety/Security-critical paths), last-pusher cannot self-approve, stale reviews dismissed, CODEOWNERS routing `.github/workflows/` + Safety-critical files to a required reviewer, required status checks in **strict** mode, **signed commits**, **linear history**, **block force-pushes**, **no admin bypass on `main`**. Merge queue on high-velocity branches.

---

## Metrics ledger (per repo)

Each repo's `ROADMAP.md` carries a **Metrics** table with this exact shape so enforcement is unambiguous. Project-specific *values* go here; the *rigor* is cited to the owning standard.

| Metric | Target | Measured by | Gate | Owner |
|--------|--------|-------------|------|-------|
| Branch coverage | ≥ 85% (libs ≥ 90%) | `pytest --cov` in CI | AUTO | — |
| axe violations | 0 crit/serious/mod | `axe-core` / `pa11y-ci` | AUTO | — |
| p95 first-token | < 1.5 s | k6 load test | AUTO | — |
| SHA-pinned `uses:` | 100% | `zizmor` / Scorecard Pinned-Deps ≥9 | AUTO | — |
| RAG faithfulness | ≥ 0.80 | RAGAS in CI | AUTO | — |
| EN/ES key parity | 100% | extract + parity check | AUTO | — |
| Screen-reader walkthrough | per release | committed checklist + ACR | REVIEW | — |
| Threat model | per new surface | committed `THREATS.md`/ADR | REVIEW | — |

A metric is **AUTO-GATE** or **REVIEW-GATE** — never "aspirational." If it cannot be made merge-blocking, it is review-gated with a checklist item and a committed artifact.

---

## Scoping: declare N/A, never silently skip

A standard that does not apply to a repo must be recorded as **N/A-with-reason** in that repo's `ROADMAP.md` — a silent skip is a defect. Common cases:

- **i18n N/A** for single-user / English-only libraries — but the repo must still record the one-line entry point (wrap strings in `_()`). EN/ES key-parity is AUTO-GATE for **every** shipping bilingual repo (civic RAG, `fare-assistant`, `ledger`, `nearmiss`, `swelter`, `trans-docs-navigator`, `personal-site`, `habitable`).
- **Observability (OTel/SLO) out-of-scope** for libraries/CLIs — but `--log-format json` opt-in must exist and the out-of-scope decision must be documented.
- **Accessibility (browser-engine) N/A** for headless libraries — but tools whose own HTML output is user-facing (eval harnesses: `civic-ai-eval-harness`, `govchat-eval`) **must** gate on their report's a11y.
- **AI-eval N/A** for non-AI repos.

**`self-osint-monitor`** is spec-only (no CI, Makefile, pyproject, or tests). It is the one repo where these standards are authored as the **M0/M1 scaffold**, not retrofitted: `CODE-QUALITY` toolchain + `make verify` + consent-gate (Safety) before any M1 code. **`queer-the-stacks` / `queer-specfic-reader`** share a package and must be reconciled (documented fork or merge) before standards work is counted, to avoid double-counting and independent drift.

---

Last verified: 2026-06-21 · Recheck cadence: quarterly, or on any new revision of ISO/IEC 25010, the DORA annual report, WCAG, OWASP ASVS, or OpenSSF Baseline — whichever is sooner.
