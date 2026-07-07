# Security & Supply-Chain Standard

This is the canonical definition of application-security and software-supply-chain rigor for every repo in this portfolio. It owns the *machinery*: ASVS level, SAST/SCA/secret-scanning configuration, Action SHA-pinning, SBOM/signing/provenance, and the token-permission model. Repos record only project-specific *values and findings* — the threat model narrative, the residual-risk register, the per-repo ASVS level declaration — in `docs/RESPONSIBLE-TECH-AUDITS.md` (methodology: `RESPONSIBLE-TECH-FRAMEWORK.md` §F) and their `ROADMAP.md` Metrics table. Reference, don't repeat.

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI, no `|| true`, no `continue-on-error`) or **REVIEW-GATE** (human judgment, paired with a checklist line and a committed, dated artifact regenerated on release). There is no aspirational third category. The portfolio already proves every target here is achievable: `habitable`, `trans-docs-navigator`, and `civic-ai-eval-harness`/`govchat-eval` already ship the full SHA-pin + SBOM + Sigstore + OIDC posture. The work is propagation, not invention.

CI/CD-pipeline hardening (token permissions, OIDC, branch rulesets, workflow SAST) lives in `CI-CD-STANDARD.md`; this document covers it only where it is load-bearing for supply-chain integrity and cross-references the rest. Toolchain floors (ruff/mypy/coverage) live in `CODE-QUALITY-STANDARD.md`.

---

## 1. ASVS level per repo (the floor and the PII tier)

Target framework is **OWASP ASVS 5.0.0** (May 2025). Every repo declares its level in `docs/RESPONSIBLE-TECH-AUDITS.md` §F. There is no silent default — a repo with no declaration fails review.

| Repo class | ASVS target | Rationale | Examples |
|---|---|---|---|
| Default floor | **L1** | ASVS 5.0 states L1 is achievable with automated tooling alone; that maps exactly to our AUTO-GATE set. | every repo, minimum |
| Touches PII / identity / location | **L2** | Field-level authz (BOPLA V8.2.1), cross-tenant isolation, breached-password checks, OIDC `acr`/`amr` validation. | `fare-assistant` (transit PII), `self-osint-monitor`, `olive-bark-logger`, `trans-docs-navigator`, `ledger` |
| Catastrophic-breach surface | L3 *(none today)* | Hardware phishing-resistant factor, adaptive authz, annual threat-model + leadership justification. No current repo hosts auth at this blast radius; if one does, it declares L3 and adopts the V6/V8/V10 L3 review-gates. | — |

L1 is satisfied entirely by §3–§4 AUTO-GATEs (parameterized queries, output encoding, TLS 1.2+, server-side function- and object-level authz). L2 adds the authz integration tests in §5 and the OAuth/OIDC review-gate. `ledger`'s no-outing guarantee and `women-artist-discovery`'s "no identity inference" AST test are project-specific ASVS-V8 abuse-case controls — keep them; they are exemplars, not exceptions.

### When this section does NOT apply
A repo with **no authentication, no authorization surface, and no network ingress** (a pure offline CLI or library, e.g. `tods-validate`, `swelter` as a library) declares `ASVS: N/A (no auth/authz/ingress surface)` with that exact reason. It still inherits all of §3, §4, §6, §7 — supply-chain and scanning are never N/A for a repo that ships code.

---

## 2. Privacy-first repos: hardened posture (olive-bark-logger, self-osint-monitor, trans-docs-navigator)

These three carry the highest individual-harm blast radius (a logger of sensitive activity, an OSINT self-monitor, and trans-resource navigation). They adopt **every** AUTO-GATE below as merge-blocking with **zero waivers**, plus:

