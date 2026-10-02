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
| A declared version names a release that exists [REL-28] | Every version the repository declares — `pyproject.toml` `[project].version`, `package.json` `version`, `CITATION.cff` `version` — is named by a tag that exists. A repository carrying **no** release tag at all is pre-release and exempt; a repository that has released and declares a version none of its tags names is publishing a number with no artifact behind it | AUTO-GATE (declared-version check, `automation/check_declared_version.py`) |

**Why REL-28 is separate from REL-03.** REL-03 asserts that the tag, the package metadata and the published artifact agree *at release time* — inside the release job, which runs only when a release is actually being cut. Nothing asked the question in the other direction, on an ordinary day: does the version this repository declares name a release that exists at all? Measured across the portfolio on 2026-09-06, **twenty public repositories declared a version in `pyproject.toml` that nothing was ever tagged for**, and one of them dated that never-cut release in `CITATION.cff`, which is what downstream indexes and academic citations permanently record. A version number is a claim; REL-03 checks the claim only in the one moment it is guaranteed true.

**The gate does not fail all twenty, and saying so is the point.** Most of them have never tagged anything at all: nothing has been released, so the declared number is a starting point rather than a claim, and this gate passes them and says which state it put them in. The failures are the smaller subset that *has* released before — three repositories on the day this was written — where a version that no tag names is a claim about a release that did not happen. A gate that failed all twenty would be measuring "has not released yet", which is not a defect.

The gate must separate three states that look identical from a distance, and the separation is the control:

| Observed | State | Disposition |
|---|---|---|
| A version is declared and the repository has **no release tag at all** | pre-release | Pass. Nothing has been released, so the number is a starting point, not a claim. `--require-release` inverts this for a repository that declares itself release-producing (REL-01). |
| A version is declared, release tags **exist**, none names it, and it is **ahead** of them | defect | Fail. A version number with no artifact behind it. Fix by cutting and signing the tag, or by moving the declaration back. |
| A version is declared, release tags **exist**, none names it, and it is **behind** them | defect | Fail. The single source of version truth (REL-02) has drifted behind the releases. |

Three further states are reported rather than scored, because reporting them as a pass or a failure would be a different kind of dishonesty: a `dynamic = ["version"]` pyproject declares nothing to check (the version is derived, which is what REL-02 asks for), a `"private": true` `package.json` is never published, and a pre-release or dev version (`0.4.0.dev0`) is an in-development number that is not expected to carry a tag. A **shallow clone** exits *cannot-run*, not *pre-release*: `actions/checkout` at its default `fetch-depth: 1` fetches no tags, and a gate that reads that empty tag list as "this repository has never released" is a gate that cannot fail. Check out with `fetch-depth: 0`.

Release preparation is the one legitimate window in which a declared version outruns the tags — the bump merges, the tag is cut after review. `--release-prep X.Y.Z` exempts exactly that version, and only while it is ahead of every existing tag; a repository wires it on its `release/v*` branches exactly as it already wires `check_changelog.py --release-prep`.

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
  and has **no bypass actors** — deliberately unlike the `protect-main` branch ruleset, which always
  carries the maintainer's admin bypass (`CI-CD-STANDARD.md` §5). A wedged branch check blocks all
  work and needs a way through; a shipped tag has no equivalent emergency, because a bad release is
  corrected by cutting a new tag rather than moving an old one. Never harmonize the two lists. `non_fast_forward` alone is insufficient because it can still permit a
  fast-forward tag move. Before tag creation, the read-only validator compares hosted state with that
  profile; the SSH-signed tag message binds the hosted ruleset ID, `updated_at`, and the accountable
  owner's empty-bypass declaration. The release fails closed if the ruleset is missing, changed, or
  does not match the signed assertion.

```bash
# keyless signed tag via gitsign (preferred — no GPG key management)
git tag -s v1.4.0 -m "v1.4.0"
git push origin v1.4.0
sh automation/dispatch_release.sh v1.4.0  # immutable-setting check + draft staging (§4)
sh automation/promote_release.sh v1.4.0   # reverify + owner-local immutable promotion
```

