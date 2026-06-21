# Release & Versioning Standard

This is the canonical definition of **how a repo cuts a release and how it numbers one**. It owns the *process and policy*: SemVer rules, the public-API contract, tag and CHANGELOG discipline, the tag-triggered release pipeline, and Trusted Publishing. The cryptographic *machinery* a release invokes — SBOM generation, cosign signing, SLSA provenance, OpenSSF Scorecard — lives in `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §6 and is referenced here, not restated. CI hardening of the release job (token scope, OIDC, concurrency, cache rules) lives in `CI-CD-STANDARD.md`. Reference, don't repeat.

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge- or tag-blocking in CI; no `|| true`, no `continue-on-error`) or **REVIEW-GATE** (human judgment, paired with a checklist line and a committed, dated artifact). There is no aspirational third category. The portfolio already proves this is achievable: `civic-ai-eval-harness`/`govchat-eval` ship the full OIDC-Trusted-Publishing + SLSA-attested release today. The work is propagation, not invention.

---

## 1. When this standard applies

| Repo class | Produces a release? | Examples |
|---|---|---|
| Published library / package (PyPI, npm) | **Yes — mandatory** | `civic-ai-eval-harness` (`govchat-eval` on PyPI), `civic-rag-starter-kit`, `nearmiss`, `tods-validate`, `swelter`, `ledger` |
| Deployed service / app (container or hosted) | **Yes** — the deployed artifact is the release | `trans-docs-navigator`, `davis-bike-hazard-map`, `personal-site`, `fare-assistant`, `olive-bark-logger`, `queer-the-stacks` |
| Reference/starter kit consumed by copy | **Yes** — versioned so consumers can pin | `civic-rag-starter-kit` |
| Pure internal tool, never consumed downstream | `N/A (not consumed downstream)` with that exact reason in the README | rare — most repos are consumed by *something* |

**There is no silent default.** A repo with no release pipeline and no `N/A (reason)` declaration **fails review**. This explicitly closes the current gap in `civic-rag-starter-kit`, `ledger`, `olive-bark-logger`, and `queer-the-stacks`, which produce artifacts but ship no release workflow or CHANGELOG.

A repo that publishes to PyPI **always** produces a release — "library, so no release" is a contradiction, not an exemption.

---

## 2. Versioning policy — SemVer 2.0.0

Every release-producing repo uses **[SemVer 2.0.0](https://semver.org/)**: `MAJOR.MINOR.PATCH`, with `MAJOR` for breaking changes, `MINOR` for backward-compatible additions, `PATCH` for backward-compatible fixes.

| Rule | Requirement | Gate |
|---|---|---|
| Single source of version truth | Version lives in exactly one place (`pyproject.toml` `project.version` or `package.json` `version`); package `__version__` derives from it (`importlib.metadata.version` / build-time inject), never hand-copied | AUTO-GATE (duplicate-version-string check) |
| Tag ⇔ metadata consistency | The git tag, the `pyproject`/`package.json` version, and the published artifact version are **identical** at release time | AUTO-GATE (version-consistency check, §4) |
| Public API is declared | Each library's `README`/`docs` names what *is* the public API (the SemVer contract surface) — everything else is private and may change without a major bump | REVIEW-GATE |
| Pre-1.0 (`0.y.z`) | Allowed, but the repo states its 0ver intent: `MINOR` may break. Graduate to `1.0.0` when the public API is stable. A library at `0.y.z` for >12 months with external users is a review finding | REVIEW-GATE |
| Breaking change ⇒ MAJOR + migration note | Any breaking change to the declared public API bumps `MAJOR` and ships a migration note in the CHANGELOG | REVIEW-GATE; AUTO-GATE assist via API-diff (`griffe` for Python, `api-extractor`/`are-the-types-wrong` for TS) flagging removed/changed public symbols |
| No re-publish of a version | A published `X.Y.Z` is immutable; defects are fixed forward in `X.Y.(Z+1)`. Yanking (§7) removes availability but never reuses the number | AUTO-GATE (registry rejects; tag is protected) |

**Data products** (`gtfs-scorecard`, `tods-validate`, transit datasets) additionally version their **schema/dataset** independently of the code: a `data-vN` tag or a `dataset_version` field, with a data card recording source, fetch timestamp, and refresh cadence (see `QUALITY-AND-METRICS-STANDARD.md` §Data quality).

### Calendar versioning (`CalVer`) — when permitted
A repo whose value is "the state of the world on a date" (a periodically-regenerated dataset, a snapshot site) **may** use `YYYY.MM.DD` CalVer instead of SemVer, but must declare it and still satisfy every tag/CHANGELOG/provenance gate below. Default is SemVer; CalVer is opt-in with a one-line rationale.

---

## 3. Tags & CHANGELOG

### 3.1 Tags — annotated, signed, immutable — AUTO-GATE
- Format `vX.Y.Z` (the `v` prefix; CalVer repos use `vYYYY.MM.DD`).
- **Annotated and signed.** Use a signed git tag (`git tag -s`) or Sigstore **gitsign** (keyless, OIDC identity — preferred, no long-lived GPG key to manage). An unsigned release tag fails the release job.
- The tag points at the **exact commit** that was tested and built. No re-tagging, no force-push to a release tag — release tags are covered by a branch/tag protection ruleset (`CI-CD-STANDARD.md`).
- Tag is created **only** on `main` after all merge gates are green.

```bash
# keyless signed tag via gitsign (preferred — no GPG key management)
git tag -s v1.4.0 -m "v1.4.0"
git push origin v1.4.0    # triggers the release workflow (§4)
```

### 3.2 CHANGELOG — Keep a Changelog 1.1.0 — AUTO-GATE on presence, REVIEW-GATE on quality
Every release-producing repo keeps a `CHANGELOG.md` in **[Keep a Changelog 1.1.0](https://keepachangelog.com/)** format with an `## [Unreleased]` section, reverse-chronological entries, and `Added/Changed/Deprecated/Removed/Fixed/Security` groupings. SemVer links at the bottom.

