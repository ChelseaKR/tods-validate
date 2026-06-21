# Documentation Standard

This standard defines the documentation every repo in this portfolio carries, what each document is responsible for, how an autonomous agent (Claude Code) reads and acts on them, and how a repo vendors and declares the cross-cutting `STANDARDS/` set. It exists so that no project re-invents structure and so that "production-ready" means the same thing across all ~18 repos.

Doc index: 8 of the `STANDARDS/` set. Peers it routes to: `CODE-QUALITY-STANDARD`, `SECURITY-AND-SUPPLY-CHAIN-STANDARD`, `CI-CD-STANDARD`, `OBSERVABILITY-STANDARD`, `ACCESSIBILITY-STANDARD`, `INTERNATIONALIZATION-STANDARD`, `AI-EVALUATION-STANDARD`, `QUALITY-AND-METRICS-STANDARD`, `RESPONSIBLE-TECH-FRAMEWORK`.

---

## 1. The `STANDARDS/` set

The portfolio standardizes rigor in one place and references it everywhere. Repos do **not** copy enforcement machinery into their own docs; they cite the standard and record only project-specific values and findings ("reference, don't repeat").

| # | Standard | Owns | One-line rationale |
|---|----------|------|--------------------|
| 0 | `RESPONSIBLE-TECH-FRAMEWORK.md` | Ethics/privacy/bias/transparency audit *methodology*, the audit-as-artifact discipline | The portfolio's signature strength; the *how*, not the per-repo findings |
| 1 | `CODE-QUALITY-STANDARD.md` | ruff/mypy/pytest floors, coverage thresholds, layout, `make verify`/CI parity | Same logical stack must pin to the same versions and rule sets across repos |
| 2 | `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | SAST/SCA/secret-scan/container-CVE, SHA-pinning, SBOM, signing, provenance | tj-actions/trivy-action 2026 compromises made mutable-tag refs an active threat |
| 3 | `CI-CD-STANDARD.md` | Token permissions, OIDC, branch protection, CODEOWNERS, workflow SAST, concurrency | Default-write `GITHUB_TOKEN` and unscanned workflows are the systemic CI gap |
| 4 | `OBSERVABILITY-STANDARD.md` | Structured logging, OTel, SLOs, health probes — tiered by deployment shape | ~15 repos log unstructured; no repo emits OTel spans or defines SLOs |
| 5 | `ACCESSIBILITY-STANDARD.md` | WCAG 2.2 AA floor, axe/Lighthouse/pa11y gates, SR walkthroughs | Structural gates are strong; browser-engine checks must graduate to blocking |
| 6 | `INTERNATIONALIZATION-STANDARD.md` | Portable catalogs (gettext `.po` / MF2-ICU), key-parity, pseudolocale | Civic repos target Spanish-dominant CA populations on hand-rolled dicts |
| 7 | `AI-EVALUATION-STANDARD.md` | RAG faithfulness, red-team, hallucination, judge-calibration, model cards | World-class bespoke eval discipline exists; codify it as the named norm |
| 8 | `DOCUMENTATION-STANDARD.md` (this) | Doc responsibilities, authoring rules, agent consumption, vendoring, declaration | So "production-ready" means one thing everywhere |
| 9 | `QUALITY-AND-METRICS-STANDARD.md` | DORA tracking, Definition of Done, the merge-gate manifest | The roll-up that the gates in 1–7 report into |

**Rejected alternative:** a single monolithic `STANDARDS.md`. Rejected because the doc index is the unit of vendoring and N/A declaration; one file per concern lets a repo mark exactly which concerns are out of scope.

### 1.1 How a repo vendors `STANDARDS/`

`STANDARDS/` is a single source of truth, not duplicated prose per repo. Vendoring mechanism, in priority order:

1. **Git submodule** at `STANDARDS/` pointing at the canonical standards repo, pinned to a tag (`standards@vMAJOR.MINOR`). This is the default.
2. **`git subtree`** for repos where contributors cannot initialize submodules (frontends handed to non-git collaborators).

Whichever is used, the pin is recorded and is itself subject to the supply-chain currency rules.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| `STANDARDS/` present and pinned | Submodule/subtree pinned to a released tag, not a floating branch | `git submodule status` shows a tag-resolved SHA; CI step asserts non-`heads/` ref | AUTO-GATE |
| Vendored version is current | Within one minor of the latest `standards` tag | CI compares pinned tag to `gh release view --repo <standards>`; warns at 1 minor, fails at 2 | AUTO-GATE |
| No forked/edited standard text in-repo | `STANDARDS/*.md` byte-identical to the pinned tag | CI `git diff --exit-code` against the submodule blob | AUTO-GATE |

```yaml
# .github/workflows/standards-pin.yml  (snippet)
- name: Assert STANDARDS/ is tag-pinned and unmodified
  run: |
    git submodule status STANDARDS | grep -Eq '^\s' \
      || { echo "STANDARDS/ submodule not initialized"; exit 1; }
    git -C STANDARDS describe --exact-match --tags HEAD \
      || { echo "STANDARDS/ not pinned to a released tag"; exit 1; }
    git diff --quiet HEAD -- STANDARDS \
      || { echo "STANDARDS/ has local edits — edit upstream, not here"; exit 1; }
```

**N/A:** none. Every repo vendors `STANDARDS/`. `self-osint-monitor` (spec-only) vendors it at M0 as part of the scaffold, before any M1 code.

---

## 2. Documents and their single responsibilities

| Document | Owns | Does **not** own |
|----------|------|------------------|
| `README.md` | First contact: what/why/for-whom, status, quickstart, the Claude Code build entrypoint, **and the Standards Conformance table (§5)** | Detailed specs, metrics tables, audit findings |
| `docs/ROADMAP.md` | The buildable spec: problem, product, research, design, architecture, quality targets, the phased build plan, GTM, legal, ops | Generic enforcement machinery (lives in `STANDARDS/`) |
| `docs/RESPONSIBLE-TECH-AUDITS.md` | Project-specific ethics, bias, privacy, transparency, accessibility, security findings, checklists, and committed reports (DPIA, ACR/VPAT, threat model, data/model cards, residual-risk register) | The audit *methodology* (lives in `STANDARDS/RESPONSIBLE-TECH-FRAMEWORK.md`) |
| `docs/adr/NNNN-*.md` | The **ADR log**: every architecturally-significant or guardrail-affecting decision, immutably, in order | Day-to-day task notes; reversible trivia |
| `CHANGELOG.md` | Human-facing record of what changed per release, Keep a Changelog format, SemVer | Commit-by-commit history (that is `git log`) |
| `CITATION.cff` | How to cite the work; author, ORCID, DOI when archived | Licensing (that is `LICENSE`) |
| `SECURITY.md` | Supported versions, private disclosure channel, response SLA | Scan configuration (that lives in CI + standard 2) |
| `CONTRIBUTING.md` | How to build, test, run `make verify`, and the DCO/sign-off + review rules | Code of conduct prose if a separate `CODE_OF_CONDUCT.md` exists |
| `STANDARDS/*` | Cross-cutting rigor stated once | Anything project-specific |

---

## 3. The ADR log

Decisions that change architecture, a hard guardrail, a dependency with a license/supply-chain impact, or a quality/audit threshold are recorded as ADRs. This replaces the prior practice of appending ADR prose to the roadmap's architecture section, which did not scale and was not diffable.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| ADR log exists | `docs/adr/` with `0000-record-architecture-decisions.md` and a MADR-format template | File presence check in CI | AUTO-GATE |
| ADRs are sequential and immutable | Filenames `NNNN-kebab-title.md`, monotonic, superseded (never edited) by a later ADR's `Status: Superseded by NNNN` | CI lints numbering gaps/dupes and forbids content changes to an `Accepted` ADR (diff on existing IDs blocks) | AUTO-GATE |
| Guardrail changes carry an ADR | Any PR touching a no-outing/grounding/consent/identity-inference guard, `permissions:` blocks, or a coverage/eval threshold links an ADR | CODEOWNERS routes those paths to a required reviewer who confirms the ADR link | REVIEW-GATE (checklist item + committed ADR artifact) |

Required ADR front matter: `Status` (`Proposed`/`Accepted`/`Superseded by NNNN`/`Deprecated`), `Date`, `Deciders`, `Context`, `Decision`, `Consequences`. Status is one of the listed values — there is no informal state.

```
docs/adr/
  0000-record-architecture-decisions.md   # the meta-ADR; explains the log
  0001-pin-actions-to-full-sha.md
  0002-gettext-po-over-python-dicts.md     # e.g. an i18n repo
```

**N/A:** none for any repo past `Spec` status. A `Spec`-status repo (`self-osint-monitor`) carries the log skeleton and ADR-0001 = "scaffold standards before M1 code".

---

## 4. CHANGELOG / CITATION / SECURITY / CONTRIBUTING expectations

These four files have one canonical shape portfolio-wide so a reader (or agent) never guesses.

| File | Required content | Measured by | Gate |
|------|------------------|-------------|------|
| `CHANGELOG.md` | Keep-a-Changelog headings; `Unreleased` section; SemVer; every release tag has a dated entry | `git tag` ⇄ changelog parity check; `Unreleased` non-empty on a tagging PR | AUTO-GATE |
| `CITATION.cff` | Valid CFF 1.2.0; `title`, `authors` (with ORCID where held), `version`, `date-released`, `license`; DOI once Zenodo-archived | `cffconvert --validate` in CI | AUTO-GATE |
| `SECURITY.md` | Supported-versions table, a private disclosure channel (GitHub private vuln reporting enabled), and a stated triage SLA (≤ 72 h ack) | File presence + repo setting `private-vulnerability-reporting=enabled` via `gh api` | AUTO-GATE (presence); REVIEW-GATE (SLA accuracy) |
| `CONTRIBUTING.md` | `make verify` as the single local gate, the PR review/sign-off rule, and a pointer to the README conformance table | Presence + a link-check that `make verify` and `STANDARDS/` are referenced | AUTO-GATE |

```cff
# CITATION.cff (minimal valid)
cff-version: 1.2.0
title: <repo>
message: "If you use this work, please cite it."
authors:
  - family-names: Kelly-Reif
    given-names: Chelsea
    orcid: "https://orcid.org/0000-0000-0000-0000"
version: 0.1.0
date-released: 2026-06-21
license: MIT
```

**N/A-with-reason allowances:**
- `CITATION.cff` may be marked N/A only for repos with no scholarly/civic-reuse intent (a purely personal local-only tool). The README states: `CITATION.cff — N/A: personal local-only utility, no external reuse expected.`
- No repo may mark `SECURITY.md` or `CHANGELOG.md` N/A. `CONTRIBUTING.md` may be N/A only for single-author `Spec`-status repos, and must flip to required at `Scaffolded`.

---

## 5. Every README declares which standards apply

Silent skipping is the defect this section eliminates. Each README carries a **Standards Conformance** table listing all ten standards (§1) with one of three states: `Applies` (and conformant), `Applies — gap tracked in #NN` (non-conformant, with an open issue), or `N/A — <one-line reason>`. There is no fourth state and no blank cell.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Conformance table complete | All ten standards present, each with a non-empty state | A `verify-conformance` CI script parses the README table; missing/blank row fails | AUTO-GATE |
| Every `N/A` has a reason | No bare `N/A` | Same script: `N/A` rows must match `N/A — .+` | AUTO-GATE |
| Every gap links an issue | `Applies — gap tracked in #NN` resolves to an open issue | `gh issue view NN` exists and is open | AUTO-GATE |
| `N/A` reasons are honest | Human confirms (e.g., i18n N/A genuinely is English-only single-user) | Release checklist line | REVIEW-GATE |

Example README block (a privacy-first local library, e.g. `ledger`):

```markdown
## Standards Conformance
| Standard | State |
|----------|-------|
| Responsible-Tech Framework | Applies (no-outing guarantee, sentinel-identity CI job) |
| Code Quality | Applies |
| Security & Supply-Chain | Applies — gap tracked in #142 (pip-audit ran with `|| true`; gate restored) |
| CI/CD | Applies |
| Observability | Applies — library tier: `--log-format json` opt-in; OTel out-of-scope (no server) |
| Accessibility | N/A — headless library, no HTML/UI surface |
| Internationalization | Applies — EN/ES key-parity gate; migrating dicts → gettext `.po` (#138) |
| AI Evaluation | N/A — no model/prompt/retrieval surface |
| Documentation | Applies |
| Quality & Metrics | Applies |
```

Common, **pre-approved** `N/A` patterns (still must be written out):
- Accessibility / i18n **N/A** for a headless library or CLI with no user-facing HTML and English-only operator output — but i18n N/A repos must still record the one-line entry point: "wrap user strings in `_()` to add a catalog."
- AI-Evaluation **N/A** for any repo with no prompt/retrieval/model-version surface.
- Observability OTel marked out-of-scope for the library/CLI tier (per standard 4's tiering) — this is a tier selection, not a skip.

---

## 6. Authoring rules

1. **Decisions, not options.** A roadmap states the chosen stack, data source, and metric with a one-line rationale. Alternatives appear only as a short "rejected because" note. Ambiguity is a defect.
2. **Every claim about quality is testable.** "Fast" is not a target; "p95 first-token latency < 1.5 s on the reference deployment, enforced by a k6 load test in CI" is. "Accessible" is not a target; "axe-core zero critical/serious/moderate, blocking" is.
3. **Binary enforcement.** Every control is either **AUTO-GATE** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATE** (human judgment, paired with a checklist item and a committed artifact). There is no "aspirational" third category. A control you cannot phrase as one of the two does not belong in a standard.
4. **Reference, don't repeat.** Generic CI gates, the quality taxonomy, and audit procedures live in `STANDARDS/`. Roadmaps and READMEs link to them and record only project-specific *values* and *findings*.
5. **Currency stamps.** Any document whose correctness depends on the outside world (laws, broker lists, framework versions, API contracts, scan tool versions) carries a `Last verified: YYYY-MM-DD` line and a `Recheck cadence:` line at the bottom.
6. **Status is explicit.** Each repo README shows one of: `Spec` · `Scaffolded` · `In build (Mx)` · `Beta` · `Production` · `Maintained` · `Archived`.
7. **N/A is declared, never silent** (§5). A standard that does not apply is written out with its reason.

---

## 7. How Claude Code should consume these docs

- **Start at the README "For Claude Code" section and the Standards Conformance table.** Together they are the contract: scope, hard guardrails (the lines that must never be crossed), commands, the definition of done, and exactly which standards bind this repo.
- **Treat `docs/ROADMAP.md` § "Implementation Plan" as the work breakdown.** Execute phases in order. Do not begin a phase until the previous phase's acceptance criteria and merge-blocking metrics pass in CI.
- **Wire `RESPONSIBLE-TECH-AUDITS.md` checklists and the applicable `STANDARDS/` gates into CI at Phase 0**, not at the end. Audits that only happen at launch are theater. The guardrail tests (no-outing sentinels, grounding/citation guards, consent gate, no-identity-inference AST test) are the *first* CI jobs to land.
- **Read `STANDARDS/` from the vendored, pinned copy** — never re-derive a rule from memory. If a gate threshold is needed (coverage floor, faithfulness floor, Scorecard minimum), the standard is authoritative.
- **Record decisions as ADRs** (§3), not as roadmap edits. When the build makes a decision the roadmap didn't anticipate, open `docs/adr/NNNN-*.md`. Touching a guardrail, a `permissions:` block, or a threshold *requires* an ADR.
- **When the spec and reality conflict** (an API changed, a metric target is infeasible on the chosen tier, a standard's gate cannot pass on the chosen platform), stop and surface the conflict with a recommended resolution and a draft ADR — do not silently diverge.
- **Keep docs live.** Update `CHANGELOG.md` `Unreleased` in the same PR as the change. Bump `CITATION.cff` `version`/`date-released` on a release PR. Flip a conformance row from "gap tracked in #NN" to "Applies" in the PR that closes the gap.

---

## 8. Definition of "production-ready" (portfolio-wide)

A system is production-ready when, and only when:

1. All acceptance criteria in `ROADMAP.md` pass.
2. Every applicable AUTO-GATE across `STANDARDS/` 1–7 is green on `main` (code quality, supply-chain, CI/CD, observability tier, accessibility, i18n where applicable, AI-eval where applicable), and every REVIEW-GATE has its committed artifact.
3. Every merge-blocking gate in `QUALITY-AND-METRICS-STANDARD.md` is green on `main`.
4. Every applicable audit in `RESPONSIBLE-TECH-AUDITS.md` has a committed, passing, release-regenerated report.
5. The README Standards Conformance table (§5) has zero open-gap rows; every row is `Applies` or `N/A — reason`.
6. The supply-chain floor holds: all `uses:` SHA-pinned, OpenSSF Scorecard Pinned-Dependencies ≥ 9/10 and Token-Permissions = 10/10, SBOM + signing on release artifacts.
7. The doc set is complete and current: `README`, `docs/ROADMAP.md`, `docs/RESPONSIBLE-TECH-AUDITS.md`, `docs/adr/`, `CHANGELOG.md`, `CITATION.cff` (or declared N/A), `SECURITY.md`, `CONTRIBUTING.md`, all carrying valid currency stamps where required.
8. There is a runnable `make verify` (or equivalent) that reproduces 1–4 locally and in CI — byte-for-byte identical invocation to the CI job, eliminating local/remote drift.
9. There is an operations section a tired on-call human could follow at 2 a.m.

A repo at `Spec` status (`self-osint-monitor`) is exempt from 1–9 except the requirement to vendor `STANDARDS/` and carry the ADR log skeleton; its ADR-0001 commits to scaffolding the standards before any M1 code.

---

Last verified: 2026-06-21 · Recheck cadence: per major framework change, on any `STANDARDS/` minor-version bump, or quarterly — whichever is first.
