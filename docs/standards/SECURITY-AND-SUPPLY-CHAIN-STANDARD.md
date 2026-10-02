# Security & Supply-Chain Standard

This is the canonical definition of application-security and software-supply-chain rigor for every repo in this portfolio. It owns the *machinery*: ASVS level, SAST/SCA/secret-scanning configuration, Action SHA-pinning, SBOM/signing/provenance, and the token-permission model. Repos record only project-specific *values and findings* — the threat model narrative, the residual-risk register, the per-repo ASVS level declaration — in `docs/RESPONSIBLE-TECH-AUDITS.md` (methodology: `RESPONSIBLE-TECH-FRAMEWORK.md` §F) and their `ROADMAP.md` Metrics table. Reference, don't repeat.

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI, no `|| true`, no `continue-on-error`) or **REVIEW-GATE** (human judgment, paired with a checklist line and a committed, dated artifact regenerated on release). There is no aspirational third category. SHA pinning, SBOM generation, keyless signing, provenance, and OIDC are established mechanisms; each repository records its own adoption evidence privately.

CI/CD-pipeline hardening (token permissions, OIDC, branch rulesets, workflow SAST) lives in `CI-CD-STANDARD.md`; this document covers it only where it is load-bearing for supply-chain integrity and cross-references the rest. Toolchain floors (ruff/mypy/coverage) live in `CODE-QUALITY-STANDARD.md`.

---

## 1. ASVS level per repo (the floor and the PII tier)

Target framework is **OWASP ASVS 5.0.0** (May 2025). Every repo declares its level in `docs/RESPONSIBLE-TECH-AUDITS.md` §F. There is no silent default — a repo with no declaration fails review.

| Repo class | ASVS target | Rationale | Examples |
|---|---|---|---|
| Default floor | **L1** | ASVS 5.0 states L1 is the minimum, first-layer-of-defense set (about 20% of its requirements). It does not say automated tooling alone achieves L1; this portfolio maps L1 to its AUTO-GATE set. | every repo, minimum |
| Touches PII / identity / location | **L2** | Field-level authz (BOPLA V8.2.3), cross-tenant isolation, breached-password checks, OIDC `acr`/`amr` validation. | public-service applications, privacy-sensitive tools, identity-aware frontends, or local data stores |
| Catastrophic-breach surface | **L3** | Hardware phishing-resistant factor, adaptive authz, annual threat-model + leadership justification. Any repository at this blast radius declares L3 and adopts the V6/V8/V10 L3 review-gates. | high-impact identity or authorization systems |

L1 is satisfied entirely by §3–§4 AUTO-GATEs (parameterized queries, output encoding, TLS 1.2+, server-side function- and object-level authz). L2 adds the authz integration tests in §5 and the OAuth/OIDC review-gate. No-outing sentinel tests and AST-level no-identity-inference checks are reference ASVS-V8 abuse-case controls; repositories keep equivalent project-specific guarantees.

### When this section does NOT apply
A repo with **no authentication, no authorization surface, and no network ingress** (for example, a pure offline CLI or library) declares `ASVS: N/A (no auth/authz/ingress surface)` with that exact reason. It still inherits all of §3, §4, §6, §7 — supply-chain and scanning are never N/A for a repo that ships code.

---

## 2. Privacy-sensitive tools: hardened posture

Tools that log sensitive activity, monitor people or identity signals, or help
people navigate sensitive resources carry a high individual-harm blast radius.
They adopt **every** AUTO-GATE below as merge-blocking with **zero waivers**,
plus:

| Control | Target | Measured by | Gate |
|---|---|---|---|
| No-secret/no-PII in logs [SEC-02] | zero matches for password/token/email/`Authorization` field values | Semgrep custom rule + log-assertion integration test (`jq` over emitted JSON) | AUTO-GATE |
| Consent gate before feature code [SEC-03] | sequenced before any feature that processes sensitive data; CI asserts gate module imported on every entrypoint | static import test | AUTO-GATE |
| No third-party exfiltration [SEC-04] | StepSecurity Harden-Runner egress allowlist in every job; deny-by-default | Harden-Runner `block` mode + audit | AUTO-GATE |
| Sentinel-identity tripwire [SEC-05] | injected sentinel survives full pipeline without leaking | isolated no-outing CI job | AUTO-GATE |
| ASVS L2 [SEC-06] | full §5 authz tests | integration suite | AUTO-GATE |

