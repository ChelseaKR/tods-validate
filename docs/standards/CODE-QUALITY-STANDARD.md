# Code Quality Standard

This is the canonical definition of **what a healthy source tree looks like** across this portfolio, and the mechanism by which each rule is **enforced** rather than recommended. Languages, versions, linters, type checkers, test floors, complexity ceilings, layout, dependency management, and review process live here once. Repos override the *values* permitted below (a hobby logger may target 85% coverage; a published library targets 90%) and record only project-specific findings — they never re-derive the structure.

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI and reproduced by `make verify`) or **REVIEW-GATE** (requires accountable human judgment, paired with a checklist item and a dated durable artifact—committed by default, or authenticated current-head metadata where this standard explicitly requires it). There is no "aspirational" third category. Ambiguity is a defect: if a rule cannot be reduced to a number plus a tool, it does not belong here.

> **Scope boundary.** This document owns *intrinsic code quality*: language/version, lint, format, types, tests, complexity, layout, deps, docstrings, review, ADRs. Cross-cutting rigor lives in sibling standards and is referenced, not repeated: supply-chain pinning and signing → `SECURITY-AND-SUPPLY-CHAIN-STANDARD`; workflow hardening/OIDC/branch protection → `CI-CD-STANDARD`; logging/OTel/SLOs → `OBSERVABILITY-STANDARD`; catalogs/key-parity → `INTERNATIONALIZATION-STANDARD`; axe/Lighthouse/SR walkthroughs and the provisional solo-maintainer disposition → `ACCESSIBILITY-STANDARD` §2.0; RAG/red-team thresholds → `AI-EVALUATION-STANDARD`; DORA + Definition-of-Done → `QUALITY-AND-METRICS-STANDARD`; ISO 25010 attribute map → `QUALITY-AND-METRICS-STANDARD`; audit artifacts → `RESPONSIBLE-TECH-FRAMEWORK`.

---

## 0. Why this exists now

Python repositories use ruff, mypy, pytest, a committed `uv.lock`, and
`make verify` parity with CI. The defect this standard prevents is **drift**:
incompatible linter/type-checker floors, inconsistent coverage thresholds,
split configuration, or project tooling hidden below the repository root. This
standard pins the canonical floors so the stack is *one* stack.

The mechanisms below are established engineering patterns; this document names
their versions and makes their enforcement portfolio-wide.

---

## 1. Languages & runtime versions

Pinned floors. A repo above the floor is conformant; a repo below it is a defect. New repos start at the floor.

| Language | Min version | Pin mechanism | Gate |
|----------|-------------|---------------|------|
| Python [CQ-01] | `requires-python = ">=3.12"` (3.13 preferred for new repos; 3.11 EOL-track only with a justified ADR) | `[project].requires-python` + committed `.python-version` (`uv python pin`) | AUTO-GATE |
| TypeScript [CQ-02] | 5.9+ (5.6+ required for `strictBuiltinIteratorReturn`) | `devDependencies.typescript` + `tsc --noEmit` | AUTO-GATE |
| Node (frontends/Lambda) [CQ-03] | 22 LTS | `package.json` `engines.node` + `.nvmrc` | AUTO-GATE |

Rationale: Python 3.10 reaches EOL October 2026; pinning ≥3.12 buys structural-pattern-matching and `tomllib` everywhere and removes the 3.10/3.11 conditional-import branches that inflate complexity. **Rejected:** floating `requires-python = ">=3.9"` — keeps dead compat branches alive and blocks `match` adoption.

---

## 2. Python toolchain (canonical floors)

The entire toolchain consolidates into a single root `pyproject.toml`. **No** `ruff.toml`, `pytest.ini`, `mypy.ini`, `setup.py`, `setup.cfg`, `tox.ini`, `.flake8`, or `requirements.txt` (lockfile excepted). Nested or split configuration must migrate to the repository root.

