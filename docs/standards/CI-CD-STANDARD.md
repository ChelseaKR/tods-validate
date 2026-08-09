# CI/CD Standard

This is the canonical definition of the **merge-blocking pipeline** and the **GitHub Actions security posture** every repo in this portfolio ships. It owns the *shape* of CI (stage order, gates, token model, branch protection, deploy/release safety); it does **not** own the *content* of individual gates — those live in their own standards and are referenced here, not repeated:

| This doc references | For |
|---|---|
| `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | SHA pinning, SBOM, cosign/SLSA, Scorecard thresholds, SAST/SCA/secret/container scanning |
| `CODE-QUALITY-STANDARD.md` | ruff/mypy/pytest floors, coverage thresholds, `uv.lock`, src layout |
| `QUALITY-AND-METRICS-STANDARD.md` | the quality-attribute taxonomy and the per-repo Metrics ledger shape |
| `ACCESSIBILITY-STANDARD.md` | axe/Lighthouse/pa11y gates, target-size, ACR |
| `AI-EVALUATION-STANDARD.md` | faithfulness/red-team/calibration gates on prompt/retrieval PRs |
| `OBSERVABILITY-STANDARD.md` | structured-log schema, OTel, `/livez`/`/readyz` |
| `INTERNATIONALIZATION-STANDARD.md` | catalog format, key-parity, pseudolocale |

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATE** (accountable human judgment, paired with a checklist item and a dated durable artifact—committed by default, authenticated current-head PR/deploy metadata only where explicitly required below). There is no "aspirational" third category. If a row below cannot be made one of these two, it is a defect in this document.

The threat model is **active, not theoretical**: the March 2026 `trivy-action` force-push (secrets exfiltrated from 75 tags), the `tj-actions` compromise, and the February 2026 AI-automated cache-poisoning campaign against Microsoft/DataDog/CNCF repos are why every control below exists. Repository-specific adoption gaps stay in the private remediation registry.

---

## 1. The canonical merge-blocking pipeline

Every repo ships **one CI workflow** (`.github/workflows/ci.yml`) whose jobs run these stages **in this order**. A merge to `main` requires **every** applicable stage green. `make verify` (Python) / `npm run verify` (TS) runs the same gates locally — see §9.

```
1. format        ruff format --check / prettier --check        → fail on any deviation
2. lint          ruff check (+ zizmor on workflow PRs)          → fail on any finding
3. type          mypy --strict / tsc --noEmit                   → zero errors
4. test          pytest --cov (branch>=85%, libs>=90%) / vitest → fail under threshold
5. security      semgrep + gitleaks + pip-audit/osv + trivy     → fail HIGH/CRITICAL (see SEC std)
6. a11y          axe-core + pa11y-ci + Lighthouse (UI repos)    → see ACCESSIBILITY std
7. perf          k6 / Lighthouse CI budgets                     → regression >10% fails
8. responsible   eval/citation/consent/no-outing gates          → see RESPONSIBLE-TECH + AI-EVAL
9. build         build artifact + container + SBOM + provenance → see SECURITY std
```

Stages 1–5 are mandatory for **every** repository. A not-yet-implemented tool
scaffolds them before feature code, and a nested project exposes the gates from
the repository root. Stages 6–8 apply by repository shape and are declared
**applicable or N/A-with-reason** in the repo's `ROADMAP.md` Metrics ledger —
silently skipping a stage is a defect.

| Stage | Applies to | N/A-with-reason permitted when |
|---|---|---|
| 1–5 | all repos | never |
| 6 a11y | any repo emitting HTML/UI (frontends, **eval harnesses whose reports are user-facing**) | no human-facing HTML output, declared in ledger |
| 7 perf | hosted services, frontends, LLM routes | pure library/CLI with no latency contract |
| 8 responsible | AI/RAG/eval, privacy-first, civic repos | repo's Responsible-Tech audit marks the gate N/A |

---

## 2. Least-privilege `GITHUB_TOKEN`

**Default is write; this is wrong.** Org-level default is set to read-only (Settings → Actions → General → "Read repository contents and packages permissions"), and **every** workflow declares a top-level `permissions` block. Write is granted **per-job, never top-level**.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Top-level `permissions:` present [CICD-02] | every workflow | zizmor + Scorecard Token-Permissions | AUTO-GATE |
| Token-Permissions score [CICD-03] | **10/10** | `ossf/scorecard-action` on default branch | AUTO-GATE (fail < 8) |
| Write scopes [CICD-04] | job-level only, minimal set | zizmor `excessive-permissions` rule | AUTO-GATE |

Every workflow carries this required top-level block:

```yaml
# top of every workflow — deny by default
permissions:
  contents: read

