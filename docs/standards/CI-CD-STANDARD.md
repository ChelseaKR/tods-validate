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

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATE** (human judgment, paired with a checklist item and a committed artifact). There is no "aspirational" third category. If a row below cannot be made one of these two, it is a defect in this document.

The threat model is **active, not theoretical**: the March 2026 `trivy-action` force-push (secrets exfiltrated from 75 tags), the `tj-actions` compromise, and the February 2026 AI-automated cache-poisoning campaign against Microsoft/DataDog/CNCF repos are why every control below exists. ~13 of 19 repos in this portfolio still reference actions by mutable tag; this standard closes that.

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

Stages 1–5 are mandatory for **every** repo (including `self-osint-monitor`, which must scaffold this as its M0 deliverable before any M1 code, and `gtfs-scorecard`, whose root has no CI today). Stages 6–8 apply by repo shape and are declared **applicable or N/A-with-reason** in the repo's `ROADMAP.md` Metrics ledger — silently skipping a stage is a defect.

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
| Top-level `permissions:` present | every workflow | zizmor + Scorecard Token-Permissions | AUTO-GATE |
| Token-Permissions score | **10/10** | `ossf/scorecard-action` on default branch | AUTO-GATE (fail < 8) |
| Write scopes | job-level only, minimal set | zizmor `excessive-permissions` rule | AUTO-GATE |

Currently missing the block entirely: `gtfs-scorecard`, `jobradar`, `personal-site`, `tods-validate` ci.yml. Required pattern:

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

Every workflow that touches AWS/GCP/Azure authenticates via **OIDC**; long-lived cloud keys in Actions secrets are prohibited. OIDC is already adopted where AWS is used (`jobradar`, `fare-assistant`, `personal-site`, `civic-ai-eval-harness` publishing) — this makes it mandatory and closes the trust scope.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Cloud creds via OIDC | 100% of cloud-touching jobs | grep for `aws-access-key`/static creds in workflows; zizmor | AUTO-GATE |
| OIDC trust subject scope | `repo:org/repo:environment:<env>` (never `:*`, never org-wide) | review of cloud trust policy artifact | REVIEW-GATE |
| New long-lived cloud secret added | alert | org audit-log rule on `org.update_actions_secret` | REVIEW-GATE |

```yaml
  deploy:
    environment: production
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@<40-char-sha>  # v4.x — see SEC std for pinning
        with:
          role-to-assume: arn:aws:iam::ACCT:role/personal-site-deploy
          aws-region: us-west-2
          # NO aws-access-key-id / aws-secret-access-key anywhere
```

The IAM trust policy `sub` must pin to the **specific repo + environment claim**, e.g. `repo:ckellyreif/personal-site:environment:production`. A wildcard subject is a REVIEW-GATE failure.

---

## 4. SHA-pinned actions (reference SECURITY-AND-SUPPLY-CHAIN-STANDARD)

The full pinning/SBOM/signing posture lives in `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`. CI restates only the **merge-blocking surface** that this pipeline enforces:

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Every `uses:` pinned to 40-char SHA + `# vX.Y.Z` comment | 100% (incl. reusable workflows **and the deploy path**) | zizmor `unpinned-uses` + Scorecard Pinned-Dependencies | AUTO-GATE |
| Pinned-Dependencies score | **≥ 9/10** | `ossf/scorecard-action` | AUTO-GATE |
| SHA freshness | Renovate `helpers:pinGitHubActionDigestsToSemver`, `minimumReleaseAge: 72h` | committed `renovate.json` / `dependabot.yml` | AUTO-GATE (config present) |

Today only `habitable`, `trans-docs-navigator`, `civic-ai-eval-harness`/`govchat-eval` pin. `nearmiss` (0/17), `gtfs-scorecard` (0/2) are fully tag-pinned; `trans-docs-navigator` leaks **one straggler tag in `deploy-aws-preview.yml`** — the deploy path is in scope, fix it. Migrate with `pin-github-action` or StepSecurity Action-Advisor:

```bash
# pins every uses: to its current SHA + version comment, repo-wide
npx pin-github-action .github/workflows/*.yml
# verify nothing references a tag/branch
! grep -rEn 'uses:.*@(v?[0-9]|main|master|latest)\b' .github/workflows/
```

---

## 5. Branch protection, required checks, no admin bypass