| Concern | Tool | Canonical pin / target | Measured by | Gate |
|---------|------|------------------------|-------------|------|
| Lint + format + import-sort + modernize + bandit [CQ-04] | **ruff** | `>=0.15.0` (current 0.15.x); `select=[E,W,F,I,UP,B,SIM,S,C90,RUF]`, `ignore=[E501]` | `ruff check` (exit≠0 fails) + `ruff format --check` | AUTO-GATE |
| Cyclomatic complexity [CQ-05] | ruff C901 | `max-complexity = 10` | same `ruff check` run | AUTO-GATE |
| Static typing [CQ-06] | **mypy `--strict`** (pin `>=1.18`) — or **pyright `strict`** / **pyrefly `>=1.1`** for new repos wanting speed | **zero** errors | `mypy --strict` (or `pyright`/`pyrefly check`) exit≠0 fails | AUTO-GATE |
| Test runner [CQ-07] | **pytest** | `>=8.0` (`minversion = "8.0"`); `--strict-markers --strict-config --import-mode=importlib` | `pytest` exit code | AUTO-GATE |
| Coverage (branch) [CQ-08] | **pytest-cov** + coverage.py 7.x | **≥85% branch** (applications) / **≥90%** (published libraries); `branch = true` | `--cov-fail-under` exit≠0 fails | AUTO-GATE |
| Dependency resolution [CQ-09] | **uv** | `>=0.11.0`; `uv.lock` committed; CI runs `uv sync --frozen` | lockfile-drift check + frozen install | AUTO-GATE |
| Build backend [CQ-10] | **hatchling** | `build-backend = "hatchling.build"` | wheel build in CI | AUTO-GATE |
| CVE scan (deps) [CQ-11] | **pip-audit** | block on fixed HIGH+CRITICAL — **`\|\| true` is forbidden** | `pip-audit` exit code (see §9) | AUTO-GATE |
| Dev-side fast feedback [CQ-12] | **pre-commit** | ruff hooks pinned to `v0.15.x`; mypy/pyright as pre-push | local + `pre-commit.ci` | REVIEW-GATE |

**Single-source ruff/mypy/pytest config** (paste into root `pyproject.toml`; this is the portfolio default — repos change values, not keys):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
requires-python = ">=3.12"

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "S", "C90", "RUF"]
ignore = ["E501"]            # line length owned by the formatter
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]       # assert is expected in tests
[tool.ruff.lint.mccabe]
max-complexity = 10
[tool.ruff.format]
quote-style = "double"

[tool.mypy]
strict = true
warn_return_any = true
disallow_untyped_defs = true
# pyright/pyrefly equivalent: typeCheckingMode = "strict"

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config --import-mode=importlib"
markers = [
  "slow: > 2s",
  "integration: requires an external service",
  "smoke: critical path",
]

[tool.coverage.run]
branch = true
source = ["src"]
[tool.coverage.report]
fail_under = 85             # libraries: 90
show_missing = true
```

**CI / `make verify` body** (the two MUST be identical — this is the portfolio's drift-killer; do not let them diverge):

```make
verify:
	uv sync --frozen
	ruff check .
	ruff format --check .
	mypy --strict src        # or: pyright  /  pyrefly check
	pytest -n auto --cov=src --cov-branch --cov-report=xml --cov-fail-under=85
	pip-audit                # no `|| true`; see SECURITY-AND-SUPPLY-CHAIN-STANDARD
```

### Per-module coverage floors — security/crypto-critical paths [CQ-48]

The 85%/90% floor is a repo-wide *average*; an average lets the exact modules where a missed branch is a safety or evidence-integrity defect hide behind well-covered glue. Modules on a **security-, crypto-, or safety-critical path** therefore carry a **per-module ≥95% coverage.py line+branch floor with branch measurement enabled**, above the baseline (AUTO-GATE).

**Mechanism** (coverage.py has no native per-module `fail_under`): after the
normal `pytest --cov` run has written `.coverage`, emit its JSON report and run
the portfolio checker against every declared critical module—in the Makefile
test/cov target **and** the CI step that mirrors it:

```make
	coverage json -o coverage.json
	python3 .standards/automation/check_critical_coverage.py coverage.json \
		--minimum 95 \
		--module "src/package/crypto.py" \
		--module "src/package/auth/*.py"
