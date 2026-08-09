# Portfolio Standards

The cross-cutting rigor for every repo in this portfolio, stated **once**. A repo references these documents and records only its own project-specific *values and findings*; it never restates the rigor. This is the "reference, don't repeat" rule, and it is load-bearing — when a target moves (an OWASP/WCAG/ISO revision), it moves in one place.

Examples use broad service shapes such as hosted services, web frontends, and
local-only tools. These are reusable categories, never stable aliases for a
specific repository. Current project inventory, applicability, implementation
status, and remediation state belong only in the private registry; they are
outside the exact `public-distribution.json` document set and are never copied
into release archives or vendored public documentation. The source repository
and its history remain private; releases expose only that history-free document
projection.

## The enforcement model (binary gate types; explicit provisional dispositions)

Every control in every standard is exactly one of two kinds. There is no third "aspirational" category.

- **AUTO-GATE** — mechanically checkable and **merge-blocking** in CI. No `|| true`, no `continue-on-error`, and no direct admin bypass on `main`; the sole break-glass path is the audited, PR-only CICD-15 procedure.
- **REVIEW-GATE** — requires an accountable human decision; paired with a checklist line and a
  dated, durable artifact that is regenerated on release. The default artifact is committed; an
  owning standard may instead require an authenticated current-head PR/release record where committing
  the decision would create a circular hash. The evidence informing that decision may be direct human
  observation or, only where the owning standard explicitly authorizes it, truth-labeled synthetic
  evidence plus residual-risk acceptance.

A provisional release is a **disposition of a REVIEW-GATE**, not a third gate type and not a pass for
work that did not happen. Synthetic evidence never becomes a human walkthrough, user research,
screen-reader testing, or a conformance finding by being signed. The owning standard must define
eligibility, required evidence, expiry, invalidation triggers, public wording, and the conditions that
restore the normal human-review requirement.

`QUALITY-AND-METRICS-STANDARD.md` is the **spine**: it owns the ISO/IEC 25010:2023 vocabulary, the DORA delivery-health backbone, and the merge-gate model, and it points to each domain standard below rather than restating it.

## The documents

| Standard | Owns | Applies to |
|----------|------|------------|
| [`QUALITY-AND-METRICS-STANDARD.md`](./QUALITY-AND-METRICS-STANDARD.md) | The quality-attribute taxonomy (ISO 25010:2023), DORA metrics, the per-repo metrics ledger, and the reference CI pipeline. The index every other standard hangs off. | All repos |
| [`AI-DEVELOPMENT-MEASUREMENT-STANDARD.md`](./AI-DEVELOPMENT-MEASUREMENT-STANDARD.md) | Track A measurement for AI-assisted development: delivery outcomes, quality-debt counterweights, local-only tool telemetry, and metrics that must never become gates. | All repos (under the Quality & Metrics scope) |
| [`CODE-QUALITY-STANDARD.md`](./CODE-QUALITY-STANDARD.md) | Languages & versions, ruff/mypy/pytest + coverage floors, complexity limits, `uv`/`hatch` + lockfiles, src layout, ADRs; TS strict + ESLint flat + Vitest for frontends. | All repos |
| [`SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`](./SECURITY-AND-SUPPLY-CHAIN-STANDARD.md) | OWASP ASVS 5.0 level, SAST/SCA/secret/container scanning, Action SHA-pinning, SBOM + Sigstore + SLSA, token-permission model. | All repos that ship code |
| [`CI-CD-STANDARD.md`](./CI-CD-STANDARD.md) | The merge-blocking pipeline, least-privilege `GITHUB_TOKEN`, OIDC (no long-lived secrets), branch rulesets + CODEOWNERS, `zizmor`, reusable workflows, `make verify` parity. | All repos with CI |
| [`RELEASE-AND-VERSIONING-STANDARD.md`](./RELEASE-AND-VERSIONING-STANDARD.md) | SemVer + public-API contract, signed tags, CHANGELOG, the trusted-main signed-tag release pipeline, Trusted Publishing (PyPI OIDC), yank/deprecation/security-release policy. | All repos that produce a release |
| [`ACCESSIBILITY-STANDARD.md`](./ACCESSIBILITY-STANDARD.md) | WCAG 2.2 AA floor, axe/pa11y/Lighthouse auto-gates, keyboard & reflow tests, human screen-reader walkthrough + ACR, and a truth-labeled provisional synthetic-evidence path for eligible solo-maintained projects. | Any repo emitting human-facing HTML |
| [`OBSERVABILITY-STANDARD.md`](./OBSERVABILITY-STANDARD.md) | OpenTelemetry, structured JSON logging with PII redaction, `/livez`+`/readyz`, SLO/error-budget + burn-rate alerts, Core Web Vitals RUM. Tiered by deployment shape. | Servers; lighter tier for libraries/frontends |
| [`PERFORMANCE-STANDARD.md`](./PERFORMANCE-STANDARD.md) | k6 latency budgets, Lighthouse-CI score + bundle budgets, the committed `perf/baseline.json` + >10%-regression rule, and its update ritual. | Hosted services + frontends (DoD performance stage) |
| [`INTERNATIONALIZATION-STANDARD.md`](./INTERNATIONALIZATION-STANDARD.md) | Externalized strings, ICU/MessageFormat 2 + gettext catalogs, BCP-47, key/placeholder-parity + pseudolocale gates, RTL. Explicit opt-out for English-only personal tools. | Public-facing civic surfaces |
| [`AI-EVALUATION-STANDARD.md`](./AI-EVALUATION-STANDARD.md) | Eval-driven development; RAG faithfulness/recall/precision, hallucination + refusal gates, red-team suites, judge calibration, model/data cards. NIST AI RMF + EU AI Act framing. | AI/RAG/eval repos |
| [`DOCUMENTATION-STANDARD.md`](./DOCUMENTATION-STANDARD.md) | What every repo documents, the per-document responsibility split, authoring rules, currency stamps, status, and the definition of production-ready. | All repos |
| [`RESPONSIBLE-TECH-FRAMEWORK.md`](./RESPONSIBLE-TECH-FRAMEWORK.md) | The audit *methodology* (Ethics, Bias, Privacy/DPIA, Transparency, Accessibility, Security) each repo instantiates as committed findings. | All repos |
| [`INCIDENT-RESPONSE-STANDARD.md`](./INCIDENT-RESPONSE-STANDARD.md) | The severity ladder, the `incident`/`sevN` label convention feeding DORA, the committed postmortem artifact, and the secret-leak runbook (rotate → revoke → history-scrub decision → postmortem). | All repos |
| [`DATA-GOVERNANCE-STANDARD.md`](./DATA-GOVERNANCE-STANDARD.md) | Data classification, data cards + lineage, retention schedules, backup/DR expectations for local-first repos, license/provenance for ingested civic data, and the policy layer over dataset versioning and PII-in-logs. | All repos that hold data beyond their own source |