Branch protection is enforced via **org-level GitHub Rulesets** (not per-repo settings, which admins can edit) and committed as a per-repo artifact so the posture is reviewable in-tree. This is essentially absent portfolio-wide today and must be added everywhere.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Branch-Protection score | **≥ 8/10** | `ossf/scorecard-action` | AUTO-GATE |
| Required reviewers on `main`/`release/*` | ≥ 1 (≥ 2 for civic/PII repos: `fare-assistant`, `gtfs-scorecard`, civic-rag) | ruleset artifact `.github/rulesets/main.json` | REVIEW-GATE |
| Required status checks | `format,lint,type,test,security` + `zizmor` + `codeql-actions` + applicable a11y/perf/responsible | ruleset `required_status_checks` | AUTO-GATE |
| Dismiss stale reviews on push | on | ruleset | AUTO-GATE |
| Admin bypass on `main` | **disabled** (`enforce_admins: true`) | direct-push test (owner push must fail) | AUTO-GATE |
| Force-push to `main`/`release/*` | blocked | ruleset | AUTO-GATE |

The committed ruleset doubles as evidence and feeds SLSA Source Track L2 (`attest-build-provenance` populates `sourceLevels` only when branch protection with required reviews is active — see SECURITY std).

```jsonc
// .github/rulesets/main.json (committed; mirrors the org ruleset)
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main", "refs/heads/release/*"] } },
  "rules": [
    { "type": "pull_request", "parameters": { "required_approving_review_count": 1,
      "dismiss_stale_reviews_on_push": true, "require_code_owner_review": true } },
    { "type": "required_status_checks", "parameters": { "required_status_checks": [
      {"context": "format"}, {"context": "lint"}, {"context": "type"},
      {"context": "test"}, {"context": "security"}, {"context": "zizmor"},
      {"context": "codeql-actions"} ] } },
    { "type": "non_fast_forward" },        // no force-push
    { "type": "deletion" }
  ],
  "bypass_actors": []                       // empty = no admin bypass
}
```

---

## 6. CODEOWNERS on security-critical paths

A committed `CODEOWNERS` routes `.github/workflows/`, rulesets, IaC, and security-critical files to a required reviewer; the ruleset sets `require_code_owner_review`. This is mechanically enforced — a PR touching a workflow cannot merge without that review. Absent portfolio-wide today.

```
# .github/CODEOWNERS
*                               @ckellyreif
/.github/workflows/             @ckellyreif      # workflow edits = poisoned-pipeline risk
/.github/rulesets/              @ckellyreif
/infra/  /terraform/            @ckellyreif
/SECURITY.md  /.github/dependabot.yml  /renovate.json  @ckellyreif
# repo-specific responsible-tech guards (no-outing, consent gate, citation):
/tests/test_no_outing.py        @ckellyreif      # ledger
/tests/test_no_identity_inference.py  @ckellyreif # women-artist-discovery
```

| Metric | Target | Gate |
|---|---|---|
| `CODEOWNERS` exists and covers `.github/workflows/` | yes | AUTO-GATE (file presence + path coverage check) |
| Code-owner review required by ruleset | on | REVIEW-GATE (ruleset artifact) |

---

## 7. Workflow SAST (zizmor + CodeQL `language: actions`)

The workflows themselves are scanned. **zizmor nowhere in the portfolio today** — required.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| zizmor on any PR touching `.github/workflows/**` | zero High/Critical findings; SARIF to Code Scanning | required status check `zizmor` | AUTO-GATE |
| CodeQL `language: actions` | nightly + on workflow PRs | required status check `codeql-actions` | AUTO-GATE |
| Dangerous-Workflow score | **10/10** | Scorecard (no `pull_request_target` checkout of untrusted code; no script injection) | AUTO-GATE (fail < 10) |

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
Production/staging deploys run only through a **named GitHub Environment** with ≥ 1 required reviewer and "Protected branches only" deployment restriction. Even a workflow running a compromised action cannot reach prod without human sign-off.

| Metric | Target | Gate |
|---|---|---|
| Prod/staging deploy gated by named Environment + required reviewer + prevent-self-review | yes | REVIEW-GATE (committed `environments-audit-YYYY-QN.json`, quarterly) |

### 8b. Concurrency groups
Deploy/release workflows set a concurrency group to prevent racing deploys; called reusable workflows declare their **own** group independent of the caller. Inconsistently applied today (`gtfs-scorecard` has 10 workflows, eval harnesses 9, most repos 1–2).