```

Every declared path/glob must match, and **every matched file passes
independently**. Do not substitute `coverage report --include=... --fail-under=95`:
that command averages the selected files and lets a 100% utility hide a
below-floor critical sibling—the same defect this control exists to prevent.

The critical set is declared per repository in the Makefile next to the check,
with a comment naming this section. Typical critical paths include cryptographic
verification, access policy, consent enforcement, citation guards, and identity
resolution. Adding a module to the set is one line; removing one is a
REVIEW-GATE decision that must say why the path is no longer critical.

**Drift remediation (mandatory, tracked privately per repository):** raise ruff
to `>=0.15.x`; pin mypy `>=1.18`; set `--cov-fail-under` everywhere it is
unset; consolidate configuration and `uv.lock` at the repository root; and run
a `pyright`/`pyrefly` benchmark before any mypy-to-pyright swap.

---

## 3. TypeScript / frontend toolchain

Applies to every TypeScript frontend, map UI, and Lambda handler. One `eslint.config.mjs` (flat config; legacy `.eslintrc` is unsupported in ESLint v10). Prettier is a **separate** step, never an ESLint rule.

| Concern | Tool | Canonical target | Measured by | Gate |
|---------|------|------------------|-------------|------|
| Type strictness [CQ-13] | `tsc --noEmit` | `strict: true` **plus** `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noUnusedLocals`, `noUnusedParameters`, `noImplicitOverride`, `noFallthroughCasesInSwitch` | `tsc --noEmit` exit code | AUTO-GATE |
| Lint [CQ-14] | ESLint v10 flat + typescript-eslint v8 | `strictTypeChecked` + `stylisticTypeChecked` + `react-hooks/recommended` (incl. `exhaustive-deps`) + `jsx-a11y/recommended`; `--max-warnings 0`; `eslint-config-prettier` last | `eslint .` exit code | AUTO-GATE |
| Format [CQ-15] | Prettier 3 | `singleQuote:true, trailingComma:"all", printWidth:100, semi:true`; run via `prettier --check .` | separate CI step | AUTO-GATE |
| Unit/component tests + coverage [CQ-16] | Vitest v4 (`provider:"v8"`) | lines/branches/functions/statements **≥80%**, `coverage.perFile: true` | threshold exit code | AUTO-GATE |
| E2E [CQ-17] | Playwright | Chromium min; `retries:2`, `forbidOnly:!!process.env.CI` | suite exit code | AUTO-GATE |
| Bundle budget [CQ-18] | size-limit v12 | critical-path JS **≤170 KB gzip** | `andresz1/size-limit-action` PR gate | AUTO-GATE |
| Chunk warning [CQ-19] | Vite 8 | `build.chunkSizeWarningLimit: 500`; `target:"baseline-widely-available"` | build log + reviewer | REVIEW-GATE |
| Bundle composition [CQ-20] | rollup-plugin-visualizer | committed HTML artifact for any PR adding a dep >50 KB gzip; no duplicate React/date libs | reviewer | REVIEW-GATE |
| SCA [CQ-21] | `npm audit --audit-level=high` / OSV-Scanner | block on fixed HIGH+CRITICAL | exit code | AUTO-GATE |

`noEmit: true`, `isolatedModules: true`, `moduleResolution: "bundler"`, `module: "ESNext"` are required (emit belongs to Vite/esbuild, not `tsc`).

**Biome v2** is an acceptable single-binary replacement for ESLint+Prettier **only on a greenfield TS repo that does not need `react-hooks/exhaustive-deps` or type-aware rules** (`no-floating-promises`). A hook-using frontend keeps the ESLint stack. A repo choosing Biome records the rule-gap audit as an ADR (REVIEW-GATE). **React Compiler** (`babel-plugin-react-compiler`) is opt-in per-file (`compilationMode:"annotation"`) and REVIEW-GATE: validate output in Vitest before enabling, then strip the now-redundant manual `useMemo`/`useCallback`.

---

## 4. Project layout

| Rule | Requirement | Gate |
|------|-------------|------|
| Python package location [CQ-23] | `src/<package>/` (PyPA src layout); `[tool.hatch.build.targets.wheel] packages = ["src/<package>"]`; never import from repo root without editable install | REVIEW-GATE (caught by `make verify` running against the installed wheel) |
| Tests location [CQ-24] | `tests/` at repo root, never inside `src/` | AUTO-GATE (ruff/pytest paths) |
| Config location [CQ-25] | exactly one root `pyproject.toml` (TS: one `package.json` + `eslint.config.mjs` + `vitest.config.ts`); no nested or duplicate config | AUTO-GATE (a repo-root config-presence check) |
| Monorepo-style nesting [CQ-26] | forbidden unless declared in an ADR | REVIEW-GATE |

Any repository with project configuration below the root surfaces a root
`pyproject.toml`, `Makefile`, and `uv.lock`; any flat-layout service adopts
`src/` plus root configuration.

---

## 5. Dependency management

| Rule | Requirement | Gate |
|------|-------------|------|
| Lockfile [CQ-09] | `uv.lock` committed; CI installs with `uv sync --frozen` (fails if lock is stale) | AUTO-GATE |
| Dev deps [CQ-27] | declared in PEP 735 `[dependency-groups]` (not `[project.optional-dependencies]`) so linters/type-checkers never ship as extras | AUTO-GATE (lint of `pyproject.toml`) |
| Hash pinning (deployed services) [CQ-28] | `uv pip compile --generate-hashes` for the deployed requirement set | REVIEW-GATE |
| Update bot [CQ-29] | Dependabot **or** Renovate enabled (`minimumReleaseAge: 72h`); required for OpenSSF Scorecard `Dependency-Update-Tool` | REVIEW-GATE (artifact: committed config) |
| Adding a dependency [CQ-30] | new runtime dep requires a one-line rationale in the PR; new dep >50 KB gzip (TS) requires a visualizer artifact (§3) | REVIEW-GATE |

GitHub Actions SHA-pinning, SBOM, Sigstore signing, and SLSA provenance are **not** specified here — see `SECURITY-AND-SUPPLY-CHAIN-STANDARD`. This document only requires that application/library dependencies are locked and scanned.

---

## 6. Docstrings, comments, and dead-code hygiene

| Rule | Requirement | Gate |
|------|-------------|------|
| Module docstring [CQ-31] | every Python module and every public TS module has a one-line purpose statement | AUTO-GATE (ruff `D`-subset where enabled; else REVIEW-GATE via checklist) |
| Public API docstrings [CQ-32] | every public function/class/CLI flag documents intent, args, raises/returns | REVIEW-GATE (paired with `DOCUMENTATION-STANDARD`) |
| Comments explain *why* [CQ-33] | comments justify non-obvious decisions, not restate code | REVIEW-GATE |
| **No `TODO`/`FIXME`/`HACK` without a linked issue** [CQ-34] | every such marker carries an issue URL, e.g. `# TODO(#142): ...`; bare markers fail CI | AUTO-GATE |
| No `type: ignore` / `eslint-disable` / `# noqa` without a linked issue [CQ-35] | each suppression carries a code *and* an issue reference; blanket ignores fail CI | AUTO-GATE |
| Commented-out code [CQ-36] | forbidden on `main`; delete it (git is the archive) | REVIEW-GATE |