jobs:
  verify:
    permissions:
      contents: read          # explicit even when same as top-level
    # ...
  publish:
    permissions:
      contents: read
      id-token: write          # OIDC, see §3
      attestations: write      # SLSA provenance, see SECURITY std
      packages: write          # only this job, only because it pushes
```

**No `secrets: inherit`** in reusable-workflow calls — pass each secret explicitly. **`persist-credentials: false`** on every `actions/checkout`. **No untrusted `github.*` context** interpolated into `run:` blocks — assign to an intermediate `env:` var first (zizmor `template-injection`, merge-blocking).

---

## 3. OIDC for cloud auth — no long-lived secrets

Every workflow that touches AWS/GCP/Azure authenticates via **OIDC**;
long-lived cloud keys in Actions secrets are prohibited. The trust policy is
scoped to the exact repository, branch or Environment, and workflow purpose.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Cloud creds via OIDC [CICD-05] | 100% of cloud-touching jobs | grep for `aws-access-key`/static creds in workflows; zizmor | AUTO-GATE |
| OIDC trust subject scope [CICD-06] | `repo:org/repo:environment:<env>` (never `:*`, never org-wide) | review of cloud trust policy artifact | REVIEW-GATE |
| New long-lived cloud secret added [CICD-07] | alert | org audit-log rule on `org.update_actions_secret` | REVIEW-GATE |

```yaml
  deploy:
    environment: production
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@<40-char-sha>  # v4.x — see SEC std for pinning
        with:
          role-to-assume: arn:aws:iam::ACCT:role/example-frontend-deploy
          aws-region: us-west-2
          # NO aws-access-key-id / aws-secret-access-key anywhere
```

The IAM trust policy `sub` must pin to the **specific repo + environment claim**, e.g. `repo:owner/example-frontend:environment:production`. A wildcard subject is a REVIEW-GATE failure.

---

## 4. SHA-pinned actions (reference SECURITY-AND-SUPPLY-CHAIN-STANDARD)

The full pinning/SBOM/signing posture lives in `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`. CI restates only the **merge-blocking surface** that this pipeline enforces:

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Every `uses:` pinned to 40-char SHA + `# vX.Y.Z` comment [CICD-08] | 100% (incl. reusable workflows **and the deploy path**) | zizmor `unpinned-uses` + Scorecard Pinned-Dependencies | AUTO-GATE |
| Pinned-Dependencies score [CICD-09] | **≥ 9/10** | `ossf/scorecard-action` | AUTO-GATE |
| SHA freshness [CICD-10] | Renovate `helpers:pinGitHubActionDigestsToSemver`, `minimumReleaseAge: 72h` | committed `renovate.json` / `dependabot.yml` | AUTO-GATE (config present) |

Every action reference, including preview and deployment workflows, must be
pinned. One straggler tag fails the gate. Migrate with `pin-github-action` or
StepSecurity Action-Advisor:

```bash
# pins every uses: to its current SHA + version comment, repo-wide
npx pin-github-action .github/workflows/*.yml
# verify nothing references a tag/branch
! grep -rEn 'uses:.*@(v?[0-9]|main|master|latest)\b' .github/workflows/
```