```yaml
concurrency:
  group: deploy-${{ github.ref }}            # deploy/release: serialize
  cancel-in-progress: false                  # never cancel an in-flight deploy
# CI/lint jobs may use cancel-in-progress: true
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| `concurrency:` on every deploy/release job | present, `cancel-in-progress: false` | workflow-lint check / zizmor | AUTO-GATE |

### 8c. Caching disabled in release/publish jobs
Cache (`actions/cache`, `cache: true` on `setup-*`) is **prohibited** in any job that deploys to prod, publishes a package, generates SLSA provenance, or holds `id-token: write` — cache poisoning violates SLSA L3 isolation. Cache is allowed only in `pull_request`-triggered build/test jobs.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| No caching in release/publish/provenance/`id-token` jobs | enforced | zizmor cache-poisoning rule + workflow-lint | AUTO-GATE |

---

## 9. Reusable workflows + `make verify` reproduces CI locally

**Reusable org workflows.** Build/test/security-scan/deploy logic lives once in a shared `.github` repo (`ckellyreif/.github`) and product repos *call* it rather than copy-pasting. Callers must not override security-critical inputs (`permissions`, environment names). This kills the per-repo drift that lets a green build in one repo fail in another.

```yaml
jobs:
  ci:
    uses: ckellyreif/.github/.github/workflows/python-verify.yml@<sha>  # vX.Y.Z
    permissions:
      contents: read
    # caller may pass project values (coverage floor) but NOT permissions/secrets blanket
    with: { cov-fail-under: 90 }   # libraries; default 85
```

| Metric | Target | Gate |
|---|---|---|
| Build/deploy logic via central reusable workflow | yes (product repos) | REVIEW-GATE (quarterly reusable-workflow security review, committed) |
| Caller does not override `permissions`/secrets | enforced | AUTO-GATE (zizmor on caller) |

**`make verify` ≡ CI.** The single command runs the *same* gate set CI runs, eliminating local/remote drift. Several Python repos already ship a `make verify` that is byte-for-byte identical to CI — this makes that the portfolio rule. CI calls the same Makefile target it asks contributors to run; the two cannot diverge.

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
| `make verify` runs the exact CI gate set | identical command surface | CI job that *only* runs `make verify` for stages 1–5 | AUTO-GATE |
| Config consolidated in single `pyproject.toml`, `uv sync --frozen` | no `ruff.toml`/`pytest.ini`/`requirements.txt` strays | CODE-QUALITY-STANDARD | AUTO-GATE |

**Repo-specific layout fixes this standard surfaces** (resolved under CODE-QUALITY-STANDARD, gated here via "`make verify` at repo root must exist and pass"):
- `jobradar`: no `pyproject.toml` — splits config across `requirements.txt` + `ruff.toml` + `pytest.ini`, no mypy. Consolidate; add type gate.
- `gtfs-scorecard`: real project hidden at `pipeline/pyproject.toml`, no root `make verify`/`uv.lock`. Add root `Makefile` delegating to `pipeline/`, or hoist config.
- `self-osint-monitor`: spec-only, no CI/Makefile/pyproject. Scaffold §1 + §2 + §9 as the **M0 deliverable** before M1 code (and sequence the consent gate per AI-EVAL/RESPONSIBLE-TECH).
- `queer-the-stacks` / `queer-specfic-reader`: duplicate `queer_the_stacks` package. Reconcile to one repo before applying this standard twice (REVIEW-GATE: documented fork/rename decision).

---

## 10. Per-repo CI declaration (committed artifact)

Each repo's `ROADMAP.md` Metrics ledger (shape defined in `QUALITY-AND-METRICS-STANDARD.md`) carries the CI-specific rows so enforcement is unambiguous and every optional stage is explicitly **applicable or N/A-with-reason**:

| Metric | Target | Measured by | Gate | Owner |
|---|---|---|---|---|
| Token-Permissions | 10/10 | scorecard-action | AUTO-GATE | — |
| Pinned-Dependencies | ≥ 9/10 | scorecard-action | AUTO-GATE | — |
| Branch-Protection | ≥ 8/10 | scorecard-action | AUTO-GATE | — |
| Dangerous-Workflow | 10/10 | scorecard-action | AUTO-GATE | — |
| Cloud auth via OIDC | 100% | workflow grep + zizmor | AUTO-GATE | — |
| zizmor on workflow PRs | 0 High/Crit | required check | AUTO-GATE | — |
| `make verify` ≡ CI | identical | CI job | AUTO-GATE | — |
| Deploy reviewer gate | env + ≥1 reviewer | environments-audit | REVIEW-GATE | — |
| a11y / perf / responsible stages | applicable **or** N/A-with-reason | ledger row | per stage | — |

A stage marked N/A **must** carry a one-line reason (e.g. "perf: pure library, no latency contract"; "i18n: single-user English-only CLI, entry point `_()` documented"). A blank or missing row is a merge-blocking defect.

---

Last verified: 2026-06-21 · Recheck cadence: per GitHub Actions security-feature release, OpenSSF Scorecard minor (currently v5.5), SLSA spec revision (currently v1.2), and OWASP Top-10 CI/CD update — review at least quarterly given the active supply-chain threat environment. Confirm current action SHAs, Scorecard check weights, and GitHub ruleset schema at build time.