A privacy-sensitive tool with no implementation yet scaffolds this standard
before its first feature code: Harden-Runner, gitleaks pre-commit + CI,
SHA-pinned actions, top-level `permissions: contents: read`, and the consent gate
land first.

---

## 3. Static analysis (SAST): Semgrep + CodeQL

**Semgrep** for fast diff-aware PR coverage (~10 s, SARIF to Code Scanning); **CodeQL** for deep cross-file taint/dataflow on a nightly schedule + required check on `main`. Rejected: Semgrep alone (misses multi-file auth bypasses); CodeQL alone (too slow for every PR, no IaC breadth).

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Semgrep findings [SEC-07] | zero unwaived **HIGH/CRITICAL** at merge | `semgrep ci --sarif` | AUTO-GATE |
| CodeQL findings [SEC-08] | zero unwaived HIGH/CRITICAL on `main` | `github/codeql-action`, nightly + required on push to `main` | AUTO-GATE |
| Workflow SAST [SEC-09] | zero high/critical | CodeQL `language: actions` + `zizmor` (see §7) | AUTO-GATE |
| Waiver hygiene [SEC-10] | every waiver has expiry + reason | committed `.semgrep-waivers.yml`, reviewed quarterly | REVIEW-GATE |

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

OSV-Scanner is the portfolio baseline (queries the same OSV DB as Scorecard's Vulnerabilities check, covers 20+ ecosystems incl. transitive lockfile deps). pip-audit / npm audit run additionally per ecosystem. **A scanner followed by `|| true` does not constitute a gate and is forbidden.**

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Python vulns [SEC-11] | zero **HIGH+CRITICAL with a fix available** | `pip-audit` (no `\|\| true`) + `osv-scanner -r .` over `uv.lock` | AUTO-GATE |
| Node vulns [SEC-12] | zero HIGH+CRITICAL | `npm audit --audit-level=high` | AUTO-GATE (frontends and Node Lambda handlers) |
| Transitive coverage [SEC-13] | lockfile present & scanned | `osv-scanner` fails if no `uv.lock`/`package-lock.json` | AUTO-GATE |
| Update automation [SEC-14] | Dependabot or Renovate config present (Scorecard `Dependency-Update-Tool`) | committed `dependabot.yml`/`renovate.json` | AUTO-GATE |
| Open critical alerts [SEC-15] | none merge-able | branch ruleset blocks merge on open Dependabot alert CVSS ≥ 7.0 | AUTO-GATE |
| Unfixable HIGH/CRITICAL waiver [SEC-16] | tracked + VEX-justified | committed `vex.json` (CycloneDX 1.7 VEX), quarterly review | REVIEW-GATE |

Repositories that fetch untrusted archives, spawn subprocesses, or process
sensitive transit or location data adopt the full SCA and secret-scan set before
lower-risk repositories. Current project prioritization lives in the private
remediation registry.

### Secret scanning — gitleaks (Gate 1+2) + TruffleHog (Gate 3)

Two-gate gitleaks: **pre-commit** (Gate 1) and **CI diff** (Gate 2). TruffleHog runs a scheduled full-history scan (Gate 3).

Gate 3 must report **all three** TruffleHog result tiers. `verified` means the credential authenticated against the live service; `unverified` means TruffleHog asked and the service said **no**; `unknown` means it could not ask. A credential that was committed and later **revoked** comes back `unverified` — the revocation is what makes the provider say no — and a cleaned-up leak is the case a full-history scan exists for. `--only-verified` and `--results=verified,unknown` exclude that tier under two different names, and both produce a scheduled scan that cannot fail on a real incident. Measured 2026-09-06 on a throwaway clone with a real-shaped AWS key planted in one commit and deleted in the next: `--results=verified` and `--results=verified,unknown` each exited 0 reporting nothing; `--results=verified,unknown,unverified` exited 183 with `unverified_secrets: 1`. If a placeholder fixture fires, exclude that **detector** by name (`--exclude-detectors=<Name>`); never narrow the tier.

| Gate | Tool | Target | Gate |
|---|---|---|---|
| 1 pre-commit [SEC-17] | gitleaks `v8.30.1` | zero unredacted matches | AUTO-GATE |
| 2 CI diff [SEC-18] | gitleaks `--exit-code 1 --redact` (no `\|\| true`) | zero matches | AUTO-GATE |
| 3 scheduled [SEC-19] | `trufflehog git --results=verified,unknown,unverified --fail` | zero findings in any reported tier | AUTO-GATE (page on hit) |

```yaml
# .pre-commit-config.yaml — Gate 1
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks: [{ id: gitleaks }]
```

This pre-commit configuration is **mandatory** in every repository; the gitleaks + ruff + mypy hooks are the required floor.

---

## 5. Input validation & authz testing (ASVS V8 / L2)

L1 floor (AUTO-GATE, all repos with ingress): parameterized queries only (no string-built SQL — Semgrep rule), output encoding on all user-controlled HTML sinks (XSS), TLS 1.2+ asserted, server-side function-level authz (V8.2.1) and object-level authz (V8.2.2).

L2 (AUTO-GATE, PII repos): an integration suite asserting **every protected endpoint returns 403 to an unauthorized principal** and that object-level (BOLA/IDOR) and field-level (BOPLA) access is denied cross-tenant. Block deploy if any protected route lacks a negative-path test.

```python
# tests/test_authz.py — the negative-path assertion, every protected route
@pytest.mark.parametrize("route", PROTECTED_ROUTES)
def test_unauthorized_principal_gets_403(client, route):
    assert client.get(route, headers=other_tenant_token()).status_code == 403
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Injection / XSS [SEC-20] | zero | Semgrep taint rules + DAST in staging | AUTO-GATE |
| Function-level authz [SEC-21] | every protected route 403s unauth | parametrized integration test | AUTO-GATE (L2) |
| Object-level authz (BOLA) [SEC-22] | cross-tenant access denied | integration test w/ second principal | AUTO-GATE (L2) |
| OAuth/OIDC (V10) [SEC-23] | PKCE enforced; `acr`/`amr` validated; sender-constrained tokens | security architecture review | REVIEW-GATE (identity-critical services) |
| Annual pentest (BOLA/BOPLA/tenant) [SEC-24] | report attached to release | manual + human triage | REVIEW-GATE (L2 PII repos) |

---

## 6. Supply chain: pin Actions, SBOM, signing, provenance, Scorecard

Mutable action references are an active supply-chain threat: the **March 2026 trivy-action force-push** and **tj-actions** compromises were real exfiltration events, not hypotheticals. Adoption status stays in the private remediation registry.

> This section owns the supply-chain **machinery** (SBOM, signing, provenance) that a release *invokes*. The release **process and policy** — SemVer, signed tags, CHANGELOG, the trusted-main signed-tag pipeline, and Trusted Publishing — lives in `RELEASE-AND-VERSIONING-STANDARD.md`. When that standard says "sign + attest → SECURITY §6," this is the section it means.

### 6.1 Pin every Action to a full 40-char commit SHA — AUTO-GATE

Every `uses:` — third-party actions, `actions/*`, **reusable workflows, and the deploy path** — is pinned to a full 40-char commit SHA with a trailing `# vX.Y.Z` comment. Tags and branches are immutable-reference failures. Partial adoption does not pass: one moving reference in a preview or deploy workflow fails the gate.

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

Migration: run StepSecurity Secure-Repo (`step-security/secure-repo`) or `pin-github-action` over each workflow to auto-generate SHA-pinned stubs.

```bash
npx pin-github-action .github/workflows/*.yml   # rewrites tags -> SHA + comment
```

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Every `uses:` SHA-pinned [SEC-25] | 100% incl. reusable + deploy | Scorecard `Pinned-Dependencies` **≥ 9/10** on default branch | AUTO-GATE |
| SHAs kept current [SEC-26] | Renovate active, 72h cooldown | committed `renovate.json` | AUTO-GATE |

### 6.2 SBOM — CycloneDX 1.7 — AUTO-GATE on every release

Generate a **CycloneDX 1.7** (ECMA-424) SBOM for every release artifact and every container image; validate against schema before signing; fail the build on schema failure. Rejected SPDX-only: CycloneDX 1.7's attestation + VEX + ML-BOM `modelCard` shapes fit our SLSA and AI-repo needs better; both are NTIA/CISA/EU-CRA accepted.

```bash
syft . -o cyclonedx-json=sbom.cdx.json            # or: cdxgen -t python -o sbom.cdx.json
cyclonedx-cli validate --input-file sbom.cdx.json --input-version v1_7
grype sbom:sbom.cdx.json --fail-on high            # gate the SBOM itself
```

Required component fields: `name`, `version`, `purl`, `hashes` (SHA-256). AI/RAG repos additionally emit an ML-BOM `modelCard` component for each model dependency (ties to the model-card lint in `AI-EVALUATION-STANDARD.md`).

### 6.3 Container CVE scanning — AUTO-GATE for every Dockerfile repo

Trivy/Grype image scan, threshold standardized to **CRITICAL,HIGH** portfolio-wide. A CRITICAL-only threshold is raised; any repository that builds an image must run the scan.

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
  - uses: actions/attest-build-provenance@<40-char-sha> # v2.x  (SLSA build provenance; no Source level, see CI-CD §5)
    with: { subject-path: 'dist/*' }
```

Caching is **disabled** in any job that signs/publishes/generates provenance (cache poisoning violates SLSA isolation). Concurrency group on release jobs. Both rules cross-reference `CI-CD-STANDARD.md`.

Deployment-side: consumers verify before install.

```bash
cosign verify --certificate-oidc-issuer=https://token.actions.githubusercontent.com \
  --certificate-identity-regexp='^https://github.com/<org>/<repo>/' $IMAGE
slsa-verifier verify-artifact --provenance-path dist/<artifact>.intoto.jsonl \
  --source-uri github.com/<org>/<repo> dist/<artifact>
```

### 6.5 OpenSSF Scorecard — required check

`ossf/scorecard-action` nightly + on PRs to default branch; SARIF to Code Scanning.

| Scorecard check | Target | Gate |
|---|---|---|
| `Pinned-Dependencies` [SEC-31] | ≥ 9/10 | AUTO-GATE |
| `Token-Permissions` [SEC-32] | 10/10 | AUTO-GATE |
| `Dangerous-Workflow` [SEC-33] | 10/10 | AUTO-GATE |
| `Branch-Protection` [SEC-34] | ≥ 8/10 | AUTO-GATE |
| `Signed-Releases` [SEC-35] | 10/10 (`.intoto.jsonl` on last 5) | AUTO-GATE (release repos) |
| `Vulnerabilities` [SEC-36] | 10/10 | AUTO-GATE |
| Aggregate [SEC-37] | ≥ 8/10 | AUTO-GATE |
| Monthly Scorecard report committed [SEC-38] | present, dated | REVIEW-GATE |

### 6.6 Third-party scripts on public sites: an allowlist held by a test — AUTO-GATE

A script that a public page loads from a third party is a dependency that ships to every visitor, runs with the page's full authority, and is invisible to every scanner above, because they read the repository and not the page. It is also the whole of a site's privacy claim: "no tracking", or "Google Analytics 4 and nothing else", is exactly as true as the pages are. A claim that no test holds can go false in one commit without turning anything red.

**Why this is a rule.** On 2026-09-17/18, Google Analytics 4 was added to 26 portfolio sites in one wave. Several of those sites said "no tracking", "no analytics" or "no third-party requests" in their pages, READMEs and threat models, and the change would have made each statement false without failing a build. One site did not change silently: `id-churn-sentinel`'s merge-blocking gate held its pages to zero third-party requests and stopped the first attempt. Its ADR 0004 then changed the gate instead of disabling it: exactly one loader allowed, matched by its whole text and by a SHA-256 digest pinned outside the module that renders it, only inside `<head>`; every other script, font, pixel, beacon and third-party host still failing; and negative controls that sabotage the page and assert that the gate goes red. That gate is the model for this section.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Third-party scripts are an allowlist held by a test [SEC-43] | the site commits `third-party-scripts.json`; a test in the suite CI runs reads it and fails on any script, tracker, pixel or third-party host that is not on it, and on a privacy page whose stated analytics differ from it | the repository's own test and its negative controls; `automation/published_output_controls.py` checks the wiring (conformance key `third_party_script_allowlist`) | AUTO-GATE (report-only through 2026-10-18) |

**The allowlist** is `third-party-scripts.json` at the repository root:

```json
{
  "privacy_page": "site/privacy.html",
  "first_party_hosts": ["example.org"],
  "scripts": [
    {
      "vendor": "Google Analytics 4",
      "src": "https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX",
      "sha256": "<SHA-256 of the exact loader text the page carries>",
      "position": "head"
    }
  ]
}
```

Each entry names its `vendor`, is pinned by its full `text` or by its `sha256` (when both are given, the digest must be the digest of the text), and states its `position`: `head` or `body`. `src` names the external address the entry loads, and `first_party_hosts` lists the hosts that are the site itself. A site that loads no third-party script commits `"scripts": []`. The empty list is the claim, and the test holds it like any other.

**The test** runs in the suite CI runs, and:

1. matches every allowlisted script to its pinned text or digest, at its position. One changed character makes it a different script, which fails as a stray;
2. fails on everything else: any other `<script>`, inline or external; a tracking pixel, beacon or iframe; and any request to a host that is neither first-party nor on the list. It checks every published page and artifact, not only the front page;
3. checks that the privacy page names each allowlisted vendor and what that vendor receives, and states no analytics that the list does not contain. With an empty list, the page claims none;
4. carries negative controls: it sabotages a page (a second script, a changed loader, a pixel, the loader in the body), asserts that each sabotage landed, and asserts that each one fails;
5. pins the digest of a script that code renders outside the module that renders it, so changing the loader takes two deliberate edits, not one.

Changing what a site loads, or what a vendor receives, is a decision record (ADR), not just a new digest.

**Applicability.** Every repository whose `applicability.yml` entry has `hosted: true` and `html: true`.

**Conformance control.** `third_party_script_allowlist` passes when the allowlist parses as above, the privacy page exists and names every allowlisted vendor, a test file reads `third-party-scripts.json`, a workflow runs the test suite, and no committed HTML page outside test fixtures has a `<script src>` on a host that is neither allowlisted nor first-party. It proves the wiring; the repository's own test proves the pages. It is report-only through 2026-10-18 and scored from 2026-10-19 (`automation/report_only.py`).

---

## 7. Least-privilege tokens, OIDC, branch protection, workflow SAST

Owned in detail by `CI-CD-STANDARD.md`; the supply-chain-load-bearing minimums repeated here so a repo author can't miss them:

| Control | Target | Measured by | Gate |
|---|---|---|---|
| Top-level `permissions` [CICD-02] | `contents: read`, per-job escalation only | present in every workflow | AUTO-GATE |
| Cloud creds [CICD-05, CICD-06, CICD-07] | OIDC only, no long-lived secrets, sub scoped to `repo:…:environment:…` | audit-log alert on new long-lived secret | AUTO-GATE |
| Workflow SAST [CICD-19] | `zizmor` required check on any PR touching `.github/workflows/` | merge-blocked on high/critical | AUTO-GATE |
| `persist-credentials: false` [SEC-39] | on every `actions/checkout` | zizmor / grep | AUTO-GATE |
| No unrecorded push to `main` [CQ-37, CICD-15] | branch ruleset blocks every push but the accountable maintainer's standing admin bypass, which is break-glass and recorded per use; normal/solo review disposition follows CQ §7.1. Tag rulesets keep an empty bypass list; branch rulesets never do (CICD §5) | committed ruleset export + bypassed-merge attestation | AUTO+REVIEW-GATE |
| CODEOWNERS routes `.github/workflows/` + security-critical files [CICD-17] | routing present in both profiles; approval mechanics are owned by CICD-18 / CQ §7.1 | committed `CODEOWNERS` | AUTO-GATE |
| Branch ruleset + CODEOWNERS as committed artifacts [CICD-12] | present | repo files | REVIEW-GATE |

```yaml
# zizmor as a required check (same trigger as CI-CD §7)
on:
  pull_request: { paths: ['.github/workflows/**', '.github/actions/**'] }
permissions:
  contents: read
  security-events: write   # SARIF upload only
jobs:
  zizmor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-char-sha> # v4.2.2
        with: { persist-credentials: false }
      - uses: zizmorcore/zizmor-action@<40-char-sha> # v0.x
```

### 7.1 Infrastructure as code: what is committed is what is live — AUTO-GATE

A security header, a Content Security Policy, a bucket policy or an IAM grant that lives in committed infrastructure-as-code is reviewed, merged, and then **in force only if something applies it**. On 2026-09-18, three sites (`afterward`, `transit-delivery-atlas`, and one private site) had merged CSP and security-header changes in CloudFormation templates or edge configuration that no pipeline applied: their CI deployed site content (`aws s3 sync`) and never touched the stack, and the private site's edge reconciliation is a `workflow_dispatch`-only workflow. The committed configuration allowed GA4 and the live configuration blocked it, silently, until someone applied the templates by hand. Every check was green, because every check read the repository and none read the account.

| Metric | Requirement | Measured by | Gate |
|---|---|---|---|
| Committed IaC is applied by CI or checked for drift [SEC-44] | A repository that commits IaC (CloudFormation/SAM templates, Terraform, CDK, Pulumi, Serverless) either **applies it from CI on an automatic trigger** (push, tag push, schedule, `workflow_run`; declared as `iac: applied-by-ci` in `applicability.yml`), or **runs a scheduled drift check** that fails when the live stack differs from the committed definition | `conformance_check.py` `iac_drift_check` | AUTO-GATE (report-only through 2026-10-18) |

**A drift check is one that can fail.** Accepted shapes, run from a `schedule:`-triggered workflow: `aws cloudformation detect-stack-drift` (then `describe-stack-resource-drifts`), plus a template diff against the deployed stack (`aws cloudformation get-template`) for properties drift detection does not cover; `terraform plan -detailed-exitcode` (exit 2 means changes are pending); `cdk diff --fail`; `driftctl`; or a repository command named for what it compares (`deploy-drift`, `stack-drift`, `iac-drift`). A bare `cdk diff` or `terraform plan` exits 0 on drift and is not a check. A comparison that runs only on `workflow_dispatch` asks only when someone remembers to ask, which is the failure this control exists for. A failing scheduled run is the alert; route it wherever the repository's scheduled failures already go.

**"Applied by CI" is a declaration, and it is checked.** `iac: applied-by-ci` in `applicability.yml` passes only when some workflow with an automatic trigger actually runs an apply (`terraform apply`, `cdk deploy`, `cloudformation deploy`, `sam deploy`, `pulumi up`, …). A `workflow_dispatch`-only apply is applied by whoever remembers, so it does not count. A repository that applies automatically but has not declared it fails with a hint to declare it: the manifest stays the source of truth for scope, and an undeclared deploy is exactly the thing a reader of the manifest cannot see.

**Prior art in this portfolio.** A private monitoring service's `deploy-drift.yml` compares its synthesized CDK template with the live stack daily; it was written after a five-day outage in which CloudFormation read `UPDATE_COMPLETE` while the function AWS ran was still the old configuration. `family-greenhouse` commits its live `protect-main` ruleset as `.github/rulesets/main.json`, with the regeneration command beside it and a recorded committed-versus-live reconciliation, and `automation/check_ruleset_profile.py --hosted` checks the same parity for this repository. SEC-44 asks the same question of the rest of the account.

A template that is committed but deliberately not deployed (a planned or decommissioned stack) still needs one of the two: a drift check that asserts the stack is **absent** (as that monitoring service does for its decommissioned stacks), or a waiver in `waivers.yml` with its reason and expiry.

---

## 8. Per-repo declarations (no silent skips)

Every repo's `docs/RESPONSIBLE-TECH-AUDITS.md` §F records, with no blanks:

1. **ASVS level** (L1 / L2 / L3 / `N/A (reason)`).
2. **Container scanning**: enabled, or `N/A (no Dockerfile)`.
3. **SBOM + signing**: enabled on release, or `N/A (not a release-producing repo)` — note this is rare; libraries published to PyPI **do** produce releases.
4. **Secret-management policy** (OSPS-BR-07.02): storage, rotation, revocation — committed once, reviewed annually.
5. **VEX** for any unfixable HIGH/CRITICAL dependency CVE.

An N/A is a *declared decision with a one-line reason*, reviewed like any other. A blank is a defect.

### Cross-repository reconciliation

- A duplicated or renamed package records one canonical repository before
  controls are applied, preventing drift and double-counting. **REVIEW-GATE.**
- A nested project declares its package path or exposes repository-root
  verification so portfolio tooling cannot silently skip it. **AUTO-GATE.**

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
