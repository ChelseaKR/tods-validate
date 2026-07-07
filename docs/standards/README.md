# Portfolio Standards

The cross-cutting rigor for every repo in this portfolio, stated **once**. A repo references these documents and records only its own project-specific *values and findings*; it never restates the rigor. This is the "reference, don't repeat" rule, and it is load-bearing — when a target moves (an OWASP/WCAG/ISO revision), it moves in one place.

## The enforcement model (binary, no exceptions)

Every control in every standard is exactly one of two kinds. There is no third "aspirational" category.

- **AUTO-GATE** — mechanically checkable and **merge-blocking** in CI. No `|| true`, no `continue-on-error`, no admin bypass on `main`.
- **REVIEW-GATE** — requires human judgment; paired with a checklist line and a **committed, dated artifact** that is regenerated on release.

`QUALITY-AND-METRICS-STANDARD.md` is the **spine**: it owns the ISO/IEC 25010:2023 vocabulary, the DORA delivery-health backbone, and the merge-gate model, and it points to each domain standard below rather than restating it.

## The documents

| Standard | Owns | Applies to |
|----------|------|------------|
| [`QUALITY-AND-METRICS-STANDARD.md`](./QUALITY-AND-METRICS-STANDARD.md) | The quality-attribute taxonomy (ISO 25010:2023), DORA metrics, the per-repo metrics ledger, and the reference CI pipeline. The index every other standard hangs off. | All repos |
| [`CODE-QUALITY-STANDARD.md`](./CODE-QUALITY-STANDARD.md) | Languages & versions, ruff/mypy/pytest + coverage floors, complexity limits, `uv`/`hatch` + lockfiles, src layout, ADRs; TS strict + ESLint flat + Vitest for frontends. | All repos |
| [`SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`](./SECURITY-AND-SUPPLY-CHAIN-STANDARD.md) | OWASP ASVS 5.0 level, SAST/SCA/secret/container scanning, Action SHA-pinning, SBOM + Sigstore + SLSA, token-permission model. | All repos that ship code |
| [`CI-CD-STANDARD.md`](./CI-CD-STANDARD.md) | The merge-blocking pipeline, least-privilege `GITHUB_TOKEN`, OIDC (no long-lived secrets), branch rulesets + CODEOWNERS, `zizmor`, reusable workflows, `make verify` parity. | All repos with CI |
| [`RELEASE-AND-VERSIONING-STANDARD.md`](./RELEASE-AND-VERSIONING-STANDARD.md) | SemVer + public-API contract, signed tags, CHANGELOG, the tag-triggered release pipeline, Trusted Publishing (PyPI OIDC), yank/deprecation/security-release policy. | All repos that produce a release |
| [`ACCESSIBILITY-STANDARD.md`](./ACCESSIBILITY-STANDARD.md) | WCAG 2.2 AA floor, axe/pa11y/Lighthouse auto-gates, keyboard & reflow tests, screen-reader walkthrough + ACR. | Any repo emitting HTML (3 frontends + Python report/answer output) |
| [`OBSERVABILITY-STANDARD.md`](./OBSERVABILITY-STANDARD.md) | OpenTelemetry, structured JSON logging with PII redaction, `/livez`+`/readyz`, SLO/error-budget + burn-rate alerts, Core Web Vitals RUM. Tiered by deployment shape. | Servers; lighter tier for libraries/frontends |
| [`INTERNATIONALIZATION-STANDARD.md`](./INTERNATIONALIZATION-STANDARD.md) | Externalized strings, ICU/MessageFormat 2 + gettext catalogs, BCP-47, key/placeholder-parity + pseudolocale gates, RTL. Explicit opt-out for English-only personal tools. | Public-facing civic surfaces |
| [`AI-EVALUATION-STANDARD.md`](./AI-EVALUATION-STANDARD.md) | Eval-driven development; RAG faithfulness/recall/precision, hallucination + refusal gates, red-team suites, judge calibration, model/data cards. NIST AI RMF + EU AI Act framing. | AI/RAG/eval repos |
| [`DOCUMENTATION-STANDARD.md`](./DOCUMENTATION-STANDARD.md) | What every repo documents, the per-document responsibility split, authoring rules, currency stamps, status, and the definition of production-ready. | All repos |
| [`RESPONSIBLE-TECH-FRAMEWORK.md`](./RESPONSIBLE-TECH-FRAMEWORK.md) | The audit *methodology* (Ethics, Bias, Privacy/DPIA, Transparency, Accessibility, Security) each repo instantiates as committed findings. | All repos |

## Living deliverables

- [`AUDIT-2026-06-21.md`](./AUDIT-2026-06-21.md) — the current conformance snapshot of all 18 repos against these standards: portfolio-wide gaps, cross-repo inconsistencies, and per-repo findings.
- [`IMPROVEMENTS-BACKLOG.md`](./IMPROVEMENTS-BACKLOG.md) — the prioritized "what to fix next," with quick wins called out. Re-run the audit and refresh both after each uplift PR.

## How a repo declares conformance

1. The repo `README.md` states **which standards apply** and marks any as `N/A` **with a one-line reason** — silent omission is a defect.
2. Per-repo *values* (measured coverage, ASVS level, ACR rows, eval thresholds, SLOs) live in that repo's `docs/ROADMAP.md` Metrics table and `docs/RESPONSIBLE-TECH-AUDITS.md`, not here.
3. `make verify` reproduces the full AUTO-GATE set locally, byte-for-byte with CI. A standard is met when its gates are green on `main` and its review-gated artifacts are committed and current.

The portfolio already proves every target here is achievable — `civic-ai-eval-harness`, `govchat-eval`, `habitable`, and `trans-docs-navigator` ship most of the maximized posture today. The work these standards describe is **propagation, not invention**.

Last verified: 2026-06-21 · Recheck cadence: per ISO 25010 / WCAG / OWASP ASVS / NIST AI RMF revision, or quarterly.
