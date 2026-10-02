# Documentation Standard

This standard defines the documentation every repo in this portfolio carries, what each document is responsible for, how an autonomous agent (Claude Code) reads and acts on them, and how a repo consumes and declares the cross-cutting `STANDARDS/` set. It exists so that no project re-invents structure and so that "production-ready" means the same thing across the portfolio.

Doc index: 10 of 15 in the `STANDARDS/` set. Peers it routes to: `CODE-QUALITY-STANDARD`, `SECURITY-AND-SUPPLY-CHAIN-STANDARD`, `CI-CD-STANDARD`, `RELEASE-AND-VERSIONING-STANDARD`, `OBSERVABILITY-STANDARD`, `PERFORMANCE-STANDARD`, `ACCESSIBILITY-STANDARD`, `INTERNATIONALIZATION-STANDARD`, `AI-EVALUATION-STANDARD`, `QUALITY-AND-METRICS-STANDARD`, `AI-DEVELOPMENT-MEASUREMENT-STANDARD`, `RESPONSIBLE-TECH-FRAMEWORK`, `INCIDENT-RESPONSE-STANDARD`, `DATA-GOVERNANCE-STANDARD`.

---

## 1. The `STANDARDS/` set

The portfolio standardizes rigor in one place and references it everywhere. Repos do **not** copy enforcement machinery into their own docs; they cite the standard and record only project-specific values and findings ("reference, don't repeat").