Bare-TODO gate (drop into CI; portfolio-standard regex):

```bash
# fails if any TODO/FIXME/HACK lacks a (#NNN) or full issue URL on the same line
! grep -rEn '(TODO|FIXME|HACK)' --include='*.py' --include='*.ts' --include='*.tsx' src \
  | grep -Ev '\(#[0-9]+\)|https?://[^ ]+/issues/[0-9]+'
```

---

## 7. Code review rules

| Rule | Requirement | Gate |
|------|-------------|------|
| PR required [CQ-37] | no direct pushes to `main`; projects with ≥2 active maintainers require ≥1 approving review from someone other than the last pusher (≥2 for auth, PII, payment, safety-critical, prompt/retrieval paths); an eligible one-person project uses the solo record below with platform approval count 0 | AUTO+REVIEW (branch ruleset + `check_solo_governance.py --hosted` — see `CI-CD-STANDARD`) |
| Stale reviews [CQ-38] | dismissed on new commits | AUTO-GATE |
| CODEOWNERS [CQ-39] | committed; routes `.github/workflows/`, security-critical files, and `DEFINITION_OF_DONE.md`; the normal profile requires code-owner approval, while eligible solo mode retains routing without pretending self-approval | AUTO-GATE (existence) / REVIEW-GATE (routing correctness) |
| Status checks [CQ-40] | all CI jobs green, branch up to date (strict) | AUTO-GATE |
| Linear history + signed commits [CQ-41] | squash/rebase only; GPG/SSH signature verification on `main`. For an accessibility §2.0 release, merge the product PR first so protected `main` becomes tested source **P**, then merge a separate evidence-only PR whose net `P..HEAD` change is exactly the record | AUTO-GATE |
| PR template DoD [CQ-42] | every PR carries the `QUALITY-AND-METRICS-STANDARD` DoD checklist; merge blocked until checked | REVIEW-GATE |
| Self-merge [CQ-43] | prohibited when an eligible independent reviewer exists; an eligible sole maintainer may merge only through the PR UI/API after the current-head attestation below and every required AUTO-GATE passes—never by direct push or bypass | AUTO+REVIEW |