---

## 5. Branch protection, required checks, auditable emergency bypass

Branch protection is enforced through a **repository-owned GitHub Ruleset** named `protect-main` and
committed as a per-repo artifact so the posture is reviewable in-tree. An
organization may add inherited rulesets as stricter, separately named defense
in depth, but inherited state does not replace the unique repository-owned
profile that the read-only validator resolves.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Branch-Protection score [CICD-11] | **≥ 8/10** | `ossf/scorecard-action` | AUTO-GATE |
| Required reviewers on `main` [CICD-12] | ≥ 1 (≥ 2 for civic/PII repos); exactly 0 only while the bounded solo-maintainer mode below is current | ruleset artifact `.github/rulesets/main.json` + `check_solo_governance.py --hosted` | AUTO+REVIEW |
| Required status checks [CICD-13] | `format,lint,type,test,security` + `zizmor` + `codeql-actions` + applicable a11y/perf/responsible | ruleset `required_status_checks` | AUTO-GATE |
| Dismiss stale reviews on push [CICD-14] | on | ruleset | AUTO-GATE |
| Emergency bypass on `main` [CICD-15] | one designated maintainer, **PR-only** (`bypass_mode: pull_request`); direct admin pushes remain blocked | committed ruleset actor + bypassed PR attestation | AUTO+REVIEW-GATE |
| Force-push to `main` [CICD-16] | blocked | ruleset | AUTO-GATE |

Repositories that actually maintain `release/*` branches create a second committed `protect-release`
profile with the same deletion, non-fast-forward, signature, linear-history, status, and review
floors. The canonical `protect-main` profile intentionally matches only `refs/heads/main`, so its live
parity check is unambiguous.

The committed ruleset doubles as evidence and feeds SLSA Source Track L2 (`attest-build-provenance` populates `sourceLevels` only when branch protection with required reviews is active — see SECURITY std).

The bypass is a break-glass path, not a second merge policy. It may be used only
when an authorized human explicitly directs the merge and a required external
gate cannot produce a result (for example, hosted CI cannot allocate a runner).
The change must still be carried by a pull request; direct pushes, force-pushes,
and branch deletion remain blocked. Before bypassing, run every available local
equivalent, record the blocked check and the explicit authorization in the PR,
and merge with the platform's PR bypass so the PR timeline and merge commit
remain the audit trail. Never disable or delete the ruleset to force a merge.
Routine red tests, missing review, or convenience are not bypass conditions.

```jsonc
// .github/rulesets/main.json (committed; mirrors repository-owned protect-main)
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "pull_request", "parameters": { "required_approving_review_count": 1,
      "dismiss_stale_reviews_on_push": true, "require_code_owner_review": true } },
    { "type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true, "required_status_checks": [
      {"context": "format"}, {"context": "lint"}, {"context": "type"},
      {"context": "test"}, {"context": "security"}, {"context": "zizmor"},
      {"context": "codeql-actions"} ] } },
    { "type": "required_signatures" },
    { "type": "required_linear_history" },
    { "type": "non_fast_forward" },        // no force-push
    { "type": "deletion" }
  ],
  "bypass_actors": [
    { "actor_id": 3114598, "actor_type": "User", "bypass_mode": "pull_request" }
  ]                                           // designated maintainer; PR path only
}
```

### 5.1 One-person project ruleset profile

`required_approving_review_count: 1` is impossible when the author is the only active maintainer;
GitHub cannot count self-approval. An eligible project following `CODE-QUALITY-STANDARD.md` §7.1 may
set that count to `0` and `require_code_owner_review` to `false`, while retaining the PR requirement,
strict required checks, stale-head invalidation, signed commits, deletion/force-push protection, and
empty bypass actors. Its current solo-maintainer declaration names the owner, declaration/expiry
dates, reporting channel, and the automatic return-to-independent-review triggers. The PR carries the
authenticated current-head decision required by CQ-37/CQ-43.

