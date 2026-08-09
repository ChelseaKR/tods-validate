# Release & Versioning Standard

This is the canonical definition of **how a repo cuts a release and how it numbers one**. It owns the *process and policy*: SemVer rules, the public-API contract, tag and CHANGELOG discipline, the trusted-main release pipeline, and Trusted Publishing. The cryptographic *machinery* a release invokes — SBOM generation, cosign signing, SLSA provenance, OpenSSF Scorecard — lives in `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §6 and is referenced here, not restated. CI hardening of the release job (token scope, OIDC, concurrency, cache rules) lives in `CI-CD-STANDARD.md`. Reference, don't repeat.

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge- or tag-blocking in CI; no `|| true`, no `continue-on-error`) or **REVIEW-GATE** (accountable human judgment, paired with a checklist line and a dated durable artifact—committed by default, authenticated release metadata only where an owning standard explicitly requires it). There is no aspirational third category. OIDC Trusted Publishing and SLSA-attested releases are established mechanisms; repository-specific adoption evidence lives in the private remediation registry.

An owning domain standard may authorize a narrowly scoped, truth-labeled **provisional release** from synthetic evidence plus maintainer residual-risk acceptance while an experiential REVIEW-GATE remains open. This changes release disposition only: it does not satisfy or reclassify the gate, establish conformance, or create a third gate type. Accessibility's bounded pathway is defined in `ACCESSIBILITY-STANDARD.md` §2.0.

---

## 1. When this standard applies

| Repo class | Produces a release? | Examples |
|---|---|---|
| Published library / package (PyPI, npm) | **Yes — mandatory** | reusable Python or JavaScript package |
| Deployed service / app (container or hosted) | **Yes** — the deployed artifact is the release | API, worker, frontend, or local app distributed to users |
| Reference/starter kit consumed by copy | **Yes** — versioned so consumers can pin | templates, policy kits, or sample datasets |
| Pure internal tool, never consumed downstream | `N/A (not consumed downstream)` with that exact reason in the README | an operator-only utility with no released artifact |

**There is no silent default.** A repository with no release pipeline and no `N/A (reason)` declaration **fails review**. Current exceptions and remediation status are tracked privately.

A repo that publishes to PyPI **always** produces a release — "library, so no release" is a contradiction, not an exemption.

---

## 2. Versioning policy — SemVer 2.0.0

Every release-producing repo uses **[SemVer 2.0.0](https://semver.org/)**: `MAJOR.MINOR.PATCH`, with `MAJOR` for breaking changes, `MINOR` for backward-compatible additions, `PATCH` for backward-compatible fixes.

| Rule | Requirement | Gate |
|---|---|---|
| Single source of version truth [REL-02] | Version lives in exactly one place (`pyproject.toml` `project.version` or `package.json` `version`); package `__version__` derives from it (`importlib.metadata.version` / build-time inject), never hand-copied | AUTO-GATE (duplicate-version-string check) |
| Tag ⇔ metadata consistency [REL-03] | The git tag, the `pyproject`/`package.json` version, and the published artifact version are **identical** at release time | AUTO-GATE (version-consistency check, §4) |
| Public API is declared [REL-04] | Each library's `README`/`docs` names what *is* the public API (the SemVer contract surface) — everything else is private and may change without a major bump | REVIEW-GATE |
| Pre-1.0 (`0.y.z`) [REL-05] | Allowed, but the repo states its 0ver intent: `MINOR` may break. Graduate to `1.0.0` when the public API is stable. A library at `0.y.z` for >12 months with external users is a review finding | REVIEW-GATE |
| Breaking change ⇒ MAJOR + migration note [REL-06] | Any breaking change to the declared public API bumps `MAJOR` and ships a migration note in the CHANGELOG | REVIEW-GATE; AUTO-GATE assist via API-diff (`griffe` for Python, `api-extractor`/`are-the-types-wrong` for TS) flagging removed/changed public symbols |
| No re-publish of a version [REL-07] | A published `X.Y.Z` is immutable; defects are fixed forward in `X.Y.(Z+1)`. Yanking (§7) removes availability but never reuses the number | AUTO-GATE (registry rejects; tag is protected) |

**Data products** additionally version their **schema/dataset** independently of the code: a `data-vN` tag or a `dataset_version` field. This standard owns that tagging mechanism; the policy it serves — dataset-version immutability, the data card recording source/license/fetch-timestamp/refresh-cadence, and the retention line — is owned by `DATA-GOVERNANCE-STANDARD.md` §1 and §5.

### Calendar versioning (`CalVer`) — when permitted
A repo whose value is "the state of the world on a date" (a periodically-regenerated dataset, a snapshot site) **may** use `YYYY.MM.DD` CalVer instead of SemVer, but must declare it and still satisfy every tag/CHANGELOG/provenance gate below. Default is SemVer; CalVer is opt-in with a one-line rationale.

---

## 3. Tags & CHANGELOG

### 3.1 Tags — annotated, signed, immutable — AUTO-GATE
- Format `vX.Y.Z` (the `v` prefix; CalVer repos use `vYYYY.MM.DD`).
- **Annotated and signed.** Use a signed git tag (`git tag -s`) or Sigstore **gitsign** (keyless, OIDC identity — preferred, no long-lived GPG key to manage). An unsigned release tag fails the release job.
- Normally the tag points at the **exact commit** that was tested and built. The only declared split
  is §4.2: an accessibility evidence-bearing tag **E** promotes the attested artifact built from
  tested protected-main source **P**, and records both identities. No re-tagging or force-push to a
  release tag — release tags are covered by a branch/tag protection ruleset (`CI-CD-STANDARD.md`).
- Tag is created **only** on `main` after all merge gates are green.
- A committed repository-owned `.github/rulesets/tags.json` named
  `protect-release-tags` targets exactly `refs/tags/v*`, restricts **all updates** and deletions,
  and has no bypass actors. `non_fast_forward` alone is insufficient because it can still permit a
  fast-forward tag move. Before tag creation, the read-only validator compares hosted state with that
  profile; the SSH-signed tag message binds the hosted ruleset ID, `updated_at`, and the accountable
  owner's empty-bypass declaration. The release fails closed if the ruleset is missing, changed, or
  does not match the signed assertion.

```bash
# keyless signed tag via gitsign (preferred — no GPG key management)
git tag -s v1.4.0 -m "v1.4.0"
git push origin v1.4.0
gh workflow run release.yml --ref main -f tag=v1.4.0  # trusted-main release (§4)
```

### 3.2 CHANGELOG — Keep a Changelog 1.1.0 — AUTO-GATE on presence, REVIEW-GATE on quality
Every release-producing repo keeps a `CHANGELOG.md` in **[Keep a Changelog 1.1.0](https://keepachangelog.com/)** format with an `## [Unreleased]` section, reverse-chronological entries, and `Added/Changed/Deprecated/Removed/Fixed/Security` groupings. SemVer links at the bottom.