### 7.1 Solo-maintainer PR disposition

GitHub does not let an author approve their own PR, so self-review cannot truthfully satisfy an
independent-approval rule. While a project has exactly one active maintainer, its ruleset may set
`required_approving_review_count: 0` but still requires a PR, strict green status checks, stale-head
invalidation, signed commits, no direct push, and no force-push. This is a bounded governance mode,
not a claim that a second person reviewed the change.

After the final push, the sole maintainer adds an authenticated PR comment bound to the current head
SHA that records: the reviewed diff range; changed risk boundaries; all automated and model-assisted
review producers and versions; durable check/audit links; every finding and remediation; rollback;
and this decision:

> I am the sole active maintainer and reviewed the diff at `<head-sha>`. No independent human approval
> occurred. The linked automated and synthetic reviews are evidence, not reviewers. All required
> AUTO-GATEs passed, I accept the listed residual risks, and I authorize merge through the
> solo-maintainer path.

The authenticated comment URL is the REVIEW-GATE artifact. A new push invalidates it. The PR records
the exact decision text, comment URL, and head SHA in its merge/squash summary so the decision remains
discoverable from Git history. Synthetic or model-assisted review may find defects, but only the
maintainer makes the risk decision.

The ruleset requires the `solo-governance` status context. That job evaluates the proposed committed
profile and the live hosted profile together; branching only on the committed approval count is a
fail-open defect. Normal/hosted-solo fails. Proposed-solo/hosted-normal is allowed only as the
serialized activation state: the hosted review mechanics remain stricter, every other visible field
matches, and the exact current-head owner attestation binds the live ruleset ID/update time. Both-solo
requires exact visible parity and the same empty-bypass declaration. Both-normal retains platform
independent approval and proves API-visible parity without claiming that GitHub's redacted bypass
field was observed. See `CI-CD-STANDARD.md` §5.1 for the activation order. A unit-test-only job is not
sufficient evidence for an active solo profile.

The committed declaration follows `templates/solo-maintainer-governance.md` and deliberately stores
no PR SHA or comment URL. `automation/check_solo_governance.py` validates its exact schema, visible
owner statement, repository binding, clean tracked state, date/filename parity, and maximum 90-day
validity. Hosted mode discovers the PR head and comment through GitHub, then fails closed unless the
API proves the declared login is the sole push-capable human and authored the exact current-head
attestation. The ordinary read-only token also proves every visible active-ruleset field; GitHub
redacts `bypass_actors` without ruleset write access, so the owner comment binds the fetched ruleset
ID/update time and explicitly declares that list empty. PR code never receives a ruleset-write
credential. Missing API access, visible drift/bypass, stale ruleset identity, or a collaborator count
that cannot be proven is a failed gate.