The `solo-governance` required status runs the repository's pinned standards validator against the
current dated declaration. Hosted mode requires `GH_TOKEN`/`GITHUB_TOKEN` and `GITHUB_REPOSITORY`,
looks up the current PR head and comments through `gh api`, authenticates the declared human's login,
account type and repository association, and requires the API's push-capable collaborator set to be
exactly that login. It also uses the ordinary read-only workflow token (Metadata:read) to compare the
active hosted `protect-main` rules against the committed profile. GitHub withholds
`bypass_actors` from callers lacking ruleset write access; PR code is never given such a credential.
The authenticated current-head owner comment therefore binds the fetched ruleset ID and
`updated_at` and explicitly declares the hosted bypass list empty. Omitted bypass data is accepted
only after that exact comment passes; a visible non-empty list always fails. Token, API, permission,
ruleset, event/head, comment, or collaborator ambiguity fails closed. Post the final-head comment,
then rerun the same head's failed required check; do not push a record containing a comment URL or
SHA to make it pass.

The status evaluates **both** the proposed committed profile and the live hosted profile on every PR;
branching on the proposed approval count alone is forbidden. The only valid states are:

| Proposed committed profile | Live hosted profile | Result |
|---|---|---|
| normal | normal | API-visible fields must match; platform independent approval remains authoritative |
| normal | solo | **fail** — hosted count zero must never enter a no-attestation CI branch |
| solo | normal | serialized activation only: exact current-head solo attestation plus equality of every visible field except the still-stricter hosted approval count/code-owner requirement |
| solo | solo | exact visible parity plus the current-head attestation bound to hosted ruleset ID/`updated_at` and an owner declaration that redacted bypass actors are empty |

Activate solo mode in that order: land the declaration and proposed solo profile in one PR; while the
hosted profile is still normal, post the generated current-head comment and let CI validate the
stricter transition state. The platform still blocks self-merge. Then change only the live approval
count to `0` and code-owner requirement to `false`. That ruleset update changes `updated_at`, so the
old comment is stale: post a fresh generated comment and rerun the same head before merging. During
the brief hosted-solo interval, any concurrent PR whose committed profile is still normal fails the
matrix above. Serialize the transition; do not have another mergeable PR in flight.

GitHub's read-only response may omit `bypass_actors`. In normal/normal mode CI can prove only visible
parity and must say exactly that; omission is never reported as proof of an empty list. Before solo
activation and before a solo deployment, the accountable owner inspects the live settings and makes
the exact ruleset-ID/`updated_at`-bound empty-bypass declaration. A visible non-empty bypass list
fails in every mode. No ruleset-write credential is exposed to pull-request code.

This profile changes only unavailable human-approval mechanics. It never turns a synthetic review
into an approval, never permits direct push, and never relaxes an AUTO-GATE. The normal profile is
restored before merging work outside the eligibility boundaries in CQ §7.1 or as soon as a second
maintainer joins.

Required status contexts are repository-specific: the generic validator accepts a non-empty unique
set and compares hosted state exactly to the committed set. Each repository's CI passes its own exact
expected set explicitly; it does not inherit this standards repo's job names. The solo profile always
includes `solo-governance`. Dated governance, synthetic-evidence, and solo-deployment records are
append-only after reaching the base branch; renewal adds a new dated file.

---

## 6. CODEOWNERS on security-critical paths

A committed `CODEOWNERS` routes `.github/workflows/`, rulesets, IaC, and security-critical files to a required reviewer. Projects with an independent reviewer set `require_code_owner_review`; an eligible one-person project keeps the routing file but records `require_code_owner_review: false` under §5.1 because a self-review is not code-owner approval. The normal setting returns with a second maintainer or for an ineligible change.