| Control | Requirement | Gate |
|---|---|---|
| CHANGELOG exists & parses [REL-09] | File present, parseable, has `Unreleased` | AUTO-GATE |
| Released version has an entry [REL-10] | The tag being released has a matching `## [X.Y.Z] - YYYY-MM-DD` section (no empty releases) | AUTO-GATE (release job greps for the version heading; fails if absent) |
| Security fixes are called out [REL-11] | Any release closing a CVE/advisory has a `Security` entry referencing the advisory | REVIEW-GATE |
| Entry is human-meaningful [REL-12] | Describes user-visible impact, not commit subjects | REVIEW-GATE |

Conventional Commits + an automated changelog generator (`git-cliff`, `release-please`) is **permitted and encouraged** to draft entries, but a human curates the released section — generated commit dumps are not a changelog.

---

## 4. The release pipeline (trusted-main, signed-tag selected)

After pushing a canonical `vX.Y.Z` signed tag, the maintainer dispatches the release workflow from
the default branch and supplies that tag as an input. `workflow_dispatch` is used deliberately: a
tag-push workflow executes the workflow definition stored at the tagged ref, while the release
authority must come from the reviewed workflow on trusted `main`. The workflow rejects dispatch from
any other ref, a non-SemVer tag, an unsigned/untrusted tag, a tag whose commit is not reachable
from current `origin/main`, or a tag whose hosted immutable-ruleset binding is absent/stale. Every
stage is AUTO-GATE unless marked; a red stage aborts before
anything is published.