Status-check names are repository-specific rather than hardcoded to this standards repo. The generic
validator accepts a non-empty unique set, each repository passes its expected set explicitly, and the
hosted comparison requires exact parity with the committed set. Once any dated solo-governance,
synthetic-evidence, or deployment-decision record reaches the base branch it is append-only; renewal
adds a new dated record rather than rewriting audit history.

That current-head comment disposes the PR merge only; it is not standing deployment approval. A
solo production/staging promotion requires the separate final record and authenticated human
decision in `templates/solo-maintainer-deploy-decision.md`, validated immediately before promotion
with `automation/check_solo_deploy_decision.py --artifact --attestation-bundle`. The deploy gate
binds signed provenance, the exact tested source and candidate digest, permits exactly zero or one
intervening bound canonical synthetic-accessibility record, and requires the final commit to add
only the decision record. It also proves the merged same-repository decision PR and current `main`,
live ruleset identity/parity, local rollback evidence, and the job-scoped environment/full-gate/
digest-recheck/audited-promotion-command chain before promotion. See `CI-CD-STANDARD.md` §8a.

This mode is available only to an independent portfolio/open-source project with one active
maintainer and no independent reviewer on the project team. It is unavailable for a contractual,
procurement, formal-conformance, or legally required deliverable; a change that creates or expands an
auth, payment, PII, safety-critical, employment, healthcare, emergency, or public-benefit boundary;
or remediation of a verified user-impacting security, privacy, safety, or accessibility incident.
Those changes wait for independent human review. The mode ends immediately when a second maintainer
joins; branch and environment approval counts return to their normal floors before the next merge.

---

## 8. Architecture Decision Records (ADRs)

| Rule | Requirement | Gate |
|------|-------------|------|
| Location [CQ-44] | `docs/adr/NNNN-title.md`, MADR format (Context / Decision / Consequences / Status) | REVIEW-GATE |
| When required [CQ-45] | any choice that is expensive to reverse: language/runtime floor change, type-checker swap (mypy→pyright/pyrefly), Biome adoption, datastore, public API shape, security/PII boundary, **declaring a standard N/A** (§11) | REVIEW-GATE (checklist item; PR touching these without an ADR is rejected) |
| Immutability [CQ-46] | ADRs are append-only; supersede, never edit silently (set `Status: superseded by NNNN`) | REVIEW-GATE |

---

## 9. The merge-gate list (Python)

A merge to `main` requires **every** AUTO-GATE green and every applicable REVIEW-GATE disposition. Section 7.1 defines the authenticated sole-maintainer decision where an independent approval is structurally unavailable. An owning domain standard may also authorize a truth-labeled provisional release from synthetic evidence plus maintainer residual-risk acceptance while a named experiential REVIEW-GATE remains open; the gate stays unattested, and the release is neither conformance nor a third gate type. Accessibility's bounded pathway is `ACCESSIBILITY-STANDARD.md` §2.0. `make verify` reproduces all AUTO-GATEs locally and is byte-for-byte the CI body.

```
AUTO-GATE (CI, blocking):
  1. uv sync --frozen                         # lock not stale
  2. ruff check .                             # lint + imports + bandit(S) + complexity(C901≤10)
  3. ruff format --check .                    # formatting
  4. mypy --strict src                        # (or pyright / pyrefly check) — zero errors
  5. pytest -n auto --cov=src --cov-branch --cov-fail-under=85   # 90 for libraries
  6. pip-audit                                # fixed HIGH+CRITICAL block; NO `|| true`
  7. no bare TODO/FIXME/HACK; no un-issued suppressions
  8. single-root-config + src-layout presence check
REVIEW-GATE (human, attested in PR):
  9. src layout sane; public API docstrings; ADR present if §8 triggered;
     DoD checklist complete; CODEOWNERS routing correct
```

## 9a. The merge-gate list (TypeScript)