```
# .github/CODEOWNERS
*                               @owner
/.github/workflows/             @owner      # workflow edits = poisoned-pipeline risk
/.github/rulesets/              @owner
/infra/  /terraform/            @owner
/SECURITY.md  /.github/dependabot.yml  /renovate.json  @owner
# repo-specific responsible-tech guards (no-outing, consent gate, citation):
/tests/test_no_outing.py        @owner
/tests/test_no_identity_inference.py  @owner
```

| Metric | Target | Gate |
|---|---|---|
| `CODEOWNERS` exists and covers `.github/workflows/` [CICD-17] | yes | AUTO-GATE (file presence + path coverage check) |
| Code-owner review required by ruleset [CICD-18] | on; reasoned solo-mode false only under §5.1 | REVIEW-GATE (ruleset artifact + solo declaration) |

---

## 7. Workflow SAST (zizmor + CodeQL `language: actions`)

The workflows themselves are scanned; `zizmor` is required.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| zizmor on any PR touching `.github/workflows/**` [CICD-19] | zero High/Critical findings; SARIF to Code Scanning | required status check `zizmor` | AUTO-GATE |
| CodeQL `language: actions` [CICD-20] | nightly + on workflow PRs | required status check `codeql-actions` | AUTO-GATE |
| Dangerous-Workflow score [CICD-21] | **10/10** | Scorecard (no `pull_request_target` checkout of untrusted code; no script injection) | AUTO-GATE (fail < 10) |

```yaml
# .github/workflows/zizmor.yml
name: zizmor
on:
  pull_request: { paths: ['.github/workflows/**', '.github/actions/**'] }
permissions:
  contents: read
  security-events: write          # SARIF upload only
jobs:
  zizmor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>          # v4.x; persist-credentials: false
        with: { persist-credentials: false }
      - uses: zizmorcore/zizmor-action@<sha>  # vX.Y.Z
```

`pull_request_target` / `workflow_run` are **prohibited** unless the workflow verifies actor membership and never checks out PR code; the only approved cross-privilege pattern is unprivileged `pull_request` uploads artifact → privileged `workflow_run` verifies then acts (zizmor + Scorecard enforce this).

---

## 8. Deploy & release safety: environments, concurrency, no-cache

### 8a. GitHub Environments with required reviewers
Production/staging deploys run only through a **named GitHub Environment** with ≥ 1 required reviewer and "Protected branches only" deployment restriction. An eligible one-person portfolio/open-source project cannot use prevent-self-review truthfully; it instead uses protected branches plus the authenticated, current-artifact pre-deploy decision below. Client, regulated, essential, PII-expanding, payment, auth, or safety-critical deployments still require an independent environment reviewer.

| Metric | Target | Gate |
|---|---|---|
| Prod/staging deploy gated by named Environment + required reviewer + prevent-self-review [CICD-22] | yes; eligible solo project uses named environment + protected branch + artifact-bound owner decision, with 0 independent reviewers explicitly recorded | REVIEW-GATE (committed `environments-audit-YYYY-QN.json`, quarterly) |
| Exact solo deployment decision verified immediately before promotion [CICD-30] | signed provenance plus exact artifact SHA-256, tested source, optional bound evidence record, destination/environment/workflow/promotion command, rollback artifact/evidence, current hosted ruleset, evidence producers/versions, still-open issue-backed experiential gates, excluded-use flags, accountable human, and ≤90-day expiry all match | AUTO+REVIEW (`check_solo_deploy_decision.py --artifact --attestation-bundle`; authenticated merged-PR comments + committed decision record) |