```
on:
  workflow_dispatch:
    inputs:
      tag: {required: true, type: string}
permissions: contents: read          # escalate per-job only (CI-CD-STANDARD §token model)

0. trust                 dispatch ref == main; tag signed by main's allowed signer; tag target ∈ main
1. version-consistency   tag == pyproject/package version == __version__   → fail on mismatch
2. re-run make verify    full lint+type+test+coverage+security AT THE TAGGED COMMIT (never trust the PR run)
3. build                 reproducible build; deterministic artifact (uv build / vite build)
4. SBOM                  CycloneDX 1.7 generated + schema-validated      → SECURITY §6.2
5. sign + attest         cosign sign + SLSA provenance (keyless, OIDC)   → SECURITY §6.4
6. publish               separate checkout-free write job: registry / GHCR / GitHub Release
7. GitHub Release        attach SBOM + provenance + CHANGELOG section as release notes
8. verify-published      pull the published artifact, verify signature + provenance end-to-end
```

Non-negotiables (cross-referenced, enforced here):
- **Caching is disabled** in any job that builds, signs, or publishes — cache poisoning violates SLSA build isolation (`CI-CD-STANDARD.md`; validated by the Feb 2026 cache-poisoning campaign against Microsoft/DataDog/CNCF repos).
- **One global concurrency group** on the release workflow so two versions cannot publish concurrently.
- **Split authority:** verification checks out and executes the tagged code with `contents: read`;
  the dependent publish job receives `contents: write` but never checks out or executes repository
  code.