## Living deliverables

The private source repository maintains copy-paste templates and portfolio-wide
operational records. They are deliberately excluded from the history-free
public document projection; each standard states the required shape of its
consumer-owned REVIEW-GATE artifacts.

Current conformance snapshots, repository classifications, remediation
priorities, and evidence links stay in the private applicability and remediation
registries. They are deliberately not part of this publishable standards index.

## Starting a new repo

Don't hand-copy files from an existing repo. The private source repository
maintains a Copier template that scaffolds `pyproject.toml`, `make verify`, CI
workflows, and documentation skeletons. That source-only scaffold is not part
of the public standards archive.

## How a repo declares conformance

1. The repo `README.md` states **which standards apply** and marks any as `N/A` **with a one-line reason** — silent omission is a defect.
2. Per-repo *values* (measured coverage, ASVS level, ACR rows, eval thresholds, SLOs) live in that repo's `docs/ROADMAP.md` Metrics table and `docs/RESPONSIBLE-TECH-AUDITS.md`, not here.
3. `make verify` reproduces the full AUTO-GATE set locally, byte-for-byte with CI. A standard is met
   when its gates are green on `main` and its review-gated artifacts are committed and current. A
   provisional release authorized by an owning standard remains explicitly **not conformant** with the
   still-open experiential review gate.

## Publishing cadence

This repo dogfoods [`RELEASE-AND-VERSIONING-STANDARD.md`](./RELEASE-AND-VERSIONING-STANDARD.md): SemVer 2.0.0, annotated signed `vX.Y.Z` tags cut only on `main`, and a Keep-a-Changelog entry per release (`CHANGELOG.md`). The cadence:

- **MINOR — monthly, if there are changes.** At most one scheduled minor per month, cut only when `main` carries unreleased backward-compatible changes (new standards or sections, new automation, relaxed or clarified guidance). No empty releases.
- **PATCH — ad hoc.** Typo, link, and tooling fixes that change no requirement ship whenever they are ready.
- **MAJOR — any gate-tightening change, with a migration note.** **Tightening any gate is a breaking change for consumers**: adding an AUTO-GATE, raising a threshold (coverage floor, severity cutoff), converting a REVIEW-GATE to an AUTO-GATE, or narrowing an N/A carve-out can turn a consuming repo's green CI red on its next bump. Every MAJOR ships a CHANGELOG migration note naming the tightened gates and what a consumer must do before bumping. Loosening a gate, or adding guidance that gates nothing, is MINOR.

Releasing: `sh automation/release.sh vX.Y.Z` verifies every gate and the live branch/tag protections,
then creates an SSH-signed tag whose message binds the immutable hosted tag ruleset. The trusted-main
workflow builds and signs the manifest-defined public document archive, creates a draft release,
byte-verifies every draft asset and attestation, and only then promotes it. Consumers pin a tag
(CI-fetch `ref:` or vendored `.standards-version`); the private release
automation opens a version-bump change in each configured consumer.

The prescribed controls are established, testable engineering patterns. Each
repository records its own implementation evidence and remaining gaps in the
private applicability registry rather than in this publishable index.

Last verified: 2026-06-21 · Recheck cadence: per ISO 25010 / WCAG / OWASP ASVS / NIST AI RMF revision, or quarterly.