The solo path uses `templates/solo-maintainer-deploy-decision.md` at
`docs/governance/solo-deploy-decision-YYYY-MM-DD[-release-id].md`. Build and test product source
commit **P**, then create the immutable candidate and record its SHA-256. There are exactly zero or
one post-test evidence commits: optional commit **E** adds one bound canonical synthetic
accessibility record and nothing else; otherwise **E=P** and `evidence_record` is `null`. The E
binding records the canonical path and material SHA-256. **E** (or **P**) becomes
`pre_decision_head_sha`. The next and final commit **D** adds only the
deploy-decision record. Product, configuration, policy, runbook, or other evidence changes after
**P** are forbidden; rebuild and retest from a new **P** instead.

After every deployment check passes, the accountable maintainer posts the validator-generated exact
decision body from their authenticated GitHub account. It states that no independent human approval
occurred and binds the immutable artifact SHA-256 and digest scope, **P**, optional **E**, destination
URL, named GitHub Environment, workflow job, exact audited repository-specific promotion command,
rollback reference/prior digest/test evidence, signed provenance, evidence producers with exact
versions, durable evidence, every open experiential gate, finding disposition, residual risks,
excluded-use flags, current hosted protect-main ruleset ID/`updated_at`/empty bypass declaration,
human identity, acceptance date, and expiry. The decision date must be on or after governance takes
effect; its expiry is at most 90 days and cannot outlive that governance declaration. It authorizes
only promotion of those exact bytes—never a rebuild or future release.

Immediately before promotion, from a clean full-history checkout at **D**, run:

```sh
GH_TOKEN="$GITHUB_TOKEN" GITHUB_REPOSITORY=owner/repo \
  python3 STANDARDS/automation/check_solo_deploy_decision.py \
  --artifact <exact-immutable-candidate> \
  --attestation-bundle <signed-provenance-bundle> \
  docs/governance/solo-deploy-decision-YYYY-MM-DD[-release-id].md
```

The full gate recomputes the artifact digest; verifies signed provenance; verifies the tracked
**P→E→D** graph and every local file/anchor at **P**; imports the canonical solo-governance and
synthetic-evidence validators; proves the decision and optional evidence comments belong to merged
same-repository PRs at **D** and **E**, respectively; and proves GitHub `main` is **D**. Live API
checks require exact committed/hosted protect-main parity and the attested ruleset identity/empty
bypass state, a well-formed sole push-capable collaborator result, still-open same-repository issues
for issue-backed open gates, and the protected-branch Environment. The workflow/job named in the
record must exist at **P**, declare that Environment at job scope, execute the full validator and an
artifact SHA-256 recheck in real `run:` bodies, then execute the exact named promotion command.
Comments or nested metadata cannot satisfy those checks. Missing network, token, permission,
history, provenance, workflow, or mismatched data fails closed.
`--structure-only` is drafting assistance and cannot authorize promotion.

This path is unavailable for client/contractual or procurement work, formal-conformance or legally
required deliverables, regulated or essential services, changes that create or expand an excluded
auth/payment/PII/safety/employment/healthcare/emergency/public-benefit boundary, or remediation of a
verified user-impact incident. Those deployments wait for independent human environment approval.

### 8b. Concurrency groups
Deploy/release workflows set a concurrency group to prevent racing deploys;
called reusable workflows declare their **own** group independent of the caller.