- The release job re-runs `make verify` at the **tagged commit** — it does not reuse the PR's green checkmark. This closes the "main drifted after the PR passed" hole.
- **OIDC only.** No long-lived PyPI/registry tokens stored as secrets. A new long-lived publish secret appearing in repo settings is an audit-log alarm (`SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §7).

### 4.1 Shared release authorization

Repositories SHOULD call the standards-owned
`.github/workflows/release-authorize.yml` at a full 40-character commit SHA for
step 0. The reusable workflow checks out the caller's reviewed `main`, rejects
non-stable or lightweight tags, verifies the SSH signer against the caller's
committed `.github/allowed_signers`, proves the selected commit is reachable
from current `origin/main`, and returns the release commit, tag, and annotated
tag-object SHA.

The caller still owns every product-specific step: version/changelog parity,
`make verify`, exact-commit builds, SBOM and provenance, registry publication,
and post-publication verification. Its write-authorized publication job MUST
remain checkout-free and MUST compare the live tag-object SHA with the
authorizer output immediately before publishing. Pinning the reusable workflow
to a branch or moving tag is non-conformant.

### 4.2 Evidence-only release head for a provisional accessibility release

`ACCESSIBILITY-STANDARD.md` §2.0 uses a two-phase build/evidence relationship so a committed evidence
record does not need to contain its own commit hash:

1. Merge the product change normally. The resulting protected-`main` source commit **P** is fully
   verified and produces immutable artifact **A** with digest **G**.
2. The release head/tag **E** adds only the validated current evidence record that names **P** and
   **G**, through a separate evidence-only PR using the repository's normal linear-history merge
   method. `make verify` still reruns at **E**, including repository-binding validation that **P** is
   an ancestor and the net `P..E` change contains exactly that one added record. At the current open
   evidence-PR head, the canonical validator runs with
   `--release-validation --artifact A --attestation-bundle B`; `--structure-only` and bare
   artifact/bundle flags are prohibited. That qualifying mode validates the current solo-governance
   declaration, authenticated current-head owner attestation, exact owner/repository parity, and
   hosted protect-main identity/no-bypass and sole-collaborator proof.
3. After **E** merges, create the separate decision-only descendant **D** required by
   `CI-CD-STANDARD.md` §8a. Its full **P→E→D** gate rechecks the exact artifact and deployment
   authorization; the synthetic validator remains scoped to **E** and is not weakened to accept **D**
   in `P..HEAD`.
4. Only after **D** passes does the release job retrieve **A**, verify **G**, and promote that exact
   artifact. It does not rebuild or relabel **A** as though it came from **E** or **D**. The tag/release
   may select **E**, while **D** remains the durable deployment authorization on `main`.
5. Provenance and release metadata record all three commit identities: **P** is the build source,
   **E** is the evidence-bearing release head, and **D** is the deployment decision. Published-artifact
   verification recomputes **G** after promotion.

Every policy, test, public-status, application, dependency, locale, data, and deployable-surface change
must already be in **P**. Any other `P..E` change, missing ancestry, digest mismatch, or build from **E**
blocks release. REL-13, REL-14, REL-16, and REL-19 remain AUTO/REVIEW gates; this section changes only
which already-verified artifact is promoted and makes its provenance more explicit.

---

## 5. Publishing channels

### 5.1 PyPI — Trusted Publishing (OIDC) — AUTO-GATE
Python packages publish via **[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)** using the workflow's OIDC identity through `pypa/gh-action-pypi-publish`. **No API token is ever stored.** A repository publishing to PyPI with a stored `PYPI_API_TOKEN` secret is a finding and must migrate.

```yaml
publish:
  environment: pypi            # required-reviewer gate (CI-CD-STANDARD §environments)
  permissions:
    id-token: write            # OIDC — the only credential
  steps:
    - uses: pypa/gh-action-pypi-publish@<40-char-sha>   # release/v1.x
```

### 5.2 Containers — GHCR, versioned + signed
Images publish to GHCR tagged with the **immutable digest** plus `vX.Y.Z` and `X.Y` moving tags. The deployed reference is the **digest**, never `:latest`. An image is cosign-signed and Trivy-scanned (`CRITICAL,HIGH` blocking) before the digest is promoted — see `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §3/§6. This applies to every repository with a `Dockerfile`.

### 5.3 Deployed apps / frontends
A deployed frontend releases a **versioned, provenance-attested build artifact** mapped to the git tag. Requirements: build provenance via `actions/attest-build-provenance`; source maps generated but access-controlled (not served publicly for repositories handling sensitive flows); the deployed version surfaced at a `/version` endpoint or build-stamped meta tag so a running deployment is traceable to a commit (ties to `OBSERVABILITY-STANDARD.md`). A §4.2 provisional release maps the tag to both the tested-source commit and evidence-bearing release head and promotes the tested artifact by digest; it never misstates which commit produced the bytes.

---

## 6. Release artifacts committed/attached — REVIEW-GATE on completeness

Each release attaches (to the GitHub Release) and, where regenerated, commits:

1. **SBOM** (`*.cdx.json`) — CycloneDX 1.7.
2. **Provenance** (`*.intoto.jsonl`) — SLSA L2 minimum, L3 for public packages.
3. **CHANGELOG section** as the release notes.
4. **AI/RAG repos additionally:** the regenerated **model card** + **data card** and the eval-run report for the released version (`AI-EVALUATION-STANDARD.md`) — a model's release is not complete without its current eval evidence.
5. **L2 PII repos:** confirmation the residual-risk register is current as of the tag (`RESPONSIBLE-TECH-FRAMEWORK.md` §F).
6. **Any domain-authorized provisional release:** the synthetic-evidence record, maintainer residual-risk acceptance, open experiential gate, and expiry/re-test trigger; for accessibility, that record is a provisional status report instead of a new-version ACR and follows `ACCESSIBILITY-STANDARD.md` §2.0.

This is the same "audit as committed build artifact" principle as the responsible-tech reports: the release evidence lives *in* the repo/release, not in a person's memory.

---

## 7. Deprecation, yank, and security releases

| Situation | Policy | Gate |
|---|---|---|
| Deprecating a public API [REL-21] | Mark deprecated in the release that introduces the replacement; keep ≥1 MINOR cycle (libraries: ≥1 MAJOR) with a runtime `DeprecationWarning`; document in CHANGELOG `Deprecated` | REVIEW-GATE |
| Yanking a bad release [REL-22] | Yank on the registry (PyPI yank / `npm deprecate`); never delete (consumers with pins must still resolve); ship the fix as a new PATCH; CHANGELOG `Security`/`Fixed` note | REVIEW-GATE + AUTO-GATE (no version reuse) |
| Security release (CVE) [REL-23] | Fix forward; if supported older majors exist, backport to each; publish within the disclosure SLA in `SECURITY.md`; reference the advisory (GHSA) in the CHANGELOG `Security` entry and the release notes | REVIEW-GATE |
| Supported-version policy [REL-24] | The README states which majors receive security fixes (default: latest major only for pre-1.0 portfolio repos) | REVIEW-GATE |

---

## 8. Adoption paths

| Starting condition | Action |
|---|---|
| Package published with a stored token | Migrate to OIDC Trusted Publishing and add version-consistency and CHANGELOG gates |
| Container deployed by a moving tag | Sign, attest, scan, and promote the immutable digest |
| Frontend deployed without a versioned artifact | Add provenance, a versioned build artifact, and a `/version` stamp |
| Artifact-producing repository with no release workflow | Scaffold `release.yml` and `CHANGELOG.md` or declare `N/A (reason)` |
| Data product | Adopt dataset versioning (§2) and the standard release gates |
| Not-yet-implemented tool | Land the release pipeline with its initial CI scaffold before feature delivery |

The private remediation registry records which repositories occupy each path
and their current state.

---

## 9. Metrics ledger (per release-producing repo)

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Tag ⇔ version consistency [REL-03] | exact match | version-check step in `release.yml` | AUTO-GATE |
| Released version in CHANGELOG [REL-10] | present, dated | grep for `[X.Y.Z]` heading | AUTO-GATE |
| Signed release tag [REL-08] | 100% of releases | gitsign/`git tag -v` verification | AUTO-GATE |
| Publish credential [REL-17] | OIDC, zero stored tokens | secret-inventory audit | AUTO-GATE |
| `make verify` re-run at tag [REL-14] | green at tagged commit | release job stage 2 | AUTO-GATE |
| SBOM + provenance attached [REL-20] | every release | release assets present + `slsa-verifier` | AUTO-GATE |
| End-to-end verify of published artifact [REL-16] | passes | stage 8 pull-and-verify | AUTO-GATE |
| Public-API SemVer correctness [REL-06] | no undeclared breaking change in MINOR/PATCH | `griffe`/`api-extractor` diff + human review | REVIEW-GATE |
| Migration note on MAJOR [REL-06] | present | release review | REVIEW-GATE |

---

Last verified: 2026-06-21 · Recheck cadence: per SemVer, Keep a Changelog, PyPI Trusted Publishing, SLSA, and Sigstore release; and immediately on any disclosed registry or GitHub Actions supply-chain compromise. Confirm current action versions (`gh-action-pypi-publish`, `attest-build-provenance`, gitsign) at build time.