| Control | Requirement | Gate |
|---|---|---|
| CHANGELOG exists & parses | File present, parseable, has `Unreleased` | AUTO-GATE |
| Released version has an entry | The tag being released has a matching `## [X.Y.Z] - YYYY-MM-DD` section (no empty releases) | AUTO-GATE (release job greps for the version heading; fails if absent) |
| Security fixes are called out | Any release closing a CVE/advisory has a `Security` entry referencing the advisory | REVIEW-GATE |
| Entry is human-meaningful | Describes user-visible impact, not commit subjects | REVIEW-GATE |

Conventional Commits + an automated changelog generator (`git-cliff`, `release-please`) is **permitted and encouraged** to draft entries, but a human curates the released section — generated commit dumps are not a changelog.

---

## 4. The release pipeline (tag-triggered)

A push of a `vX.Y.Z` tag triggers a single hardened release workflow. Every stage is AUTO-GATE unless marked; a red stage aborts the release before anything is published.

```
on: push: tags: ['v*']
permissions: contents: read          # escalate per-job only (CI-CD-STANDARD §token model)

1. version-consistency   tag == pyproject/package version == __version__   → fail on mismatch
2. re-run make verify    full lint+type+test+coverage+security AT THE TAGGED COMMIT (never trust the PR run)
3. build                 reproducible build; deterministic artifact (uv build / vite build)
4. SBOM                  CycloneDX 1.7 generated + schema-validated      → SECURITY §6.2
5. sign + attest         cosign sign + SLSA provenance (keyless, OIDC)   → SECURITY §6.4
6. publish               Trusted Publishing (§5) / GHCR / GitHub Release
7. GitHub Release        attach SBOM + provenance + CHANGELOG section as release notes
8. verify-published      pull the published artifact, verify signature + provenance end-to-end
```

