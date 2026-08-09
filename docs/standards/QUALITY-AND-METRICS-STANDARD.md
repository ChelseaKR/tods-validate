# Quality & Metrics Standard

This is the canonical definition of the quality attributes every project targets and the mechanism by which their metrics are **enforced** rather than merely measured. It is the **spine** of `STANDARDS/`: it owns the vocabulary (ISO/IEC 25010:2023), the delivery-health backbone (DORA), and the merge-gate model. The cross-cutting depth for each domain lives in a dedicated sibling standard — this document **points to** them and does not restate them.

Projects override the *values* (a hobby logger needs less than a public benefits tool) but not the *structure*.

> **On "100% enforcement."** A metric is enforced when failing it **blocks the merge** — not when a dashboard shows it red after the fact. Everything mechanically checkable is a hard CI gate; everything requiring judgment (genuine bias, accessibility-of-experience, ethical edge cases) remains a *required human sign-off gate* with a checklist and a dated durable artifact (committed by default; an authenticated current-head PR/release record only where the owning standard authorizes it). An owning domain standard may authorize a narrowly scoped, truth-labeled **provisional release** from synthetic evidence plus maintainer residual-risk acceptance while an experiential REVIEW-GATE remains open. That disposition does not satisfy or reclassify the gate, establish conformance, or create a third gate type. Accessibility's bounded pathway is defined in `ACCESSIBILITY-STANDARD.md` §2.0.

## Sibling standards (reference, don't repeat)

This document is the index. Each row below is enforced **in** the named standard; the cell here states only the one-line interface this spine depends on.