| # | Standard | Owns | One-line rationale |
|---|----------|------|--------------------|
| 0 | `RESPONSIBLE-TECH-FRAMEWORK.md` | Ethics/privacy/bias/transparency audit *methodology*, the audit-as-artifact discipline | The portfolio's signature strength; the *how*, not the per-repo findings |
| 1 | `CODE-QUALITY-STANDARD.md` | ruff/mypy/pytest floors, coverage thresholds, layout, `make verify`/CI parity | Same logical stack must pin to the same versions and rule sets across repos |
| 2 | `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | SAST/SCA/secret-scan/container-CVE, SHA-pinning, SBOM, signing, provenance | The tj-actions (March 2025) and trivy-action (March 2026) compromises made mutable-tag refs an active threat |
| 3 | `CI-CD-STANDARD.md` | Token permissions, OIDC, branch protection, CODEOWNERS, workflow SAST, concurrency | Default-write tokens and unscanned workflows are systemic risks |
| 4 | `RELEASE-AND-VERSIONING-STANDARD.md` | SemVer + public-API contract, signed tags, CHANGELOG, trusted-main signed-tag release pipeline, Trusted Publishing, yank/deprecation/security-release policy | Every consumed artifact needs an explicit version and release contract |
| 5 | `OBSERVABILITY-STANDARD.md` | Structured logging, OTel, SLOs, health probes — tiered by deployment shape | Telemetry needs one portable schema and enforcement model |
| 6 | `PERFORMANCE-STANDARD.md` | k6 latency budgets, Lighthouse-CI score and bundle budgets, committed regression baselines | Performance claims need a reproducible budget and an explicit baseline-update ritual |
| 7 | `ACCESSIBILITY-STANDARD.md` | WCAG 2.2 AA floor, axe/Lighthouse/pa11y gates, SR walkthroughs | Structural and browser-engine checks must both block |
| 8 | `INTERNATIONALIZATION-STANDARD.md` | Portable catalogs (gettext `.po` / MF2-ICU), key-parity, pseudolocale | Civic multilingual surfaces need portable catalogs and parity gates |
| 9 | `AI-EVALUATION-STANDARD.md` | RAG faithfulness, red-team, hallucination, judge-calibration, model cards | AI evaluation needs shared thresholds and evidence artifacts |
| 10 | `DOCUMENTATION-STANDARD.md` (this) | Doc responsibilities, authoring rules, American English, agent consumption, vendoring, declaration | So "production-ready" means one thing everywhere |
| 11 | `QUALITY-AND-METRICS-STANDARD.md` | DORA tracking, Definition of Done, the merge-gate manifest | The roll-up that the domain standards' gates report into |
| 12 | `AI-DEVELOPMENT-MEASUREMENT-STANDARD.md` | Outcome-oriented measurement for AI-assisted development, with quality-debt counterweights and prohibited uses | Development telemetry must inform process without becoming an individual-performance gate |
| 13 | `INCIDENT-RESPONSE-STANDARD.md` | Severity ladder, `incident`/`sevN` label convention feeding DORA, committed postmortem artifact, secret-leak runbook | Incidents need durable, consistently classified evidence |
| 14 | `DATA-GOVERNANCE-STANDARD.md` | Data classification, data cards + lineage, retention schedules, backup/DR, license/provenance for ingested civic data | Data rules had four partial owners and no retention/backup floor |
| 15 | `DISCOVERY-AND-ADOPTION-STANDARD.md` | Open Graph + backlink on published sites, a runnable README first screen, searched-for terms in the About, reserved install names, custom social previews, link-checked money pages, human-approved sends — **advisory** until promoted | Forty green CI runs and zero external referrers: distribution depended on memory, and memory lost; its conformance row is optional until promotion |

**Rejected alternative:** a single monolithic `STANDARDS.md`. Rejected because the doc index is the unit of vendoring and N/A declaration; one file per concern lets a repo mark exactly which concerns are out of scope.

### 1.1 How a repo consumes `STANDARDS/`

`STANDARDS/` is a single source of truth, not duplicated prose per repo. It lives in its own repo (`ChelseaKR/portfolio-standards`), released with SemVer tags per `RELEASE-AND-VERSIONING-STANDARD.md`. Distribution mechanisms, in priority order (per `automation/README.md` §Distribution):

1. **CI-fetch (primary).** The consuming repo's CI checks out `portfolio-standards` at a pinned release tag into a gitignored `.standards/` directory via a read-only deploy key, and runs the gates from there (`automation/ci-fetch/standards.yml` is the hardened reference workflow). Nothing from the standards repo is committed into the consuming repo.
2. **Vendored pinned copy (secondary).** For repos that cannot CI-fetch (no GitHub Actions, or a public repo where the deploy-key tradeoff is unacceptable), commit a copy at `STANDARDS/` (or `docs/standards/`) plus a one-line `.standards-version` marker recording the tag consumed. A Renovate custom datasource (or a small scheduled agent) opens a "bump standards to vX.Y.Z" PR on each release — pinned version + reviewable PR, no silent drift.

**Rejected alternative: git submodule.** Evaluated and rejected — submodule ergonomics are painful across a multi-repository portfolio and break shallow CI clones unless every workflow sets `submodules: true`. Do not build it.

Whichever mechanism is used, the pin is recorded and is itself subject to the supply-chain currency rules.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Standards pin present and tag-pinned [DOC-01] | The workflow `ref:` (CI-fetch) or `.standards-version` (vendored) names a released tag, never a branch | CI asserts the recorded ref matches a `vMAJOR.MINOR.PATCH` tag and is not `main`/a `heads/` ref | AUTO-GATE |
| Pinned version is current [DOC-02] | Within one minor of the latest `portfolio-standards` tag | CI compares the pinned tag to `gh release view --repo ChelseaKR/portfolio-standards`; warns at 1 minor, fails at 2 | AUTO-GATE |
| No forked/edited standard text in-repo [DOC-03] | Vendored `STANDARDS/*.md` byte-identical to the pinned tag's archive | CI diffs the vendored copy against the tag tarball (`git archive`); CI-fetch repos pass trivially — nothing is committed | AUTO-GATE |

```yaml
# .github/workflows/standards.yml  (snippet — full hardened workflow in automation/ci-fetch/standards.yml)
- name: Fetch pinned standards (private, read-only deploy key)
  uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
  with:
    repository: ChelseaKR/portfolio-standards
    ref: v1.0.1                      # bump in lockstep with .standards-version
    ssh-key: ${{ secrets.STANDARDS_DEPLOY_KEY }}
    path: .standards
    persist-credentials: false

- name: Standards freshness gate
  run: python3 .standards/automation/check_staleness.py --standards-dir .standards
```

**N/A:** none. Every repository consumes `STANDARDS/` by one of the two mechanisms. A pre-code repository wires it into the initial scaffold before feature code.

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
| `CONTRACTS.md` | Identifiers that must not be renamed without a migration, version or alias, each with its owner and change policy (§4.1) | The schemas themselves (those live beside the code that writes them) |
| `docs/incidents/YYYY-MM-DD-*.md` | Project-specific, blameless, committed postmortems per closed `incident` issue | The severity ladder, label convention, and secret-leak runbook *methodology* (lives in `STANDARDS/INCIDENT-RESPONSE-STANDARD.md`) |
| `docs/data/<source>.md` | Project-specific data cards: source, license, fetch cadence, tier, retention line, dataset version per ingested source | The classification tiers, retention floors, and backup/DR requirements *methodology* (lives in `STANDARDS/DATA-GOVERNANCE-STANDARD.md`) |
| `STANDARDS/*` | Cross-cutting rigor stated once | Anything project-specific |

---

## 3. The ADR log

Decisions that change architecture, a hard guardrail, a dependency with a license/supply-chain impact, or a quality/audit threshold are recorded as ADRs. This replaces the prior practice of appending ADR prose to the roadmap's architecture section, which did not scale and was not diffable.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| ADR log exists [DOC-04] | `docs/adr/` with `0000-record-architecture-decisions.md` and a MADR-format template | File presence check in CI | AUTO-GATE |
| ADRs are sequential and immutable [DOC-05] | Filenames `NNNN-kebab-title.md`, monotonic, superseded (never edited) by a later ADR's `Status: Superseded by NNNN` | CI lints numbering gaps/dupes and forbids content changes to an `Accepted` ADR (diff on existing IDs blocks) | AUTO-GATE |
| Guardrail changes carry an ADR [DOC-06] | Any PR touching a no-outing/grounding/consent/identity-inference guard, `permissions:` blocks, or a coverage/eval threshold links an ADR | CODEOWNERS routes those paths; the normal profile requires an eligible reviewer, while bounded solo mode records the owner's ADR disposition under `CODE-QUALITY-STANDARD.md` §7.1 | REVIEW-GATE (checklist item + committed ADR artifact) |

Required ADR front matter: `Status` (`Proposed`/`Accepted`/`Superseded by NNNN`/`Deprecated`), `Date`, `Deciders`, `Context`, `Decision`, `Consequences`. Status is one of the listed values — there is no informal state.

```
docs/adr/
  0000-record-architecture-decisions.md   # the meta-ADR; explains the log
  0001-pin-actions-to-full-sha.md
  0002-gettext-po-over-python-dicts.md     # e.g. an i18n repo
```

**N/A:** none for any repository past `Spec` status. A `Spec`-status repository carries the log skeleton and ADR-0001 = "scaffold standards before feature code".

---

## 4. CHANGELOG / CITATION / SECURITY / CONTRIBUTING expectations

These four files have one canonical shape portfolio-wide so a reader (or agent) never guesses.

| File | Required content | Measured by | Gate |
|------|------------------|-------------|------|
| `CHANGELOG.md` [DOC-07] | Keep-a-Changelog headings; `Unreleased` section; SemVer; every release tag has a dated entry | `git tag` ⇄ changelog parity check; `Unreleased` non-empty on a tagging PR | AUTO-GATE |
| `CITATION.cff` [DOC-08] | Valid CFF 1.2.0; `message`, `title`, `authors` (with ORCID where held), and `license`; `date-released` exactly when a tag names the declared `version`; DOI once Zenodo-archived | `cffconvert --validate` in CI; `automation/conformance_check.py` (`citation_cff`) | AUTO-GATE |
| `SECURITY.md` [DOC-09] | Supported-versions table, a private disclosure channel (GitHub private vuln reporting enabled), and a stated triage SLA (≤ 72 h ack) | File presence + repo setting `private-vulnerability-reporting=enabled` via `gh api` | AUTO-GATE (presence); REVIEW-GATE (SLA accuracy) |
| `CONTRIBUTING.md` [DOC-10] | `make verify` as the single local gate, the PR review/sign-off rule, and a pointer to the README conformance table | Presence + a link-check that `make verify` and `STANDARDS/` are referenced | AUTO-GATE |

```cff
# CITATION.cff (released-software example)
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

Before the first release tag, omit release-specific `version` and `date-released` rather
than inventing a release. Both fields are optional in the authoritative
[CFF 1.2.0 schema guide](https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md);
the portfolio requires them only where a release actually exists.

**`date-released` is a fact about the version this file declares, not about the
repository.** A repository that released `0.1.0` and is now preparing `0.2.0`
declares `version: "0.2.0"` and carries **no** `date-released`: there is no date
to give, because `v0.2.0` has not been cut. The rule is therefore per declared
version, and it runs in both directions:

| State of the declared `version` | `date-released` |
|---|---|
| A tag names it (`v<version>`, or a bare `<version>` where that is the repo's convention) | **Required.** The release happened; the date it happened is part of the citation record, and the record is what downstream indexes keep. |
| No tag names it | **Must be absent.** A release date on an unreleased version records a release that never happened. Add it in the same PR that cuts the tag (§3.2/REL-25 then checks it against the tag's own date). |
| The tag list could not be established | **Not measured**, never passed. A shallow or `--no-tags` checkout has no tag list to read, and reading its emptiness as "nothing has been released" would switch the requirement off wherever CI checks out shallowly — an absence rendered as a value, and a control that cannot fail. Check out with `fetch-depth: 0`, or let the checker read `origin`. |

**N/A-with-reason allowances:**
- `CITATION.cff` may be marked N/A only for repos with no scholarly/civic-reuse intent (a purely personal local-only tool). The README states: `CITATION.cff — N/A: personal local-only utility, no external reuse expected.`
- No repo may mark `SECURITY.md` or `CHANGELOG.md` N/A. `CONTRIBUTING.md` may be N/A only for single-author `Spec`-status repos, and must flip to required at `Scaffolded`.

### 4.1 `CONTRACTS.md`: identifiers that must not be renamed

Some names outlive the code that writes them. A `localStorage` key is in every visitor's browser; a DynamoDB attribute is in every stored item; a published JSON field, a CLI flag, a package's public function, a URL slug and a StoreKit product ID are in other people's code, bookmarks, search indexes and App Store records. Renaming one in the source is a one-line diff that passes every test in the repository, and it breaks everything outside it. On 2026-09-18 the portfolio-wide American English sweep had to guard these by hand, from memory, repository by repository: a private app's `favourites.v1` storage key, the `gtfs-scorecard` published artifact and schema fields, `afterward`'s dataset fields, public package APIs, and StoreKit IDs. Nothing listed them, so the only protection was an agent remembering to look.

A repository with **published artifacts, persisted storage, or a public package** keeps a short `CONTRACTS.md` at its root (or a `## Contracts` / `## Stable identifiers` section in `README.md`, `ARCHITECTURE.md` or a top-level `docs/*.md`) listing every identifier that must not be renamed without a migration, a version, or an alias:

| Requirement | What passes | Checked by | Gate |
|---|---|---|---|
| Persisted and published identifiers are declared [DOC-23] | A register table with an **Identifier** column, an **Owner** column and a **Change policy** column, and at least one row; or an explicit `None.` declaration when the repository has nothing to list. Kinds to cover: storage keys, database attributes, published schema and JSON fields, public API and CLI names, URLs and slugs, product IDs | `conformance_check.py` `identifier_contracts` (shape); PR review (completeness) | AUTO-GATE (report-only through 2026-10-18) + REVIEW-GATE |

```markdown
# Contracts

| Identifier | Kind | Where | Owner | Change policy |
|---|---|---|---|---|
| `favourites.v1` | localStorage key | `src/store.ts` | web app | Never renamed. A successor ships as `favorites.v2`, reads v1 once, then writes v2 only |
| `score_pct` | published JSON field | `site/data/*.json` | pipeline | Additive changes only; a rename ships the old name as an alias for one major version |
```

**Scope is read from `applicability.yml`, not judged per repository.** DOC-23 applies when the manifest entry has `distributable: true` (a public package), `hosted: true` (URLs, slugs and client storage), or the `civic-data-tool`, `eval-harness`, `monitoring-service` or `local-first-tool` archetype (published artifacts or persisted state). An unregistered repository is scoped conservatively. A repository in scope that genuinely persists and publishes nothing says so with `None.` and one line of why; that is a declaration, and a missing file is not.

**The AUTO half checks shape, not completeness.** It confirms the register exists and has the three columns; it cannot know that a key is missing. Review owns that, and the cheapest moment to catch an omission is the pull request that introduces the identifier. A rename of a listed identifier without the listed migration, version or alias is a review finding.

---

## 5. Every README declares which standards apply

Silent skipping is the defect this section eliminates. Each README carries a **Standards Conformance** table listing all 15 standards (§1) with one of three states: `Applies` (and conformant), `Applies — gap tracked in #NN` (non-conformant, with an open issue), or `N/A — <one-line reason>`. There is no fourth state and no blank cell.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Conformance table complete [DOC-11] | All 15 standards present, each with a non-empty state | A `verify-conformance` CI script parses the README table; missing/blank row fails | AUTO-GATE |
| Every `N/A` has a reason [DOC-12] | No bare `N/A` | Same script: `N/A` rows must match `N/A — .+` | AUTO-GATE |
| Every gap links an issue [DOC-13] | `Applies — gap tracked in #NN` resolves to an open issue | `gh issue view NN` exists and is open | AUTO-GATE |
| `N/A` reasons are honest [DOC-14] | Human confirms (e.g., i18n N/A genuinely is English-only single-user) | Release checklist line | REVIEW-GATE |

Example README block for a privacy-first local library:

```markdown
## Standards Conformance
| Standard | State |
|----------|-------|
| Responsible-Tech Framework | Applies (no-outing guarantee, sentinel-identity CI job) |
| Code Quality | Applies |
| Security & Supply-Chain | Applies — gap tracked in #142 (pip-audit ran with `|| true`; gate restored) |
| CI/CD | Applies |
| Release & Versioning | Applies — CalVer opt-out N/A; SemVer tags + CHANGELOG |
| Observability | Applies — library tier: `--log-format json` opt-in; OTel out-of-scope (no server) |
| Performance | N/A — headless library with no latency-sensitive service or frontend bundle |
| Accessibility | N/A — headless library, no HTML/UI surface |
| Internationalization | Applies — EN/ES key-parity gate; migrating dicts → gettext `.po` (#138) |
| AI Evaluation | N/A — no model/prompt/retrieval surface |
| Documentation | Applies |
| Quality & Metrics | Applies |
| AI Development Measurement | Applies — local aggregate delivery and quality-debt metrics; never used as gates |
| Incident Response | Applies — `incident`/`sevN` labels wired, no SEV1/2 to date |
| Data Governance | Applies — local-only data store, L3 tier, no-outing guarantee is the retention floor |
```

Common, **pre-approved** `N/A` patterns (still must be written out):
- Accessibility / i18n **N/A** for a headless library or CLI with no user-facing HTML and English-only operator output — but i18n N/A repos must still record the one-line entry point: "wrap user strings in `_()` to add a catalog."
- AI-Evaluation **N/A** for any repo with no prompt/retrieval/model-version surface.
- Observability OTel marked out-of-scope for the library/CLI tier (per `OBSERVABILITY-STANDARD.md` tiering) — this is a tier selection, not a skip.

---

## 6. Authoring rules

1. **Decisions, not options.** A roadmap states the chosen stack, data source, and metric with a one-line rationale. Alternatives appear only as a short "rejected because" note. Ambiguity is a defect.
2. **Every claim about quality is testable.** "Fast" is not a target; "p95 first-token latency < 1.5 s on the reference deployment, enforced by a k6 load test in CI" is. "Accessible" is not a target; "axe-core zero critical/serious/moderate, blocking" is.
3. **Binary enforcement.** Every control is either **AUTO-GATE** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATE** (human judgment, paired with a checklist item and a dated durable artifact—committed by default, authenticated current-head PR/release metadata only when explicitly authorized). A domain-authorized provisional release leaves its experiential REVIEW-GATE open; documentation must truth-label the synthetic evidence and maintainer residual-risk acceptance. It is not conformance or a third gate category (`ACCESSIBILITY-STANDARD.md` §2.0).
4. **Reference, don't repeat.** Generic CI gates, the quality taxonomy, and audit procedures live in `STANDARDS/`. Roadmaps and READMEs link to them and record only project-specific *values* and *findings*.
5. **Currency stamps.** Any document whose correctness depends on the outside world (laws, broker lists, framework versions, API contracts, scan tool versions) carries a `Last verified: YYYY-MM-DD` line and a `Recheck cadence:` line at the bottom.
6. **Status is explicit.** Each repo README shows one of: `Spec` · `Scaffolded` · `In build (Mx)` · `Beta` · `Production` · `Maintained` · `Archived`.
7. **N/A is declared, never silent** (§5). A standard that does not apply is written out with its reason.
8. **American English** in code and text alike, with three stated exceptions (§11).

---

## 7. How Claude Code should consume these docs

- **Start at `CLAUDE.md` and the README's Standards Conformance table.** Together they are the contract: scope, hard guardrails (the lines that must never be crossed), commands, the definition of done, and exactly which standards bind this repo. Agent-facing instructions live in `CLAUDE.md` (or `AGENTS.md`), never in a README section — the README is the visitor's front door (§9) [DOC-18].
- **Treat `docs/ROADMAP.md` § "Implementation Plan" as the work breakdown.** Execute phases in order. Do not begin a phase until the previous phase's acceptance criteria and merge-blocking metrics pass in CI.
- **Wire `RESPONSIBLE-TECH-AUDITS.md` checklists and the applicable `STANDARDS/` gates into CI at Phase 0**, not at the end. Audits that only happen at launch are theater. The guardrail tests (no-outing sentinels, grounding/citation guards, consent gate, no-identity-inference AST test) are the *first* CI jobs to land.
- **Read `STANDARDS/` from the pinned copy** (the CI-fetched `.standards/` checkout or the vendored copy, §1.1) — never re-derive a rule from memory. If a gate threshold is needed (coverage floor, faithfulness floor, Scorecard minimum), the standard is authoritative.
- **Record decisions as ADRs** (§3), not as roadmap edits. When the build makes a decision the roadmap didn't anticipate, open `docs/adr/NNNN-*.md`. Touching a guardrail, a `permissions:` block, or a threshold *requires* an ADR.
- **When the spec and reality conflict** (an API changed, a metric target is infeasible on the chosen tier, a standard's gate cannot pass on the chosen platform), stop and surface the conflict with a recommended resolution and a draft ADR — do not silently diverge.
- **Keep docs live.** Update `CHANGELOG.md` `Unreleased` in the same PR as the change. Bump `CITATION.cff` `version`/`date-released` on a release PR. Flip a conformance row from "gap tracked in #NN" to "Applies" in the PR that closes the gap.

---

## 8. Definition of "production-ready" (portfolio-wide)

A system is production-ready when, and only when:

1. All acceptance criteria in `ROADMAP.md` pass.
2. Every applicable AUTO-GATE across `STANDARDS/` is green on `main` (code quality, supply-chain, CI/CD, release, observability tier, performance where applicable, accessibility, i18n where applicable, AI-eval where applicable, incident-response label/postmortem hygiene, data governance where the repo holds data), and every REVIEW-GATE, including applicable AI-development measurement evidence, has its committed artifact.
3. Every merge-blocking gate in `QUALITY-AND-METRICS-STANDARD.md` is green on `main`.
4. Every applicable audit in `RESPONSIBLE-TECH-AUDITS.md` has a committed, passing, release-regenerated report.
5. The README Standards Conformance table (§5) has zero open-gap rows; every row is `Applies` or `N/A — reason`.
6. The supply-chain floor holds: all `uses:` SHA-pinned, OpenSSF Scorecard Pinned-Dependencies ≥ 9/10 and Token-Permissions = 10/10, SBOM + signing on release artifacts.
7. The doc set is complete and current: `README`, `docs/ROADMAP.md`, `docs/RESPONSIBLE-TECH-AUDITS.md`, `docs/adr/`, `docs/incidents/` (or declared N/A), `docs/data/` (or declared N/A), `CHANGELOG.md`, `CITATION.cff` (or declared N/A), `SECURITY.md`, `CONTRIBUTING.md`, all carrying valid currency stamps where required.
8. There is a runnable `make verify` (or equivalent) that reproduces 1–4 locally and in CI — byte-for-byte identical invocation to the CI job, eliminating local/remote drift.
9. There is an operations section a tired on-call human could follow at 2 a.m.

A release authorized provisionally by an owning domain standard is explicitly **not** “production-ready” or conformant under this definition. Its README, release notes, and audit artifact must identify the synthetic method, the open experiential gate, the maintainer's residual-risk acceptance, and the expiry/re-test trigger; accessibility uses `ACCESSIBILITY-STANDARD.md` §2.0.

A repository at `Spec` status is exempt from 1–9 except the requirement to vendor `STANDARDS/` and carry the ADR log skeleton; its ADR-0001 commits to scaffolding the standards before any feature code.

---

## 9. Audience register — a public README reads visitor-first

The README is the front door for a stranger, not a status report for the
operator. A buried quickstart, unexplained milestone codes, account or billing
state in the opening paragraph, or a section addressed to a coding agent are
all written for the wrong reader. These rules make the register mechanical:

| Requirement | What passes | Checked by | Gate |
|---|---|---|---|
| Visitor-first opening [DOC-17] | A quickstart-class heading (`Quickstart` / `Getting started` / `Install` / `Usage`) or a fenced command block appears within the README's first 60 lines | `conformance_check.py` `readme_quickstart` | AUTO-GATE |
| Agent contract lives in `CLAUDE.md` [DOC-18] | No README heading addressed to tooling ("For Claude Code", "For the agent", …); the agent entrypoint, commands, and definition of done live in `CLAUDE.md` or `AGENTS.md` (§7) | `conformance_check.py` `agent_docs_separated` | AUTO-GATE |
| No stale privacy assumptions [DOC-19] | A public repo's README / SECURITY.md / CONTRIBUTING.md / workflow comments never claim "private repo"; a repo flipped public sweeps these the same day | `conformance_check.py` `stale_private_refs` — runs only when visibility is confirmable, skips gracefully offline | AUTO-GATE |
| Front door carries no internal ops state [DOC-20] | No account billing/quota state, queue mechanics, or unexplained milestone codes in the README; deliberately-published working notes (ideation, research roadmaps, synthetic user research) open with a label saying exactly what they are | PR review + the quarterly DOC staleness pass | REVIEW-GATE |

Working-in-the-open is encouraged, not penalized: ideation logs, research
roadmaps, and synthetic user-research packets are welcome in a public repo —
labeled, and linked from the README as working notes rather than presented as
the front door.

## 10. Capability claims: claim, evidence, and explicit gap

Repos that make public safety, accessibility, civic-outcome, evidence-integrity,
or domain-fitness claims maintain `docs/capabilities.md` with the columns
Capability, Status, Current claim, Evidence, and Explicit gap. The ledger is
the current source of truth when a dated research, roadmap, or audit snapshot
differs from current implementation.

| Requirement | What passes | Checked by | Gate |
|---|---|---|---|
| Claim/evidence/gap ledger [DOC-21] | Every capability row uses the standard Shipped / Partial / Planned / Externally unvalidated vocabulary, states a bounded current claim, links repository-local evidence, and names the residual gap | `automation/check_claim_ledger.py`; human review decides whether the evidence actually supports the claim | AUTO+REVIEW |

The AUTO half checks shape and link existence; it does **not** infer that a test
proves a claim. The REVIEW half rejects overbroad wording, missing real-world
limits, and attempts to collapse automated evidence into legal, safety,
accessibility, or domain validation. External review stays visibly open until a
dated artifact records it.

## 11. Language: American English (en-US)

Every repository in this portfolio uses American English everywhere, in code and in
user-facing text (owner decision, 2026-09-18). One spelling per word is what lets a
search for `color` find every color, and a reader stop wondering whether `normalize()`
and a British-spelled twin are two functions.

**Scope.** Identifiers, comments and docstrings, UI and other user-facing strings
(including the English source strings of a translation catalog), documentation,
commit messages, and pull request titles and descriptions. Text in another language,
such as a Spanish catalog, is not English and is out of scope.

**Exceptions.** There are three:

- **(a) Proper nouns and quoted or verbatim third-party text.** Organization names
  ("Centre for …"), license titles ("Open Government Licence"), terms-of-service
  snapshots, and agency and place names in data keep the spelling their owner gave
  them. So does a third-party identifier quoted in code, such as the GitHub Actions
  `cancelled()` status function, or a URL. The prose around a quotation is still
  American English.
- **(b) Persisted or published identifiers.** Storage keys, database attributes,
  published schema fields, API routes and parameters, environment variables, CLI
  flags, and public package function names change only through a migration, a
  versioned contract, or a deprecated alias that keeps the old name working, and
  never by find-and-replace, which breaks every reader of the old name. Until that
  change ships, the old name is a recorded exception.
- **(c) Generated output.** It is fixed in its generator, never by hand, and the next
  run brings it into line. Exclude the output from the check and name its generator.

| Requirement | What passes | Checked by | Gate |
|---|---|---|---|
| American English [DOC-22] | Zero findings from codespell's builtin `en-GB_to_en-US` dictionary across the repository's tracked files, after the exceptions the repository records; commit messages and pull request text in American English | `conformance_check.py` `en_us_spelling` (`automation/spelling_controls.py`, tracked files); PR review (commit messages and PR text; published history is never rewritten to fix spelling) | AUTO+REVIEW (the AUTO half report-only through 2026-10-18, scored from 2026-10-19) |

**Rollout.** DOC-22 lands report-only, like every rule added on 2026-09-18. Through
2026-10-18 a finding appears in the conformance report's report-only table and as an
annotation in per-repo CI, and it moves no score and fails no build. From 2026-10-19
it is scored like any other control. The date lives in `automation/report_only.py`,
and extending it is a CHANGELOG entry with a reason, never a silent edit.

**How the check runs.** `conformance_check.py` lists the repository's tracked files
(`git ls-files`) and runs codespell `>=2.3` (the first release that honors an inline
`codespell:ignore`) over them. CI installs the release pinned by hash in
`automation/requirements-codespell.txt`. The flags:

```bash
codespell --builtin en-GB_to_en-US \
  --regex '[A-Z]?[a-z]+|[A-Z]+(?![a-z])' \
  --uri-ignore-words-list '*' --check-hidden -- <tracked files>
```

- `--regex` splits identifiers on case and `_`. codespell's default word pattern reads
  `snake_case_name` as one token and never looks up the words inside it, so without
  this flag a British spelling in an identifier passes.
- `--uri-ignore-words-list '*'` reads URLs and email addresses as third-party
  identifiers (exception a).
- `--check-hidden` reads files whose name starts with a dot, such as
  `.pre-commit-config.yaml`, which codespell otherwise skips even when they are named
  on its command line. A file inside `.github/` named on the command line is read
  either way; codespell skips that directory only when it walks a directory.

A run that could not have failed is a failure, never a pass: no codespell, no git work
tree, no tracked files, a codespell exit other than 0 or 65, or a canary file of
British spellings, passed alongside the repository's files, that codespell did not
report. The canary catches a stub on `PATH` and an exceptions file that skips
everything. To reproduce the check locally:

```bash
git ls-files -z -- . ':!.codespellrc' | xargs -0 codespell --builtin en-GB_to_en-US \
  --regex '[A-Z]?[a-z]+|[A-Z]+(?![a-z])' --uri-ignore-words-list '*' --check-hidden --
```

**Recording an exception.** Exceptions live in the repository's `.codespellrc`, which
codespell reads on its own and the check never scans. The check passes the dictionary
and the word pattern on its command line, so the file can record exceptions but cannot
swap either one. Every entry names the exception, (a), (b) or (c), that
it falls under. Use the narrowest mechanism that fits:

| Mechanism | Use it for | Example |
|---|---|---|
| Inline `codespell:ignore <word>` comment | One quoted line or test fixture | `assert parse("colour") == "color"  # codespell:ignore colour` |
| `ignore-regex` | A proper noun or third-party identifier that recurs. It covers the phrase, so the bare word still fails | `ignore-regex = Open Government Licence` |
| `skip` (globs over paths as `git ls-files` prints them) | Generated output (name the generator), lockfiles, vendored copies, data files that quote third-party names, catalogs in another language | `skip = data/raw/*,uv.lock` |
| `ignore-words-list` | Last resort: it exempts the word everywhere in the repository | — |

A `.codespellrc` that sets `write-changes` is refused: the check never rewrites the
tree. A repository that vendors `STANDARDS/` (§1.1) cannot edit that text (DOC-03), so
it skips the vendored directory. That text is checked here, where it is written, and a
re-vendor delivers each fix.

---

Last verified: 2026-06-21 · Recheck cadence: per major framework change, on any `STANDARDS/` minor-version bump, or quarterly — whichever is first.