Non-negotiables (cross-referenced, enforced here):
- **Caching is disabled** in any job that builds, signs, or publishes — cache poisoning violates SLSA build isolation (`CI-CD-STANDARD.md`; validated by the Feb 2026 cache-poisoning campaign against Microsoft/DataDog/CNCF repos).
- **Concurrency group** on the release workflow so two tags can't publish simultaneously.
- The release job re-runs `make verify` at the **tagged commit** — it does not reuse the PR's green checkmark. This closes the "main drifted after the PR passed" hole.
- **OIDC only.** No long-lived PyPI/registry tokens stored as secrets. A new long-lived publish secret appearing in repo settings is an audit-log alarm (`SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §7).

---

## 5. Publishing channels

### 5.1 PyPI — Trusted Publishing (OIDC) — AUTO-GATE
Python packages publish via **[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)** using the workflow's OIDC identity through `pypa/gh-action-pypi-publish`. **No API token is ever stored.** A repo publishing to PyPI with a stored `PYPI_API_TOKEN` secret is a finding — migrate it. `govchat-eval` already does this; propagate to every PyPI repo.

```yaml
publish:
  environment: pypi            # required-reviewer gate (CI-CD-STANDARD §environments)
  permissions:
    id-token: write            # OIDC — the only credential
  steps:
    - uses: pypa/gh-action-pypi-publish@<40-char-sha>   # release/v1.x
```

### 5.2 Containers — GHCR, versioned + signed
Images publish to GHCR tagged with the **immutable digest** plus `vX.Y.Z` and `X.Y` moving tags. The deployed reference is the **digest**, never `:latest`. Image is cosign-signed and Trivy-scanned (`CRITICAL,HIGH` blocking) before the digest is promoted — see `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §3/§6. Applies to every repo with a `Dockerfile` (`trans-docs-navigator`, `olive-bark-logger`, `queer-the-stacks`, `civic-rag-starter-kit`, `davis-bike-hazard-map`, the eval harnesses).

### 5.3 Deployed apps / frontends
`personal-site`, `davis-bike-hazard-map` (PWA), and the `trans-docs-navigator` frontend release a **versioned, provenance-attested build artifact** mapped to the git tag. Requirements: build provenance via `actions/attest-build-provenance`; source maps generated but access-controlled (not served publicly for repos handling sensitive flows); the deployed version surfaced at a `/version` endpoint or build-stamped meta tag so a running deployment is traceable to a commit (ties to `OBSERVABILITY-STANDARD.md`).

---

## 6. Release artifacts committed/attached — REVIEW-GATE on completeness

Each release attaches (to the GitHub Release) and, where regenerated, commits:

1. **SBOM** (`*.cdx.json`) — CycloneDX 1.7.
2. **Provenance** (`*.intoto.jsonl`) — SLSA L2 minimum, L3 for public packages.
3. **CHANGELOG section** as the release notes.
4. **AI/RAG repos additionally:** the regenerated **model card** + **data card** and the eval-run report for the released version (`AI-EVALUATION-STANDARD.md`) — a model's release is not complete without its current eval evidence.
5. **L2 PII repos:** confirmation the residual-risk register is current as of the tag (`RESPONSIBLE-TECH-FRAMEWORK.md` §F).

This is the same "audit as committed build artifact" principle as the responsible-tech reports: the release evidence lives *in* the repo/release, not in a person's memory.

---

## 7. Deprecation, yank, and security releases

| Situation | Policy | Gate |
|---|---|---|
| Deprecating a public API | Mark deprecated in the release that introduces the replacement; keep ≥1 MINOR cycle (libraries: ≥1 MAJOR) with a runtime `DeprecationWarning`; document in CHANGELOG `Deprecated` | REVIEW-GATE |
| Yanking a bad release | Yank on the registry (PyPI yank / `npm deprecate`); never delete (consumers with pins must still resolve); ship the fix as a new PATCH; CHANGELOG `Security`/`Fixed` note | REVIEW-GATE + AUTO-GATE (no version reuse) |
| Security release (CVE) | Fix forward; if supported older majors exist, backport to each; publish within the disclosure SLA in `SECURITY.md`; reference the advisory (GHSA) in the CHANGELOG `Security` entry and the release notes | REVIEW-GATE |
| Supported-version policy | The README states which majors receive security fixes (default: latest major only for pre-1.0 portfolio repos) | REVIEW-GATE |

---

## 8. Per-repo posture (current state → target)

| Repo | Today | Action |
|---|---|---|
| `civic-ai-eval-harness` / `govchat-eval` | Full OIDC Trusted Publishing + SLSA attestation + version-check | **Reference implementation** — lift its `release.yml` into the others |
| `swelter`, `nearmiss`, `tods-validate` | SBOM/signing present, release maturity varies | Add version-consistency + CHANGELOG-entry gates; confirm Trusted Publishing |
| `trans-docs-navigator` | Strong supply-chain posture, deployed app | Add `/version` stamp; ensure tag-triggered provenance on the deployed build |
| `civic-rag-starter-kit`, `ledger`, `olive-bark-logger`, `queer-the-stacks` | **No release workflow / CHANGELOG** | **Primary gap** — scaffold `release.yml` + `CHANGELOG.md` from the reference repo |
| `davis-bike-hazard-map`, `personal-site` | Frontend builds, no versioned release artifact | Add build-provenance + versioned artifact + `/version` |
| `fare-assistant`, `women-artist-discovery`, `habitable`, `jobradar` | Mixed | Declare release-or-`N/A(reason)`; adopt the pipeline if consumed |
| `gtfs-scorecard` | Data product | Adopt dataset versioning (§2) + the standard release gates |
| `self-osint-monitor` | Spec-only, no CI | Release pipeline lands with its M0 CI scaffold, not before M1 |

---

## 9. Metrics ledger (per release-producing repo)

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Tag ⇔ version consistency | exact match | version-check step in `release.yml` | AUTO-GATE |
| Released version in CHANGELOG | present, dated | grep for `[X.Y.Z]` heading | AUTO-GATE |
| Signed release tag | 100% of releases | gitsign/`git tag -v` verification | AUTO-GATE |
| Publish credential | OIDC, zero stored tokens | secret-inventory audit | AUTO-GATE |
| `make verify` re-run at tag | green at tagged commit | release job stage 2 | AUTO-GATE |
| SBOM + provenance attached | every release | release assets present + `slsa-verifier` | AUTO-GATE |
| End-to-end verify of published artifact | passes | stage 8 pull-and-verify | AUTO-GATE |
| Public-API SemVer correctness | no undeclared breaking change in MINOR/PATCH | `griffe`/`api-extractor` diff + human review | REVIEW-GATE |
| Migration note on MAJOR | present | release review | REVIEW-GATE |

---

Last verified: 2026-06-21 · Recheck cadence: per SemVer, Keep a Changelog, PyPI Trusted Publishing, SLSA, and Sigstore release; and immediately on any disclosed registry or GitHub Actions supply-chain compromise. Confirm current action versions (`gh-action-pypi-publish`, `attest-build-provenance`, gitsign) at build time.