| Domain | Owning standard | Interface this spine depends on |
|--------|-----------------|---------------------------------|
| Code quality / toolchain | `CODE-QUALITY-STANDARD.md` | ruff ≥0.15.x, mypy `--strict`, branch coverage ≥85% (libs ≥90%), single `pyproject.toml`, `uv sync --frozen`, `make verify` byte-equal to CI |
| CI/CD hardening | `CI-CD-STANDARD.md` | top-level `permissions: contents: read`, OIDC-only cloud creds, `zizmor` on workflow PRs, concurrency groups, committed CODEOWNERS + branch ruleset |
| Security & supply chain | `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | ASVS 5.0 L2; SHA-pinned actions; Semgrep/CodeQL/gitleaks/pip-audit/Trivy blocking on HIGH+CRITICAL; SBOM + cosign + SLSA L2 |
| Release & versioning | `RELEASE-AND-VERSIONING-STANDARD.md` | SemVer 2.0.0; signed tags; CHANGELOG entry per release; trusted-main dispatch re-runs verification at the selected tag; Trusted Publishing (OIDC, no stored tokens); version-consistency gate |
| Observability | `OBSERVABILITY-STANDARD.md` | structured JSON logs, OTel spans, `/livez` + `/readyz`, SLOs + burn-rate alerts (tiered by deployment shape) |
| Performance | `PERFORMANCE-STANDARD.md` | k6 p95 budgets + Lighthouse-CI score/bundle budgets asserted against committed `perf/baseline.json`; >10% regression fails without product-owner sign-off; copyable `perf/` reference dir |
| Accessibility | `ACCESSIBILITY-STANDARD.md` | WCAG 2.2 AA floor; axe zero critical/serious/moderate; pa11y **blocking**; screen-reader walkthrough + ACR per release; provisional solo-maintainer disposition in §2.0 |
| Internationalization | `INTERNATIONALIZATION-STANDARD.md` | portable catalogs (gettext `.po` / MF2-ICU); EN/ES key-parity + placeholder-parity + pseudolocale gates |
| AI evaluation | `AI-EVALUATION-STANDARD.md` | RAGAS faithfulness ≥0.80; hallucination ≤5%; Garak/Promptfoo OWASP-LLM red-team; judge-calibration agreement ≥0.80 / κ ≥0.60 |
| Incident response | `INCIDENT-RESPONSE-STANDARD.md` | severity ladder (SEV1–4); `incident`/`sevN` labels feeding the DORA rows below; committed postmortem within 7 days (SEV1/2); secret-leak runbook |
| Data governance | `DATA-GOVERNANCE-STANDARD.md` | data classification (L0–L3); data cards + lineage per ingest source; retention schedules; backup/DR for local-first repos; license/provenance for civic data |

**Rule:** a repo records project-specific *values and findings* (its measured coverage, its ACR rows, its red-team results) in its own `ROADMAP.md` / audit artifacts. It does **not** restate the rigor — it cites the standard.

---

## The enforcement model (two gate types; provisional release is not a gate type)

Every control in every standard is exactly one of:

- **AUTO-GATE** — mechanically checkable, **merge-blocking in CI**, required status check under branch protection. Example: `pytest --cov-fail-under=85`.
- **REVIEW-GATE** — requires human judgment, paired with **(a)** a checklist item in the PR template and **(b)** a dated durable artifact (normally committed; authenticated current-head PR/release metadata only where explicitly authorized). The transition is blocked until the box is checked and the artifact is in the diff or linked, unless the owning domain standard explicitly authorizes a truth-labeled provisional release while leaving that box open.

A control that is "run but `|| true`," "advisory," or "on the roadmap" is a **defect**. The owning standard must make the check blocking or classify it honestly as a non-gate; project-specific findings stay in the private remediation registry.

---

## Quality-attribute taxonomy — ISO/IEC 25010:2023

**Updated to the 2023 second edition** (replaces 2011). Nine top-level product-quality characteristics; the deltas from 2011 are load-bearing and called out. Each feature/story **must** map to ≥1 measurable acceptance criterion under ≥1 characteristic; an untested characteristic is an **out-of-scope violation** and must be declared N/A-with-reason (see *Scoping*). **Recheck the standard version at build time.**

> 2023 deltas you must use the new vocabulary for: *Usability* → **Interaction Capability** (adds inclusivity, self-descriptiveness, user-engagement); *Portability* → **Flexibility** (adds **scalability**); Security adds **resistance**; and **Safety** is a brand-new ninth characteristic. ISO 25010:2023 also defines a *Quality-in-Use* model (Effectiveness, Efficiency, Satisfaction, Freedom-from-Risk, Context-Coverage) — used in REVIEW-GATE acceptance criteria for civic/public-facing repos.

### 1. Functional Suitability *(completeness, correctness, appropriateness)*
- **Targets:** all acceptance criteria pass; no `P0`/`P1` open at release; acceptance tests mapped 1:1 to roadmap features.
- **Gate (AUTO):** full suite green; mapping checked in CI.

### 2. Performance Efficiency *(time behaviour, resource utilization, capacity)*
- **Targets (web/API default):** p95 server response <500 ms (non-LLM routes); p95 first-token <1.5 s and full-response <6 s (LLM routes); Lighthouse Performance ≥90; critical-path JS <200 KB gzip. Regression budget: no numeric regression >10% vs committed baseline without product-owner sign-off.
- **Gate (AUTO):** **see `PERFORMANCE-STANDARD.md`** (reference implementation in `perf/`: copyable k6 script, `lighthouserc` budget, baseline schema). k6 asserts p95 budgets; Lighthouse CI asserts score + bundle budgets; `perf/baseline.json` committed, updated per PR touching latency-sensitive paths; >10% regression vs baseline fails without product-owner sign-off.

### 3. Compatibility *(co-existence, interoperability)*
- **Targets:** two latest versions of Chrome/Firefox/Safari/Edge; documented minimum Node/Python runtimes; no undeclared global state; declared, versioned API contracts.
- **Gate (AUTO):** Playwright cross-browser smoke; runtime/dependency matrix in CI.

### 4. Interaction Capability *(recognizability, learnability, operability, user-error protection, engagement, inclusivity, self-descriptiveness, user assistance)* — *formerly Usability*
- **Targets:** **WCAG 2.2 AA** floor (retain any higher conformance a repository has declared); keyboard-only completion of every primary task; visible focus; `prefers-reduced-motion` respected; readable at 200% zoom / 320 px; 2.5.8 target-size ≥24×24 CSS px; real multilingual content where civic.
- **Gate:** **see `ACCESSIBILITY-STANDARD.md` and `INTERNATIONALIZATION-STANDARD.md`.** AUTO: axe zero critical/serious/moderate; pa11y-ci **blocking**; Lighthouse a11y ≥0.9, or a higher self-declared floor. REVIEW: screen-reader walkthrough + ACR per release. Any provisional accessibility disposition follows `ACCESSIBILITY-STANDARD.md` §2.0 and leaves the REVIEW-GATE open.

### 5. Reliability *(faultlessness, availability, fault tolerance, recoverability)*
- **Targets:** declared SLO (default 99.5% monthly for hosted services); graceful degradation on dependency failure; no data loss on crash; idempotent writes; MTTR clock starts at alert-fire, not customer report.
- **Gate:** AUTO: chaos/fault-injection test for top dependency failure; restart-recovery test; `/livez` + `/readyz` (**see `OBSERVABILITY-STANDARD.md`**). REVIEW: error-budget burn reviewed at release.

### 6. Security *(confidentiality, integrity, non-repudiation, accountability, authenticity, **resistance**)* — *`resistance` new in 2023*
- **Targets:** ASVS 5.0 **L2** for anything touching sensitive PII, including transit/location data and civic RAG; L1 floor elsewhere; no HIGH/CRITICAL SAST/SCA findings; secrets never in source; least-privilege tokens; signed commits + signed releases.
- **Gate:** **see `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` + `CI-CD-STANDARD.md`.** AUTO: Semgrep/CodeQL, gitleaks (pre-commit **and** CI, **no `|| true`**), pip-audit/OSV/Trivy blocking on **CRITICAL,HIGH**, SHA-pinned `uses:`, SBOM+cosign+SLSA L2. REVIEW: threat model per new attack surface; Scorecard ≥8/10 with critical checks 10/10.

### 7. Maintainability *(modularity, reusability, analysability, modifiability, testability)*
- **Targets:** branch coverage ≥85% (libraries ≥90%); cyclomatic complexity ≤10 (`ruff C90`); typed (TS strict / `mypy --strict` or `pyright`); lint/format clean; duplication ≤3% on new code; no `TODO` without a linked issue.
- **Gate:** **see `CODE-QUALITY-STANDARD.md`.** AUTO: coverage/complexity/type/lint all merge-blocking via `make verify` (byte-equal to CI).

### 8. Flexibility *(adaptability, **scalability**, installability, replaceability)* — *formerly Portability; adds scalability*
- **Targets:** one-command local bring-up; containerized; IaC where hosted; documented teardown; horizontal-scale path documented for hosted services; no machine-specific assumptions.
- **Gate (AUTO):** CI builds container + runs from-scratch bring-up; IaC `plan` validates.

### 9. Safety — **NEW in 2023** *(operational constraint, risk identification, fail-safe, hazard warning, safe integration)*
- **Definition:** "acceptable levels of risk to human life, health, property, or environment." For **non-safety-critical but high-stakes** surfaces such as civic benefits, transit, identity, or public-data tools, Safety applies via **fail-safe** and **safe-integration** sub-characteristics.
- **Targets / measured-by per repo (illustrative, values live in-repo):**
  - no-outing guarantee — injected sentinel identities never surface (isolated CI job). **AUTO.**
  - "no identity inference ever" via AST-level static test. **AUTO.**
  - civic RAG or public-service AI: no ungrounded code path; citation/grounding guards. **AUTO** (see `AI-EVALUATION-STANDARD.md`).
  - evidence-integrity pipeline: reproducibility tamper-tripwire. **AUTO.**
  - privacy-sensitive local tools: consent gate sequenced before any feature. **AUTO** gate + **REVIEW** consent artifact.
- **Gate:** AUTO where the guard is code-enforced (the above); REVIEW: residual-risk register + fail-safe walkthrough per release. For genuinely safety-critical features, the acceptance criteria must address all five Safety sub-characteristics explicitly.

### 10. Data quality & lineage *(portfolio addendum — civic/transit ingest)*
- **Owned by `DATA-GOVERNANCE-STANDARD.md`.** Data-card presence, source + fetch-timestamp traceability, schema validation on ingest, staleness alarms, and per-source freshness SLAs are specified in full there (§1–2); this taxonomy slot exists only so "data quality" has a home in the ISO 25010 characteristic list.
- **Targets/Gate:** see `DATA-GOVERNANCE-STANDARD.md` §1 (data cards) and §2 (retention). Applies to civic/transit data products, monitoring pipelines, and civic RAG. Untrusted external archives or subprocess paths additionally carry a Safety + Security note owned by `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`.

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

**Implementation contract:** a `gh api`-based collector reads deploy, release,
and publish workflow runs plus `incident`-labelled issues, then writes a
committed quarterly `DORA-<year>-Q<n>.md` report and JSON snapshot. Hosted
repositories and Lambdas feed deploy events; library/CLI repositories report
DF/LT only. Failed-Deployment Recovery Time reads N/A until the repository has
adopted the incident-label convention; the collector never fabricates a zero.

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
10. performance             → k6/Lighthouse budgets, ≤10% regress  [PERFORMANCE]
                              vs committed perf/baseline.json
11. build + container + IaC plan
```