```yaml
concurrency:
  group: deploy-${{ github.ref }}            # deploy/release: serialize
  cancel-in-progress: false                  # never cancel an in-flight deploy
# CI/lint jobs may use cancel-in-progress: true
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| `concurrency:` on every deploy/release job [CICD-23] | present, `cancel-in-progress: false` | workflow-lint check / zizmor | AUTO-GATE |

### 8c. Caching disabled in release/publish jobs
Cache (`actions/cache`, `cache: true` on `setup-*`) is **prohibited** in any job that deploys to prod, publishes a package, generates SLSA provenance, or holds `id-token: write` — cache poisoning violates SLSA L3 isolation. Cache is allowed only in `pull_request`-triggered build/test jobs.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| No caching in release/publish/provenance/`id-token` jobs [CICD-24] | enforced | zizmor cache-poisoning rule + workflow-lint | AUTO-GATE |

---

## 9. Reusable workflows + `make verify` reproduces CI locally

**Reusable workflows.** Build/test/security-scan logic must live once in the
central standards repository. The reference contract uses
`.github/workflows/python-verify.yml` for stages 1–5 and composite actions such
as `.github/actions/{a11y-scan,i18n-gates,eval-gates,release-pipeline}` for
repo-shape-dependent stages 6–8. Product repos call these components rather
than copy-pasting them. Callers
must not override security-critical inputs (`permissions`, environment
names); they pass values (paths, thresholds, python versions), never
structure. This kills the per-repo drift that lets a green build in one
repo fail in another.

```yaml
jobs:
  ci:
    uses: ChelseaKR/portfolio-standards/.github/workflows/python-verify.yml@<sha>  # vX.Y.Z
    permissions:
      contents: read
    # caller may pass project values (coverage floor, package path) but NOT permissions/secrets blanket
    with: { package-path: "src tests", cov-fail-under: 90 }   # libraries; default 85
```

| Metric | Target | Gate |
|---|---|---|
| Build/deploy logic via central reusable workflow [CICD-25] | yes (product repos) | REVIEW-GATE (quarterly reusable-workflow security review, committed) |
| Caller does not override `permissions`/secrets [CICD-26] | enforced | AUTO-GATE (zizmor on caller) |

**`make verify` ≡ CI.** The single command runs the *same* gate set CI runs, eliminating local/remote drift. CI calls the same Makefile target it asks contributors to run; the two cannot diverge.

```makefile
# Makefile — CI invokes `make verify`; nothing in CI runs gates the Makefile doesn't
verify: format-check lint type test security
format-check: ; ruff format --check .
lint:         ; ruff check .
type:         ; mypy --strict src
test:         ; pytest --cov=src --cov-branch --cov-fail-under=85
security:     ; pip-audit && gitleaks detect --no-banner   # NO `|| true` — see SECURITY std
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| `make verify` runs the exact CI gate set [CICD-27] | identical command surface | CI job that *only* runs `make verify` for stages 1–5 | AUTO-GATE |
| Config consolidated in single `pyproject.toml`, `uv sync --frozen` [CICD-28] | no `ruff.toml`/`pytest.ini`/`requirements.txt` strays | CODE-QUALITY-STANDARD | AUTO-GATE |

**Layout fixes this standard surfaces** (resolved under CODE-QUALITY-STANDARD,
gated here via "`make verify` at repo root must exist and pass"):
- A service with split Python configuration consolidates it into a root `pyproject.toml` and adds the type gate.
- A nested project exposes a root `Makefile` that delegates to the package, or hoists its configuration and lockfile.
- A not-yet-implemented privacy-sensitive tool scaffolds §1, §2, and §9 before feature code, sequenced after its consent gate per AI-EVAL/RESPONSIBLE-TECH.
- Duplicate or forked packages record one canonical repository before applying portfolio controls, so audit work is neither duplicated nor lost.

---

## 10. Per-repo CI declaration (committed artifact)

Each repo's `ROADMAP.md` Metrics ledger (shape defined in `QUALITY-AND-METRICS-STANDARD.md`) carries the CI-specific rows so enforcement is unambiguous and every optional stage is explicitly **applicable or N/A-with-reason**:

| Metric | Target | Measured by | Gate | Owner |
|---|---|---|---|---|
| Token-Permissions [CICD-03] | 10/10 | scorecard-action | AUTO-GATE | — |
| Pinned-Dependencies [CICD-09] | ≥ 9/10 | scorecard-action | AUTO-GATE | — |
| Branch-Protection [CICD-11] | ≥ 8/10 | scorecard-action | AUTO-GATE | — |
| Dangerous-Workflow [CICD-21] | 10/10 | scorecard-action | AUTO-GATE | — |
| Cloud auth via OIDC [CICD-05] | 100% | workflow grep + zizmor | AUTO-GATE | — |
| zizmor on workflow PRs [CICD-19] | 0 High/Crit | required check | AUTO-GATE | — |
| `make verify` ≡ CI [CICD-27] | identical | CI job | AUTO-GATE | — |
| Deploy reviewer gate [CICD-22] | env + ≥1 reviewer | environments-audit | REVIEW-GATE | — |
| a11y / perf / responsible stages [CICD-29] | applicable **or** N/A-with-reason | ledger row | per stage | — |