```
AUTO-GATE (CI, blocking):
  1. tsc --noEmit                             # strict + 7 beyond-strict flags
  2. eslint . --max-warnings 0                # strictTypeChecked + react-hooks + jsx-a11y
  3. prettier --check .
  4. vitest run --coverage                    # lines/branches/functions/statements ≥80, perFile
  5. playwright test                          # Chromium; forbidOnly in CI
  6. size-limit                               # critical-path JS ≤170 KB gzip
  7. npm audit --audit-level=high  (or OSV-Scanner)
  8. no bare TODO; no un-issued eslint-disable
REVIEW-GATE (human):
  9. visualizer artifact for deps >50 KB; React Compiler output validated;
     ADR if §8 triggered; DoD checklist complete
```

Accessibility (axe/Lighthouse/pa11y), observability, i18n key-parity, and AI-eval gates are **also** merge-blocking where applicable — they are specified in their own standards and surface here only as additional required status checks.

---

## 10. Mutation testing (quality of the tests themselves)

Line/branch coverage proves code *ran*, not that assertions *catch regressions*. For repositories whose correctness is load-bearing (AI/evaluation harnesses, access-policy guarantees, public-service grounding guards, and civic RAG citation guards), a mutation-testing pass quantifies test strength.

| Metric | Target | Tool | Gate |
|--------|--------|------|------|
| Mutation score (core safety modules) [CQ-47] | ≥70% killed | `mutmut` / `cosmic-ray` (Py), Stryker (TS) | REVIEW-GATE (nightly, not per-PR; surviving mutants triaged) |

REVIEW-GATE because run time makes it a poor per-PR blocker; the artifact is a committed mutation report regenerated per release.

---

## 11. When this standard does NOT apply — declare N/A, never skip silently

A repo that opts out of a rule records the decision; silence is a defect. The declaration lives in the repo's `README.md` "Standards conformance" block (or an ADR for §8 triggers) as `N/A — <reason>`.

| Rule | Legitimately N/A when… | Required declaration |
|------|------------------------|----------------------|
| TS/frontend toolchain (§3) | repo has no TypeScript surface | `frontend-quality: N/A — pure-Python service` |
| Coverage 90% library floor | repo is an application, not a published library | `coverage: app floor 85% — not a published library` |
| PyPI Trusted Publisher / attestations | repo is never published to an index | `publish: N/A — internal/site only` |
| Mutation testing (§10) | repo has no safety-critical module | `mutation: N/A — no load-bearing correctness guarantee` |
| Playwright E2E | library/CLI with no UI | `e2e: N/A — no browser surface` |
| Container CVE scan | repo ships no Dockerfile | `container-scan: N/A — no Dockerfile` |

What is **never** N/A for shipping code: ruff, type-checking, pytest+coverage floor, complexity ≤10, `uv.lock` frozen, dependency CVE scan, no-bare-TODO, PR review, single-root-config. A repo cannot declare these out of scope.

**Not-yet-implemented tools are not exempt from scaffolding:** their first
engineering milestone authors a root `pyproject.toml` with the §2 block,
`make verify` equal to CI, a `src/` layout, and `uv.lock` **before** feature code.
For a privacy-sensitive tool, this is sequenced after its consent gate.

---

## 12. Conformance ledger (per repo)

Each repo's `README.md` carries this table so a reader sees compliance at a glance. Values, not structure, vary.

| Control | This repo's value | Gate | Status |
|---------|-------------------|------|--------|
| ruff | `>=0.15.x`, full select set | AUTO | ✅ / ⛔ |
| type checker | mypy --strict @1.18 | AUTO | |
| branch coverage | ≥85% (lib: 90%) | AUTO | |
| max-complexity | 10 | AUTO | |
| `uv.lock` frozen | yes | AUTO | |
| dep CVE scan | pip-audit, no `\|\| true` | AUTO | |
| no bare TODO | enforced | AUTO | |
| src layout | yes | REVIEW | |
| ADRs | `docs/adr/` | REVIEW | |
| N/A declarations | listed with reasons | REVIEW | |

---

Last verified: 2026-06-21 · Recheck cadence: quarterly, and on any release of ruff (minor), uv (minor), mypy/pyright/pyrefly (minor), TypeScript (minor), ESLint/typescript-eslint (major), Vitest (major), or a new PEP affecting `pyproject.toml` / packaging.