| Control | Target | Measured by | Gate |
|---|---|---|---|
| No-secret/no-PII in logs | zero matches for password/token/email/`Authorization` field values | Semgrep custom rule + log-assertion integration test (`jq` over emitted JSON) | AUTO-GATE |
| Consent gate before feature code | sequenced before any M1 feature; CI asserts gate module imported on every entrypoint | static import test | AUTO-GATE (`self-osint-monitor`) |
| No third-party exfiltration | StepSecurity Harden-Runner egress allowlist in every job; deny-by-default | Harden-Runner `block` mode + audit | AUTO-GATE |
| Sentinel-identity tripwire | injected sentinel survives full pipeline without leaking | isolated CI job (lift `ledger`'s no-outing test pattern) | AUTO-GATE |
| ASVS L2 | full §5 authz tests | integration suite | AUTO-GATE |

`self-osint-monitor` is spec-only today (no CI, no `pyproject`, no tests). It **scaffolds this standard as its M0 deliverable** before any M1 feature code — Harden-Runner, gitleaks pre-commit + CI, SHA-pinned actions, top-level `permissions: contents: read`, and the consent gate land first.

---

## 3. Static analysis (SAST): Semgrep + CodeQL

**Semgrep** for fast diff-aware PR coverage (~10 s, SARIF to Code Scanning); **CodeQL** for deep cross-file taint/dataflow on a nightly schedule + required check on `main`. Rejected: Semgrep alone (misses multi-file auth bypasses); CodeQL alone (too slow for every PR, no IaC breadth).

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Semgrep findings | zero unwaived **HIGH/CRITICAL** at merge | `semgrep ci --sarif` | AUTO-GATE |
| CodeQL findings | zero unwaived HIGH/CRITICAL on `main` | `github/codeql-action`, nightly + required on push to `main` | AUTO-GATE (graduate `davis-bike-hazard-map` from advisory) |
| Workflow SAST | zero high/critical | CodeQL `language: actions` + `zizmor` (see §7) | AUTO-GATE |
| Waiver hygiene | every waiver has expiry + reason | committed `.semgrep-waivers.yml`, reviewed quarterly | REVIEW-GATE |

```yaml
# .github/workflows/sast.yml — Semgrep PR gate
permissions:
  contents: read
jobs:
  semgrep:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write   # upload SARIF only
    steps:
      - uses: actions/checkout@<40-char-sha> # v4.2.2
        with: { persist-credentials: false }
      - uses: semgrep/semgrep-action@<40-char-sha> # v1.x
      - run: semgrep ci --sarif --output=semgrep.sarif --severity=ERROR --severity=WARNING
      - uses: github/codeql-action/upload-sarif@<40-char-sha> # v3.x
        with: { sarif_file: semgrep.sarif }
```

`make verify` runs `semgrep ci` locally so the gate is byte-for-byte reproducible (matches the portfolio's `make verify` == CI discipline).

---

## 4. Dependency scanning (SCA) + secret scanning

### SCA — pip-audit / npm audit / OSV-Scanner + Dependabot/Renovate

OSV-Scanner is the portfolio baseline (queries the same OSV DB as Scorecard's Vulnerabilities check, covers 20+ ecosystems incl. transitive lockfile deps). pip-audit / npm audit run additionally per ecosystem. **The `|| true` on `pip-audit` in `ledger` and `nearmiss` is deleted — that neuter defeats the gate entirely.**

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Python vulns | zero **HIGH+CRITICAL with a fix available** | `pip-audit` (no `\|\| true`) + `osv-scanner -r .` over `uv.lock` | AUTO-GATE |
| Node vulns | zero HIGH+CRITICAL | `npm audit --audit-level=high` | AUTO-GATE (frontends + `personal-site` Lambda) |
| Transitive coverage | lockfile present & scanned | `osv-scanner` fails if no `uv.lock`/`package-lock.json` | AUTO-GATE |
| Update automation | Dependabot or Renovate config present (Scorecard `Dependency-Update-Tool`) | committed `dependabot.yml`/`renovate.json` | AUTO-GATE |
| Open critical alerts | none merge-able | branch ruleset blocks merge on open Dependabot alert CVSS ≥ 7.0 | AUTO-GATE |
| Unfixable HIGH/CRITICAL waiver | tracked + VEX-justified | committed `vex.json` (CycloneDX 1.7 VEX), quarterly review | REVIEW-GATE |

`gtfs-scorecard` (fetches external GTFS zips, runs a Java subprocess) and `fare-assistant` (transit PII) currently have the **thinnest** scanning despite the highest sensitivity — they adopt the full SCA + secret-scan set first.

### Secret scanning — gitleaks (Gate 1+2) + TruffleHog (Gate 3)

Two-gate gitleaks: **pre-commit** (Gate 1) and **CI diff** (Gate 2). TruffleHog runs a scheduled full-history scan (Gate 3) with live-credential verification.

| Gate | Tool | Target | Gate |
|---|---|---|---|
| 1 pre-commit | gitleaks `v8.30.1` | zero unredacted matches | AUTO-GATE |
| 2 CI diff | gitleaks `--exit-code 1 --redact` (no `\|\| true`) | zero matches | AUTO-GATE |
| 3 scheduled | `trufflehog git --object-discovery --results=verified,unknown --fail` | zero verified live creds | AUTO-GATE (page on hit) |

```yaml
# .pre-commit-config.yaml — Gate 1 (also closes the pre-commit adoption gap)
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks: [{ id: gitleaks }]
```

Pre-commit adoption is currently the minority (~6 of 19 repos). This config is now **mandatory** in every repo; the gitleaks + ruff + mypy hooks are the required floor.

---

## 5. Input validation & authz testing (ASVS V8 / L2)

L1 floor (AUTO-GATE, all repos with ingress): parameterized queries only (no string-built SQL — Semgrep rule), output encoding on all user-controlled HTML sinks (XSS), TLS 1.2+ asserted, server-side function-level authz (V8.1.1) and object-level authz (V8.1.2).

L2 (AUTO-GATE, PII repos): an integration suite asserting **every protected endpoint returns 403 to an unauthorized principal** and that object-level (BOLA/IDOR) and field-level (BOPLA) access is denied cross-tenant. Block deploy if any protected route lacks a negative-path test.

```python
# tests/test_authz.py — the negative-path assertion, every protected route
@pytest.mark.parametrize("route", PROTECTED_ROUTES)
def test_unauthorized_principal_gets_403(client, route):
    assert client.get(route, headers=other_tenant_token()).status_code == 403
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Injection / XSS | zero | Semgrep taint rules + DAST in staging | AUTO-GATE |
| Function-level authz | every protected route 403s unauth | parametrized integration test | AUTO-GATE (L2) |
| Object-level authz (BOLA) | cross-tenant access denied | integration test w/ second principal | AUTO-GATE (L2) |
| OAuth/OIDC (V10) | PKCE enforced; `acr`/`amr` validated; sender-constrained tokens | security architecture review | REVIEW-GATE (identity-critical services) |
| Annual pentest (BOLA/BOPLA/tenant) | report attached to release | manual + human triage | REVIEW-GATE (L2 PII repos) |

---

## 6. Supply chain: pin Actions, SBOM, signing, provenance, Scorecard

This is the portfolio's largest open gap (~13 of 19 repos non-conformant on SHA-pinning) and the most active threat — the **March 2026 trivy-action force-push** and **tj-actions** compromises were real exfiltration events, not hypotheticals.

> This section owns the supply-chain **machinery** (SBOM, signing, provenance) that a release *invokes*. The release **process and policy** — SemVer, signed tags, CHANGELOG, the tag-triggered pipeline, and Trusted Publishing — lives in `RELEASE-AND-VERSIONING-STANDARD.md`. When that standard says "sign + attest → SECURITY §6," this is the section it means.

### 6.1 Pin every Action to a full 40-char commit SHA — AUTO-GATE

Every `uses:` — third-party actions, `actions/*`, **reusable workflows, and the deploy path** — is pinned to a full 40-char commit SHA with a trailing `# vX.Y.Z` comment. Tags and branches are immutable-reference failures. This explicitly closes `nearmiss` (0/17 SHA), `gtfs-scorecard` (0/2), and `trans-docs-navigator`'s single straggler in `deploy-aws-preview.yml`.

```yaml
# correct — immutable, human-readable
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
- uses: astral-sh/setup-uv@<40-char-sha> # v5.x
# WRONG — mutable, exploitable
- uses: actions/checkout@v4
- uses: gitleaks/gitleaks-action@v2
```

Renovate keeps SHAs current and survivable:

```json
// renovate.json
{
  "extends": ["config:recommended", "helpers:pinGitHubActionDigestsToSemver"],
  "minimumReleaseAge": "72 hours"
}
```

Migration: run StepSecurity Action-Advisor (app.stepsecurity.io) or `pin-github-action` over each workflow to auto-generate SHA-pinned stubs.

```bash
npx pin-github-action .github/workflows/*.yml   # rewrites tags -> SHA + comment
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Every `uses:` SHA-pinned | 100% incl. reusable + deploy | Scorecard `Pinned-Dependencies` **≥ 9/10** on default branch | AUTO-GATE |
| SHAs kept current | Renovate active, 72h cooldown | committed `renovate.json` | AUTO-GATE |

### 6.2 SBOM — CycloneDX 1.7 — AUTO-GATE on every release

Generate a **CycloneDX 1.7** (ECMA-424) SBOM for every release artifact and every container image; validate against schema before signing; fail the build on schema failure. Rejected SPDX-only: CycloneDX 1.7's attestation + VEX + ML-BOM `modelCard` shapes fit our SLSA and AI-repo needs better; both are NTIA/CISA/EU-CRA accepted.

```bash
syft . -o cyclonedx-json=sbom.cdx.json            # or: cdxgen -t python -o sbom.cdx.json
cyclonedx-cli validate --input-file sbom.cdx.json --input-version v1_7
grype sbom:sbom.cdx.json --fail-on high            # gate the SBOM itself
```

Required component fields: `name`, `version`, `purl`, `hashes` (SHA-256). AI/RAG repos additionally emit an ML-BOM `modelCard` component for each model dependency (ties to the model-card lint in `AI-EVALUATION-STANDARD.md`).

### 6.3 Container CVE scanning — AUTO-GATE for every Dockerfile repo

Trivy/Grype image scan, threshold standardized to **CRITICAL,HIGH** portfolio-wide (the eval harnesses' CRITICAL-only setting is raised). Closes the missing scans in `davis-bike-hazard-map`, `habitable`, `civic-rag-starter-kit`, `queer-the-stacks`, `trans-docs-navigator`.

```bash
trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 $IMAGE
```

### 6.4 Signing + provenance — Sigstore cosign + SLSA — AUTO-GATE on release

Keyless cosign (OIDC via the workflow identity; Fulcio cert + Rekor log; no long-lived keys). Target **SLSA Build L2** minimum (signed provenance, hosted build, consumer-verifiable); **L3** for public/critical packages via `slsa-framework/slsa-github-generator` (signing key inaccessible to build steps, isolated ephemeral build). Provenance predicate `https://slsa.dev/provenance/v1`.

```yaml
# release signing — keyless, OIDC identity
permissions:
  id-token: write    # OIDC
  contents: write    # attach release assets
  attestations: write
steps:
  - uses: sigstore/cosign-installer@<40-char-sha> # v3.x
  - run: cosign sign --yes $IMAGE
  - run: cosign attest --yes --predicate sbom.cdx.json --type cyclonedx $IMAGE
  - uses: actions/attest-build-provenance@<40-char-sha> # v2.x  (SLSA L2 + Source Track)
    with: { subject-path: 'dist/*' }
```

Caching is **disabled** in any job that signs/publishes/generates provenance (cache poisoning violates SLSA isolation). Concurrency group on release jobs. Both rules cross-reference `CI-CD-STANDARD.md`.

Deployment-side: consumers verify before install.

```bash
cosign verify --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  --certificate-identity-regexp='^https://github.com/<org>/<repo>/' $IMAGE
slsa-verifier verify-artifact --source-uri github.com/<org>/<repo> dist/<artifact>
```

### 6.5 OpenSSF Scorecard — required check

`ossf/scorecard-action` nightly + on PRs to default branch; SARIF to Code Scanning.

| Scorecard check | Target | Gate |
|---|---|---|
| `Pinned-Dependencies` | ≥ 9/10 | AUTO-GATE |
| `Token-Permissions` | 10/10 | AUTO-GATE |
| `Dangerous-Workflow` | 10/10 | AUTO-GATE |
| `Branch-Protection` | ≥ 8/10 | AUTO-GATE |
| `Signed-Releases` | 10/10 (`.intoto.jsonl` on last 5) | AUTO-GATE (release repos) |
| `Vulnerabilities` | 10/10 | AUTO-GATE |
| Aggregate | ≥ 8/10 | AUTO-GATE |
| Monthly Scorecard report committed | present, dated | REVIEW-GATE |

---

## 7. Least-privilege tokens, OIDC, branch protection, workflow SAST

Owned in detail by `CI-CD-STANDARD.md`; the supply-chain-load-bearing minimums repeated here so a repo author can't miss them:

| Control | Target | Measured by | Gate |
|---|---|---|---|
| Top-level `permissions` | `contents: read`, per-job escalation only | present in every workflow (closes `gtfs-scorecard`, `jobradar`, `personal-site`, `tods-validate`) | AUTO-GATE |
| Cloud creds | OIDC only, no long-lived secrets, sub scoped to `repo:…:environment:…` | audit-log alert on new long-lived secret | AUTO-GATE |
| Workflow SAST | `zizmor` required check on any PR touching `.github/workflows/` | merge-blocked on high/critical | AUTO-GATE |
| `persist-credentials: false` | on every `actions/checkout` | zizmor / grep | AUTO-GATE |
| No direct push to `main` | branch ruleset, no admin bypass, ≥1 required review | committed ruleset export | AUTO-GATE |
| CODEOWNERS routes `.github/workflows/` + security-critical files | required reviewer | committed `CODEOWNERS` | AUTO-GATE |
| Branch ruleset + CODEOWNERS as committed artifacts | present | repo files | REVIEW-GATE (close portfolio-wide absence) |

```yaml
# zizmor as a required check
permissions: { contents: read }
jobs:
  zizmor:
    if: contains(toJSON(github.event.pull_request.changed_files), '.github/workflows/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-char-sha> # v4.2.2
        with: { persist-credentials: false }
      - uses: zizmorcore/zizmor-action@<40-char-sha> # v0.x
```

---

## 8. Per-repo declarations (no silent skips)

Every repo's `docs/RESPONSIBLE-TECH-AUDITS.md` §F records, with no blanks:

1. **ASVS level** (L1 / L2 / L3 / `N/A (reason)`).
2. **Container scanning**: enabled, or `N/A (no Dockerfile)`.
3. **SBOM + signing**: enabled on release, or `N/A (not a release-producing repo)` — note this is rare; libraries published to PyPI **do** produce releases.
4. **Secret-management policy** (OSPS-BR-07.02): storage, rotation, revocation — committed once, reviewed annually.
5. **VEX** for any unfixable HIGH/CRITICAL dependency CVE.

An N/A is a *declared decision with a one-line reason*, reviewed like any other. A blank is a defect.

### Cross-repo reconciliation (blocking on the affected repos)
- `queer-the-stacks` / `queer-specfic-reader` share the `queer_the_stacks` package — an undocumented fork/rename. Reconcile to one canonical repo before applying this standard, or both drift and double-count. **REVIEW-GATE.**
- `gtfs-scorecard` has no repo-root config; its project lives at `pipeline/`. CI here must target `pipeline/` (or hoist config to root) so portfolio tooling does not silently skip it. **AUTO-GATE** (CI path declared).

---

## 9. The blocking security pipeline (reference)

Ordered, all blocking; `make verify` runs the local-runnable subset byte-for-byte:

```
1. secret scan        → gitleaks pre-commit (Gate 1) + CI diff (Gate 2)
2. SAST               → semgrep ci (HIGH/CRITICAL) ; CodeQL nightly + required on main
3. SCA                → pip-audit / npm audit --audit-level=high / osv-scanner (no || true)
4. authz tests        → 403-on-unauth + BOLA/BOPLA (L2 repos)
5. container scan     → trivy image --severity CRITICAL,HIGH (Dockerfile repos)
6. workflow SAST      → zizmor (PRs touching .github/workflows/)
7. supply chain (rel) → SBOM (CycloneDX 1.7) -> validate -> cosign sign + attest -> SLSA provenance
8. scorecard          → ossf/scorecard-action, aggregate >= 8, criticals at target
9. (human) review     → threat-model sign-off, VEX, secrets policy, pentest (L2)
```

---

Last verified: 2026-06-21 · Recheck cadence: per OWASP ASVS, SLSA, CycloneDX, OpenSSF Scorecard/Baseline, and Sigstore release; and immediately on any disclosed GitHub Actions supply-chain compromise. Confirm current tool versions (gitleaks, TruffleHog, Scorecard, cosign, CycloneDX spec) at build time.