A stage marked N/A **must** carry a one-line reason (e.g. "perf: pure library, no latency contract"; "i18n: single-user English-only CLI, entry point `_()` documented"). A blank or missing row is a merge-blocking defect.

## 11. CI minute efficiency (lean Actions)

Minutes are both a cost and a failure mode: a private repo that exhausts its Actions quota (or hits a billing lapse) **stops gating merges entirely**. Spend the fewest minutes that still enforces every metric in §10.

**11a. Visibility is a governance boundary, not a cost lever.** Repository
visibility defaults to restricted until an explicit publication review clears
it. Never publish a repository merely to reduce CI cost; reduce runner usage or
fund the required private checks instead.

**11b. Runners.** `ubuntu-latest` is the default. `macos-*` (**10× minutes**) and `windows-*` (**2×**) are **forbidden on per-push/PR CI**; if a platform genuinely needs coverage it runs on a **nightly `schedule` matrix only**, with the reason in a comment. CI does not exercise OS-specific device I/O (e.g. live audio), so OS-matrixing the unit suite is pure cost.

**11c. Cancel superseded runs.** Every CI/lint workflow sets, at the top level:
```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```
(Release/publish/deploy jobs keep `cancel-in-progress: false` per §8b.)

**11d. Gate heavy & advisory jobs.** Browser E2E, fuzz, load, and other multi-minute jobs: a **blocking** E2E may run on PRs into `main`; any **non-blocking/advisory** variant (`continue-on-error: true`) runs on `schedule` (nightly) or behind a label, never on every push. An advisory job that cannot fail the merge has no business spending minutes on every commit.

**11e. CodeQL.** Run on **PRs into `main` + a weekly `schedule`**; drop the redundant `push: main` trigger when the PR run already covers it. Never on feature-branch pushes.

**11f. Cache dependencies.** Use the toolchain action's built-in cache (`setup-python cache: pip`, `setup-node cache: npm`, `setup-uv` cache) on all CI — except release/publish jobs (§8c).

**11g. Trim PR matrices.** Test the single canonical version on PRs; run the full version matrix on `main` + nightly.

**11h. Skip CI on docs-only changes** without breaking required checks: filter heavy jobs with `paths-ignore: ['**.md', 'docs/**', 'LICENSE']`, and provide a same-named **always-green skip job** so the required status still reports success and the PR stays mergeable. (A required check that simply never runs leaves a PR stuck "Expected — waiting".)

**11i. `push:` scope.** Expensive build, coverage, and deploy jobs may restrict
`push:` to `main`, with feature validation coming from `pull_request`. A
repository that can publish source or documentation runs its lightweight
publication-boundary guard on **every branch push** as defense in depth; the
local pre-push guard and hosting policy remain responsible for preventing an
unsafe push before server-side CI can react.

Measured by a `ci-minutes` review-gate row in the ledger; the merge-blocking floor is: **no `macos`/`windows` on PR CI · concurrency-cancel present · advisory jobs scheduled, not per-push**.

---

Last verified: 2026-07-16 · Recheck cadence: per GitHub Actions security-feature release, OpenSSF Scorecard minor (currently v5.5), SLSA spec revision (currently v1.2), and OWASP Top-10 CI/CD update — review at least quarterly given the active supply-chain threat environment. Confirm current action SHAs, Scorecard check weights, and GitHub ruleset schema at build time.