`make verify` runs stages 1–4 (and 6–9 where applicable) locally, **byte-for-byte identical to CI** — the portfolio's drift-killing discipline; propagate it to every Python repo.

**REVIEW-GATE (human sign-off committed as PR attestation + artifact):**
- PR template checklist: acceptance criteria linked to issue; observability added (OTel spans on new paths); docs updated; rollback plan for schema/infra changes; ISO 25010 characteristic(s) named.
- New external attack surface → threat-model sign-off (`SECURITY`).
- New custom interactive component → ARIA APG audit; screen-reader walkthrough (`ACCESSIBILITY`; §2.0 governs any provisional disposition).
- New AI feature → NIST AI RMF risk register + EU AI Act / ISO 42001 impact assessment (`AI-EVALUATION`).

**RELEASE-GATE:** performance baseline regression passed; runbook updated; ACR (or the accessibility §2.0 provisional status record) + SBOM + provenance regenerated ("audit-as-artifact"); rollback documented. A domain-authorized provisional release must carry the synthetic-evidence record and maintainer residual-risk acceptance while keeping the human gate visibly open; it is not a conformance result.

**Branch protection (per `CI-CD-STANDARD.md`, org rulesets preferred):** PR required (≥1 independent approval, ≥2 for Safety/Security-critical paths), stale reviews dismissed, CODEOWNERS routing `.github/workflows/` + Safety-critical files to a required reviewer, required status checks in **strict** mode, **signed commits**, **linear history**, and **blocked force-pushes/direct admin pushes**. A designated maintainer may bypass only through a PR under the documented CICD-15 emergency procedure. An eligible exactly-one-maintainer project uses CQ §7.1/CICD §5.1: platform approval count 0 plus an authenticated current-head owner decision and all checks green; it never labels self/synthetic review as independent approval. Accessibility §2.0 preserves linear history by merging the product change first, testing that protected-main commit, and merging the record through a separate evidence-only PR. Merge queue on high-velocity branches.