### 3.2 CHANGELOG — Keep a Changelog 1.1.0 — AUTO-GATE on presence, REVIEW-GATE on quality
Every release-producing repo keeps a `CHANGELOG.md` in **[Keep a Changelog 1.1.0](https://keepachangelog.com/)** format with an `## [Unreleased]` section, reverse-chronological entries, and `Added/Changed/Deprecated/Removed/Fixed/Security` groupings. SemVer links at the bottom.

| Control | Requirement | Gate |
|---|---|---|
| CHANGELOG exists & parses [REL-09] | File present, parseable, has `Unreleased` | AUTO-GATE |
| Released version has an entry [REL-10] | The tag being released has a matching `## [X.Y.Z] - YYYY-MM-DD` section (no empty releases) | AUTO-GATE (release job greps for the version heading; fails if absent) |
| Recorded release date is the tag's date [REL-25] | The date on `## [X.Y.Z] - YYYY-MM-DD` **and** `CITATION.cff`'s `date-released` both equal the date the tag itself carries (an annotated tag's tagger date) | AUTO-GATE (release-date parity check, §4 stage 1) |
| Release notes account for the change set [REL-33] | The release section accounts for **every pull request merged since the previous tag**: an entry that names it (`#123`, or the issue its merge subject names), or an explicit internal marker (`<!-- internal: #124 #125 -->`, an `### Internal` list, or a "No user-facing change: #124" line). Silence is not a marker. The release-preparation PR runs `automation/changelog_completeness.py --release-prep X.Y.Z` | AUTO-GATE (report-only through 2026-10-18; conformance control `changelog_completeness`) |
| Security fixes are called out [REL-11] | Any release closing a CVE/advisory has a `Security` entry referencing the advisory | REVIEW-GATE |
| Entry is human-meaningful [REL-12] | Describes user-visible impact, not commit subjects | REVIEW-GATE |

**Why REL-25 is separate from REL-10.** REL-10 asks whether the heading *exists*. The heading carries a date, and asking only about existence leaves that date unchecked by anything. A release section is written when the release is prepared and the tag is cut when the release is actually cut; those are routinely different days, and the gap is invisible because every check still passes. The same drift reaches `CITATION.cff`, whose `date-released` is maintained beside the heading rather than derived from the tag. Neither error is recoverable after the fact: the tag is immutable (REL-07), a published version is never re-cut (REL-07 again), and the citation metadata is what downstream indexes and academic citations record permanently. A wrong release date is therefore a defect that must be caught **before** the tag exists, which is why the check runs in both a prospective mode on the release-preparation PR and a tag-bound mode in the pipeline. "Fix it in the next release" does not repair the recorded history.

**Why REL-33 is separate from REL-10 and REL-12.** REL-10 asks whether a release section exists and REL-12 whether its entries are meaningful; neither asks whether the section is *complete*, and notes written from memory are not. family-greenhouse v0.35.0's CHANGELOG section and GitHub release listed three changes while `git log v0.34.0..v0.35.0` held nine user-facing merges: six shipped unannounced, including a referral program and an abandoned-checkout recovery email on a product that takes real payments. The v0.36.0 notes then initially missed #813 and #814 as well. Every check passed both times, because every check asked about the section and none compared it with the history it describes. Run against v0.35.0, `changelog_completeness.py --tag v0.35.0` fails and names all twelve merged pull requests, because the section cited none of them.

How the check reads history, and the three states it will not call a pass:

- **Pull requests come from first-parent merge subjects**: a squash merge's trailing `(#123)` or a merge commit's `Merge pull request #123`. A range that has commits but no pull request number at all (a rebase-merge history) is *cannot run*, exit 3: it saw nothing to compare, and a pass would claim it had.
- **A shallow clone with no tag in reach is *cannot run***, for the same reason as REL-28: an empty tag list read as "never released" is a check that cannot fail. Check out with `fetch-depth: 0`.
- **A first release has no previous change set**, and the check says so (N/A), rather than passing it silently.

The commit that prepares the release (`chore(release): prepare X.Y.Z (#N)`) is reported as release preparation, not a change. The marker is deliberately explicit rather than inferred from a commit type: a `ci:` or `docs:` subject is a hint about user impact, not a decision about it, and the decision is what the release-preparation review is for. Wire it on the release-preparation PR exactly as `check_changelog.py --release-prep` is already wired:

```yaml
- name: Release notes account for the change set (REL-33)
  if: startsWith(github.head_ref, 'release/v')
  run: python3 .standards/automation/changelog_completeness.py --release-prep "${GITHUB_HEAD_REF#release/v}"
```

The conformance control `changelog_completeness` checks that wiring: for a repository with a `CHANGELOG.md` and at least one release tag, some pull-request-triggered workflow must execute the script (directly, or through the Makefile target or package script a step runs). A step name or a comment that mentions it does not count.

Conventional Commits + an automated changelog generator (`git-cliff`, `release-please`) is **permitted and encouraged** to draft entries, but a human curates the released section — generated commit dumps are not a changelog.

---

## 4. The release pipeline (trusted-main, signed-tag selected)

After pushing a canonical `vX.Y.Z` signed tag, the maintainer uses an owner-local helper with an
administration-capable GitHub credential to verify that repository-level immutable releases are
enabled and dispatch the draft-staging workflow from the default branch. No administration credential
is stored in Actions. `workflow_dispatch` is used deliberately: a
tag-push workflow executes the workflow definition stored at the tagged ref, while the release
authority must come from the reviewed workflow on trusted `main`. The workflow rejects dispatch from
any other ref, any rerun, a dispatch whose actor or triggering actor is not the repository owner, a
non-SemVer tag, an unsigned/untrusted tag, a tag whose commit is not reachable
from current `origin/main`, or a tag whose hosted immutable-ruleset binding is absent/stale. Every
stage is AUTO-GATE unless marked; a red stage aborts before anything is published. The workflow only
stages and verifies a draft. Owner-local promotion then independently verifies the successful workflow
identity, signed provenance, notes, archive, checksum, SBOM, and exact draft bytes; performs the
administration-only immutable-setting check adjacent to publication; and requires the API response to
report the release immutable.

```
on:
  workflow_dispatch:
    inputs:
      tag: {required: true, type: string}
permissions: contents: read          # escalate per-job only (CI-CD-STANDARD §token model)

0. trust                 dispatch ref == main; tag signed by main's allowed signer; tag target ∈ main
1. version-consistency   tag == pyproject/package version == __version__   → fail on mismatch
1a. release-date parity  CHANGELOG [X.Y.Z] date == CITATION date-released == the tag's own date (§3.2)
2. re-run make verify    full lint+type+test+coverage+security AT THE TAGGED COMMIT (never trust the PR run)
3. build                 reproducible build; deterministic artifact (uv build / vite build)
3a. quickstart-from-artifact  install THIS artifact in a clean env, run the documented quickstart
                              from outside the checkout (§5.4)  — where a distributable exists
4. SBOM                  CycloneDX 1.7 generated + schema-validated      → SECURITY §6.2
5. sign + attest         cosign sign + SLSA provenance (keyless, OIDC)   → SECURITY §6.4
6. stage draft           separate checkout-free write job uploads the exact GitHub Release draft
7. verify draft          download and verify SBOM, provenance, notes, and every staged byte
8. owner-local promote   reverify, check immutable hosting through the admin API, then publish
```

Non-negotiables (cross-referenced, enforced here):
- **Caching is disabled** in any job that builds, signs, or publishes — cache poisoning violates SLSA build isolation (`CI-CD-STANDARD.md`; validated by the Feb 2026 cache-poisoning campaign against Microsoft/DataDog/CNCF repos).
- **One global concurrency group** on the release workflow so two versions cannot publish concurrently.
- **Immutable hosting is checked outside Actions:** trusted-main never receives an administration
  credential and never publishes. The owner-local promoter reverifies the trusted draft, checks the
  administration API immediately before publication, and requires the response to report the release
  immutable. A mutable response is treated as a failed promotion and re-drafted when GitHub permits.
  Because GitHub still permits edits to displayed release titles and notes, the exact reviewed notes
  are also a checksummed immutable asset; that asset and its provenance-bound digest are canonical.
- **Split authority:** verification checks out and executes the tagged code with `contents: read`;
  the dependent publish job receives `contents: write` but never checks out or executes repository
  code.
- The release job re-runs `make verify` at the **tagged commit** — it does not reuse the PR's green checkmark. This closes the "main drifted after the PR passed" hole.
- A private-source repository may publish a versioned, reviewed public projection
  of the tagged CHANGELOG section. The workflow still validates the authoritative
  CHANGELOG at the tag, reads the exact notes blob from protected `main`, applies
  the current containment policy, and binds the policy commit plus notes digest
  into signed provenance. The projection preserves material public changes and
  migration instructions while generalizing internal inventory references.
- **OIDC only.** No long-lived PyPI/registry tokens stored as secrets. A new long-lived publish secret appearing in repo settings is an audit-log alarm (`SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §7).

### 4.0 Trigger, trust, and provenance — one model, checked mechanically — AUTO-GATE

Everything above this line describes the model. Nothing measured it. Measured across the portfolio on 2026-09-06: **three incompatible trigger models in use** — dispatch-only, tag/release-triggered, and both at once, sometimes inside a single repository — and tag-signature verification present in **nine of eighteen** sampled release workflows, ranging from eight references in one repository to none at all in three others. Twenty-six repositories have a release or publish workflow and have never cut a release. Fifty-three repositories were each inventing a release model because the standard's own model had no control ID and no checker. The same measurement records a release pull request in `tods-validate` (#79) held open for weeks on exactly the decision this section now writes down: when a model is stated only in prose, there is nothing for a reviewer to point at, so the decision gets deferred rather than made.

These three controls apply to every workflow that **publishes a release artifact** — a PyPI publish action, `twine upload`, `gh release create`/`upload`, `softprops/action-gh-release`, `npm publish`, or a container push bound to a release version. Scope is measured, not assumed: a `docker/build-push-action` step with `load: true` and no `push: true` publishes nothing, and a preview deploy pushing `image:${{ github.sha }}` is a deployment (§5.3), not a release. Both are reported out of scope rather than silently skipped.

| Metric | Requirement | Measured by | Gate |
|---|---|---|---|
| Trigger is `workflow_dispatch` alone [REL-29] | The workflow's only trigger is `workflow_dispatch`, taking a **required `tag` input**. `push` (tags or branches), `release`, `workflow_run`, `schedule`, `create`, `repository_dispatch`, `pull_request` and `pull_request_target` are refused — **including when they sit alongside a conforming dispatch** | `automation/check_release_trigger.py` | AUTO-GATE |
| Tag trust before publication [REL-30] | The tag's signature is verified against a **committed** allowed-signers file before anything is published: inline (`git verify-tag` / `git tag -v`, `gpg.ssh.allowedSignersFile`, the annotated tag-object check, and the `merge-base --is-ancestor` reachability proof) or by calling `release-authorize.yml` (§4.1) pinned to a full 40-character commit SHA | `automation/check_release_trigger.py` | AUTO-GATE |
| Published artifacts are provenance-attested [REL-31] | Every published artifact carries a provenance attestation minted in the run that produced it: `actions/attest-build-provenance` (the default — SHA-pinned, with `attestations: write`), `slsa-framework/slsa-github-generator`, or the keyless `cosign attest-blob --type slsaprovenance*` shape prescribed at §4 stage 5 | `automation/check_release_trigger.py` | AUTO-GATE |

**Why dispatch-only, and why "both" is worse than either.** A tag push is one git command. It has no second pair of eyes, no approval surface, and no record of a decision — and a tag-push workflow runs *the workflow definition stored at the tagged ref*, so the release authority comes from whatever code the tag points at rather than from the reviewed workflow on trusted `main`. A dispatch against an already-signed tag separates **minting** the tag from **publishing** it, and those are the two acts a release consists of. `fhir-scorecard` reached this conclusion independently and wrote it in its own workflow: *pushing a tag is not a review.*

The mixed model — a correct `workflow_dispatch` with a `push: tags:` beside it — is the defect this control is most concerned with, because it is the one that passes every check written the obvious way. Asking "does this workflow have a dispatch with a tag input?" says yes; the tag push publishes anyway, and the deliberate dispatch is decoration. Three repositories were in exactly that state. A control that can be satisfied while the behavior it forbids still happens is not a control.

**Why the signature check needs its three companions.** `git verify-tag` on its own answers less than it appears to. Without `git cat-file -t` the tag may be lightweight, and a lightweight tag has no signature to verify at all — verification of nothing succeeds. Without `gpg.ssh.allowedSignersFile` pointing at a file **committed in the repository**, the trust root is whatever the runner happens to have, which is nothing. Without `merge-base --is-ancestor` the tag may name a commit that never reached `main`, so a fully verified signature can authorize code no gate ever saw. The four together are the reference implementation; the portfolio's signing key lives at `~/.ssh/github-release-signing` and `tods-validate` is the reference consumer.

**Why provenance is listed here and not only under SECURITY §6.4.** REL-16 verifies provenance *after* publication. REL-31 asserts that there is provenance to verify. `actions/attest-build-provenance` is the portfolio default and this control names it, but the keyless `cosign attest-blob --type slsaprovenance1` shape that §4 stage 5 and `standards-init` already prescribe satisfies it equally — REL-31 requires an attestation, not one vendor's spelling of it. An `attest-build-provenance` step in a workflow that grants no `attestations: write` is a **failure, not a pass**: the step cannot mint what it claims to mint, which is the same shape as a gate that cannot fail.

### 4.1 Shared release authorization

Repositories SHOULD call the standards-owned
`.github/workflows/release-authorize.yml` at a full 40-character commit SHA for
step 0, from **`ChelseaKR/.github`**.

The same file also exists in this repository, which is private. A **public**
repository cannot call a reusable workflow that lives in a private one: GitHub
refuses it at parse time as `workflow was not found`, even though the commit and
the file both exist and Actions access is already granted. Public callers MUST
therefore pin the copy in `ChelseaKR/.github`, which is public. Private callers
MAY pin either, and SHOULD pin the public one so the reference does not depend on
the caller's visibility never changing.

The pinned SHA MUST be one that is also a tag in the repository it names; a
40-character SHA proves format, not identity, and resolves through a fork's
shared object store. The reusable workflow checks out the caller's reviewed `main`, rejects
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

### 5.4 The documented quickstart runs from the installed artifact — AUTO-GATE

A repository's whole test suite runs from its checkout. That is a blind spot with a precise shape: when a documented first command reads a fixture, demo dataset or example file that lives at the repository root and was never declared as package data, the command works in every test run and cannot work for anyone who installs the distributable. **Nothing inside the repository can observe this**, because nothing inside it ever runs from outside it. Coverage does not help; the code path is exercised, just never with the data absent. The failure lands on the first command a new user types, and it lands as whatever the tool does when its inputs are missing — a fail-closed error exit for a project that validates its inputs, an uncaught `FileNotFoundError` for one that does not. Neither is a good introduction, and both are invisible until a stranger runs the tool.

| Rule | Requirement | Gate |
|---|---|---|
| Quickstart runs from a built artifact [REL-26] | A project that publishes a distributable runs its own documented quickstart against that **built artifact, installed into a clean environment, from a working directory outside the checkout** — not from the source tree | AUTO-GATE where a distributable exists |
| Quickstart data ships inside the distribution [REL-27] | Every fixture, sample or example a documented command reads is declared package data and resolved through the installed package (`importlib.resources`), never by a path relative to the source tree | AUTO-GATE (a consequence of REL-26; it is how REL-26 is passed) |

**Scope.** REL-26 binds only where a distributable is built — a wheel, an sdist, an npm package. A repository that deliberately ships no distributable declares `N/A` under §1 and is not measured here; that carve-out is real and several repository classes rely on it. The applicability manifest records which repositories build one, so the scope is a registry lookup and not a judgment call made per release.

**What "documented" means.** The commands under test are the ones the README actually shows a new user, delimited by `<!-- quickstart:begin -->` / `<!-- quickstart:end -->` so extraction is unambiguous and so the marked path is specifically the *installed-artifact* path rather than a from-a-clone path. A repository that publishes a distributable and documents no runnable first command fails this gate: an unrunnable quickstart and an absent one leave a new user in the same position.

Prefer running this against the exact artifact the pipeline is about to publish rather than a rebuild of it — the check then also carries REL-16's end-to-end intent, verifying that the bytes being shipped are the bytes that work.

---

## 6. Release artifacts committed/attached — REVIEW-GATE on completeness

Each release attaches (to the GitHub Release) and, where regenerated, commits:

1. **SBOM** (`*.cdx.json`) — CycloneDX 1.7.
2. **Provenance** (`*.intoto.jsonl`) — SLSA L2 minimum, L3 for public packages.
3. **CHANGELOG section** as the release notes, or the exact containment-scanned
   public projection described in §4 for a private-source repository.
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

### 8.1 A release is what puts a change in force — AUTO-GATE

**A change to a versioned artifact is not in force until a release is cut.** Consumers pin a version — a CI-fetch `ref:`, a vendored `.standards-version`, a `>=X.Y` requirement — so a requirement that is merged to `main` and never released reaches nobody. "Merged" and "in force" are different states, and only the second one changes anyone's behavior.

This is not hypothetical and it is not somebody else's repository. On 2026-09-06 the `CI-CD-STANDARD` §11c concurrency-key amendment landed on `portfolio-standards` `main` as two reviewed pull requests; `habitable`'s vendored copy still pinned **v2.0.0, dated 2026-08-09**, so the fix was written, correct, reviewed, and inert. An agent looking at it declined to hand-patch the pinned snapshot, on the correct reasoning that patching a pin makes it a faithful copy of no upstream version at all. Twenty-six repositories in this portfolio have a release or publish workflow and have never cut a release; the machinery is built and the release never happens.

That is REL-28 read from the other end. There, a version number with no artifact behind it. Here, an artifact with no release in front of it. Both are an absence — a release that did not happen — being treated as though it were a value.

| Metric | Requirement | Measured by | Gate |
|---|---|---|---|
| Release cadence is stated [REL-32] | A repository whose consumers pin a version declares, in a discoverable place, when it cuts a release: a `Release cadence:` line, read with the same free-text vocabulary the staleness stamps at the foot of every standard already use (`monthly` / `quarterly` / `semi-annual` / `annual`). **With no stated cadence there is no date anything can be late against, and the absence is itself the defect.** Unreleased work older than the stated cadence is a finding | `automation/check_release_currency.py` | AUTO-GATE |

**The two halves are enforced in different places, on purpose.** Writing the cadence line is something any contributor can do, so `--declaration-only` runs on the merge gate. Cutting a release is an owner action requiring an administration credential (§4), so the lag half runs on the scheduled self-check, which files an issue. A merge gate that only the owner can unjam blocks every other contributor from every unrelated change, and a queue jammed on someone else's credential is a worse failure than a late release. Enforcement is still binary — the scheduled run either passes or fails, and its failure opens an issue; it is simply not wired to a merge.

A repository with no release tag yet is pre-release: there is no last release to be late against, so the lag half reports N/A. A shallow clone reports *cannot run*, for the reason given at §2 (REL-28).

---

## 9. Metrics ledger (per release-producing repo)

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Tag ⇔ version consistency [REL-03] | exact match | version-check step in `release.yml` | AUTO-GATE |
| Released version in CHANGELOG [REL-10] | present, dated | grep for `[X.Y.Z]` heading | AUTO-GATE |
| Recorded date == tag date [REL-25] | exact match, both places | release-date parity check (stage 1a) | AUTO-GATE |
| Documented quickstart runs from the artifact [REL-26, REL-27] | passes from a clean install outside the checkout | quickstart-from-artifact check (stage 3a) | AUTO-GATE where a distributable exists |
| Signed release tag [REL-08] | 100% of releases | gitsign/`git tag -v` verification | AUTO-GATE |
| Publish credential [REL-17] | OIDC, zero stored tokens | secret-inventory audit | AUTO-GATE |
| `make verify` re-run at tag [REL-14] | green at tagged commit | release job stage 2 | AUTO-GATE |
| SBOM + provenance attached [REL-20] | every release | release assets present + `slsa-verifier` | AUTO-GATE |
| End-to-end verify of published artifact [REL-16] | passes | stage 8 pull-and-verify | AUTO-GATE |
| Public-API SemVer correctness [REL-06] | no undeclared breaking change in MINOR/PATCH | `griffe`/`api-extractor` diff + human review | REVIEW-GATE |
| Migration note on MAJOR [REL-06] | present | release review | REVIEW-GATE |

---

Last verified: 2026-06-21 · Recheck cadence: per SemVer, Keep a Changelog, PyPI Trusted Publishing, SLSA, and Sigstore release; and immediately on any disclosed registry or GitHub Actions supply-chain compromise. Confirm current action versions (`gh-action-pypi-publish`, `attest-build-provenance`, gitsign) at build time.