---

## Metrics ledger (per repo)

Each repo's `ROADMAP.md` carries a **Metrics** table with this exact shape so enforcement is unambiguous. Project-specific *values* go here; the *rigor* is cited to the owning standard.

| Metric | Target | Measured by | Gate | Owner |
|--------|--------|-------------|------|-------|
| Branch coverage [CQ-08] | ≥ 85% (libs ≥ 90%) | `pytest --cov` in CI | AUTO | — |
| axe violations [A11Y-01] | 0 crit/serious/mod | `axe-core` / `pa11y-ci` | AUTO | — |
| p95 first-token [QM-02] | < 1.5 s | k6 load test | AUTO | — |
| SHA-pinned `uses:` [SEC-25] | 100% | `zizmor` / Scorecard Pinned-Deps ≥9 | AUTO | — |
| RAG faithfulness [AIEV-02] | ≥ 0.80 | RAGAS in CI | AUTO | — |
| EN/ES key parity [I18N-08] | 100% | extract + parity check | AUTO | — |
| Screen-reader walkthrough [A11Y-11, A11Y-14] | per release | committed checklist + ACR | REVIEW | — |
| Threat model [QM-14] | per new surface | committed `THREATS.md`/ADR | REVIEW | — |

A metric is **AUTO-GATE** or **REVIEW-GATE** — never "aspirational." If it cannot be made merge-blocking, it is review-gated with a checklist item and a dated durable artifact under the owning standard.

---

## Scoping: declare N/A, never silently skip

A standard that does not apply to a repo must be recorded as **N/A-with-reason** in that repo's `ROADMAP.md` — a silent skip is a defect. Common cases:

- **i18n N/A** for single-user / English-only libraries — but the repo must still record the one-line entry point (wrap strings in `_()`). Locale key-parity is AUTO-GATE for **every** shipping multilingual repository.
- **Observability (OTel/SLO) out-of-scope** for libraries/CLIs — but `--log-format json` opt-in must exist and the out-of-scope decision must be documented.
- **Accessibility (browser-engine) N/A** for headless libraries — but tools whose own HTML output is user-facing **must** gate on their report's accessibility.
- **AI-eval N/A** for non-AI repos.

A pre-code repository authors these standards as its initial scaffold rather
than retrofitting them: the code-quality toolchain, `make verify`, and any
applicable consent gate land before feature code. Duplicate or forked packages
must be reconciled or documented before conformance is counted.

## DORA implementation — no longer aspirational

The DORA section mandated automated measurement but named only the `fourkeys`
reference. The portfolio implementation is **`automation/delivery_metrics.py`**
(git + `gh` mining, no LLM), emitting `metrics/PORTFOLIO-METRICS.md` on the weekly
launchd cadence: the DORA five plus the AI-quality-debt counterweights (churn,
short-term-churn-14d, unreviewed-merge rate, revert rate). It **segments AI-authored
vs human-authored** work via the `Co-Authored-By: Claude …` commit trailer, which
closes the DORA-2025 AI-capabilities checklist item "AI-generated code segmented in
DORA metrics." The full Track A methodology — the BASELINE/graduation gate state,
the never-gate list, telemetry privacy, and the quarterly DORA AI-Capabilities
self-assessment — lives in **`AI-DEVELOPMENT-MEASUREMENT-STANDARD.md`**.

---

Last verified: 2026-06-21 · Recheck cadence: quarterly, or on any new revision of ISO/IEC 25010, the DORA annual report, WCAG, OWASP ASVS, or OpenSSF Baseline — whichever is sooner.
