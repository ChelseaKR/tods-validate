# Code Quality Standard

This is the canonical definition of **what a healthy source tree looks like** across the ~18 repos in this portfolio, and the mechanism by which each rule is **enforced** rather than recommended. Languages, versions, linters, type checkers, test floors, complexity ceilings, layout, dependency management, and review process live here once. Repos override the *values* permitted below (a hobby logger may target 85% coverage; a published library targets 90%) and record only project-specific findings — they never re-derive the structure.

> **Enforcement is binary.** A control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI and reproduced by `make verify`) or **REVIEW-GATE** (requires human judgment, paired with a checklist item and a committed artifact). There is no "aspirational" third category. Ambiguity is a defect: if a rule cannot be reduced to a number plus a tool, it does not belong here.

> **Scope boundary.** This document owns *intrinsic code quality*: language/version, lint, format, types, tests, complexity, layout, deps, docstrings, review, ADRs. Cross-cutting rigor lives in sibling standards and is referenced, not repeated: supply-chain pinning and signing → `SECURITY-AND-SUPPLY-CHAIN-STANDARD`; workflow hardening/OIDC/branch protection → `CI-CD-STANDARD`; logging/OTel/SLOs → `OBSERVABILITY-STANDARD`; catalogs/key-parity → `INTERNATIONALIZATION-STANDARD`; axe/Lighthouse/SR walkthroughs → `ACCESSIBILITY-STANDARD`; RAG/red-team thresholds → `AI-EVALUATION-STANDARD`; DORA + Definition-of-Done → `QUALITY-AND-METRICS-STANDARD`; ISO 25010 attribute map → `QUALITY-AND-METRICS-STANDARD`; audit artifacts → `RESPONSIBLE-TECH-FRAMEWORK`.

---

## 0. Why this exists now

The Python core of this portfolio is already mature — ruff + mypy + pytest + committed `uv.lock` in a single `pyproject.toml`, with `make verify` byte-for-byte identical to CI in several repos. The defect is **drift**: four distinct ruff major-version floors for the same linter, mypy split across 1.10/1.11, coverage floors ranging from unset to 94%, `jobradar` with no `pyproject.toml` at all, `gtfs-scorecard` hiding its project under `pipeline/`, and `self-osint-monitor` with no toolchain. A passing build in one repo can fail in another running the same logical stack. This standard pins the canonical floors so the stack is *one* stack.

The work is propagation, not invention. Every rule below already exists in at least one repo; the rule names the version and makes it portfolio-wide.

---

## 1. Languages & runtime versions

Pinned floors. A repo above the floor is conformant; a repo below it is a defect. New repos start at the floor.

| Language | Min version | Pin mechanism | Gate |
|----------|-------------|---------------|------|
| Python | `requires-python = ">=3.12"` (3.13 preferred for new repos; 3.11 EOL-track only with a justified ADR) | `[project].requires-python` + committed `.python-version` (`uv python pin`) | AUTO-GATE |
| TypeScript | 5.9+ (5.6+ required for `strictBuiltinIteratorReturn`) | `devDependencies.typescript` + `tsc --noEmit` | AUTO-GATE |
| Node (frontends/Lambda) | 22 LTS | `package.json` `engines.node` + `.nvmrc` | AUTO-GATE |

Rationale: Python 3.10 reaches EOL October 2026; pinning ≥3.12 buys structural-pattern-matching and `tomllib` everywhere and removes the 3.10/3.11 conditional-import branches that inflate complexity. **Rejected:** floating `requires-python = ">=3.9"` — keeps dead compat branches alive and blocks `match` adoption.

---

## 2. Python toolchain (canonical floors)

The entire toolchain consolidates into a single root `pyproject.toml`. **No** `ruff.toml`, `pytest.ini`, `mypy.ini`, `setup.py`, `setup.cfg`, `tox.ini`, `.flake8`, or `requirements.txt` (lockfile excepted). This deletion is named for `jobradar` (splits config across `requirements.txt` + `ruff.toml` + `pytest.ini`, no mypy) and `gtfs-scorecard` (config under `pipeline/`, no top-level `uv.lock`).

| Concern | Tool | Canonical pin / target | Measured by | Gate |
|---------|------|------------------------|-------------|------|
| Lint + format + import-sort + modernize + bandit | **ruff** | `>=0.15.0` (current 0.15.x); `select=[E,W,F,I,UP,B,SIM,S,C90,RUF]`, `ignore=[E501]` | `ruff check` (exit≠0 fails) + `ruff format --check` | AUTO-GATE |
| Cyclomatic complexity | ruff C901 | `max-complexity = 10` | same `ruff check` run | AUTO-GATE |
| Static typing | **mypy `--strict`** (pin `>=1.18`) — or **pyright `strict`** / **pyrefly `>=1.1`** for new repos wanting speed | **zero** errors | `mypy --strict` (or `pyright`/`pyrefly check`) exit≠0 fails | AUTO-GATE |
| Test runner | **pytest** | `>=8.0` (`minversion = "8.0"`); `--strict-markers --strict-config --import-mode=importlib` | `pytest` exit code | AUTO-GATE |
| Coverage (branch) | **pytest-cov** + coverage.py 7.x | **≥85% branch** (applications) / **≥90%** (published libraries); `branch = true` | `--cov-fail-under` exit≠0 fails | AUTO-GATE |
| Dependency resolution | **uv** | `>=0.11.0`; `uv.lock` committed; CI runs `uv sync --frozen` | lockfile-drift check + frozen install | AUTO-GATE |
| Build backend | **hatchling** | `build-backend = "hatchling.build"` | wheel build in CI | AUTO-GATE |
| CVE scan (deps) | **pip-audit** | block on fixed HIGH+CRITICAL — **`\|\| true` is forbidden** | `pip-audit` exit code (see §9) | AUTO-GATE |
| Dev-side fast feedback | **pre-commit** | ruff hooks pinned to `v0.15.x`; mypy/pyright as pre-push | local + `pre-commit.ci` | REVIEW-GATE |

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

**Drift remediation (mandatory, tracked per repo):** raise ruff to `>=0.15.x` (fixes `fare-assistant`, `habitable`, `ledger`, `swelter`, `queer-the-stacks`, `women-artist-discovery` at `>=0.6`; `tods-validate` `>=0.5`; `nearmiss` `>=0.4`); pin mypy `>=1.18` (resolves the 1.10/1.11 split); set `--cov-fail-under` everywhere it is unset (`fare-assistant`, `gtfs-scorecard`, `nearmiss`, `swelter`, `tods-validate`); migrate `jobradar` to a root `pyproject.toml` + add mypy; lift `gtfs-scorecard` config and `uv.lock` to repo root; add `pyright`/`pyrefly` benchmark before any mypy→pyright swap.

---

## 3. TypeScript / frontend toolchain

Applies to `personal-site`, `davis-bike-hazard-map`, `trans-docs-navigator`, and any future TS surface (including Lambda handlers). One `eslint.config.mjs` (flat config; legacy `.eslintrc` is unsupported in ESLint v10). Prettier is a **separate** step, never an ESLint rule.

| Concern | Tool | Canonical target | Measured by | Gate |
|---------|------|------------------|-------------|------|
| Type strictness | `tsc --noEmit` | `strict: true` **plus** `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noUnusedLocals`, `noUnusedParameters`, `noImplicitOverride`, `noFallthroughCasesInSwitch` | `tsc --noEmit` exit code | AUTO-GATE |
| Lint | ESLint v10 flat + typescript-eslint v8 | `strictTypeChecked` + `stylisticTypeChecked` + `react-hooks/recommended` (incl. `exhaustive-deps`) + `jsx-a11y/recommended`; `--max-warnings 0`; `eslint-config-prettier` last | `eslint .` exit code | AUTO-GATE |
| Format | Prettier 3 | `singleQuote:true, trailingComma:"all", printWidth:100, semi:true`; run via `prettier --check .` | separate CI step | AUTO-GATE |
| Unit/component tests + coverage | Vitest v4 (`provider:"v8"`) | lines/branches/functions/statements **≥80%**, `coverage.perFile: true` | threshold exit code | AUTO-GATE |
| E2E | Playwright | Chromium min; `retries:2`, `forbidOnly:!!process.env.CI` | suite exit code | AUTO-GATE |
| Bundle budget | size-limit v12 | critical-path JS **≤170 KB gzip** | `andresz1/size-limit-action` PR gate | AUTO-GATE |
| Chunk warning | Vite 8 | `build.chunkSizeWarningLimit: 500`; `target:"baseline-widely-available"` | build log + reviewer | REVIEW-GATE |
| Bundle composition | rollup-plugin-visualizer | committed HTML artifact for any PR adding a dep >50 KB gzip; no duplicate React/date libs | reviewer | REVIEW-GATE |
| SCA | `npm audit --audit-level=high` / OSV-Scanner | block on fixed HIGH+CRITICAL | exit code | AUTO-GATE |

`noEmit: true`, `isolatedModules: true`, `moduleResolution: "bundler"`, `module: "ESNext"` are required (emit belongs to Vite/esbuild, not `tsc`).

**Biome v2** is an acceptable single-binary replacement for ESLint+Prettier **only on a greenfield TS repo that does not need `react-hooks/exhaustive-deps` or type-aware rules** (`no-floating-promises`). All three current frontends use hooks → they keep the ESLint stack. A repo choosing Biome records the rule-gap audit as an ADR (REVIEW-GATE). **React Compiler** (`babel-plugin-react-compiler`) is opt-in per-file (`compilationMode:"annotation"`) and REVIEW-GATE: validate output in Vitest before enabling, then strip the now-redundant manual `useMemo`/`useCallback`.

---

## 4. Project layout

| Rule | Requirement | Gate |
|------|-------------|------|
| Python package location | `src/<package>/` (PyPA src layout); `[tool.hatch.build.targets.wheel] packages = ["src/<package>"]`; never import from repo root without editable install | REVIEW-GATE (caught by `make verify` running against the installed wheel) |
| Tests location | `tests/` at repo root, never inside `src/` | AUTO-GATE (ruff/pytest paths) |
| Config location | exactly one root `pyproject.toml` (TS: one `package.json` + `eslint.config.mjs` + `vitest.config.ts`); no nested or duplicate config | AUTO-GATE (a repo-root config-presence check) |
| Monorepo-style nesting | forbidden unless declared in an ADR | REVIEW-GATE |

Named remediation: `gtfs-scorecard` must surface a root `pyproject.toml`/`Makefile`/`uv.lock` (its real project lives under `pipeline/`); `jobradar` must adopt `src/` + root config.

---

## 5. Dependency management

| Rule | Requirement | Gate |
|------|-------------|------|
| Lockfile | `uv.lock` committed; CI installs with `uv sync --frozen` (fails if lock is stale) | AUTO-GATE |
| Dev deps | declared in PEP 735 `[dependency-groups]` (not `[project.optional-dependencies]`) so linters/type-checkers never ship as extras | AUTO-GATE (lint of `pyproject.toml`) |
| Hash pinning (deployed services) | `uv pip compile --generate-hashes` for the deployed requirement set | REVIEW-GATE |
| Update bot | Dependabot **or** Renovate enabled (`minimumReleaseAge: 72h`); required for OpenSSF Scorecard `Dependency-Update-Tool` | REVIEW-GATE (artifact: committed config) |
| Adding a dependency | new runtime dep requires a one-line rationale in the PR; new dep >50 KB gzip (TS) requires a visualizer artifact (§3) | REVIEW-GATE |

GitHub Actions SHA-pinning, SBOM, Sigstore signing, and SLSA provenance are **not** specified here — see `SECURITY-AND-SUPPLY-CHAIN-STANDARD`. This document only requires that application/library dependencies are locked and scanned.

---

## 6. Docstrings, comments, and dead-code hygiene

| Rule | Requirement | Gate |
|------|-------------|------|
| Module docstring | every Python module and every public TS module has a one-line purpose statement | AUTO-GATE (ruff `D`-subset where enabled; else REVIEW-GATE via checklist) |
| Public API docstrings | every public function/class/CLI flag documents intent, args, raises/returns | REVIEW-GATE (paired with `DOCUMENTATION-STANDARD`) |
| Comments explain *why* | comments justify non-obvious decisions, not restate code | REVIEW-GATE |
| **No `TODO`/`FIXME`/`HACK` without a linked issue** | every such marker carries an issue URL, e.g. `# TODO(#142): ...`; bare markers fail CI | AUTO-GATE |
| No `type: ignore` / `eslint-disable` / `# noqa` without a linked issue | each suppression carries a code *and* an issue reference; blanket ignores fail CI | AUTO-GATE |
| Commented-out code | forbidden on `main`; delete it (git is the archive) | REVIEW-GATE |

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
| PR required | no direct pushes to `main`; ≥1 approving review from someone other than the last pusher (≥2 for auth, PII, payment, safety-critical, prompt/retrieval paths) | AUTO-GATE (branch ruleset — see `CI-CD-STANDARD`) |
| Stale reviews | dismissed on new commits | AUTO-GATE |
| CODEOWNERS | committed; routes `.github/workflows/`, security-critical files, and `DEFINITION_OF_DONE.md` to a required reviewer | AUTO-GATE (existence) / REVIEW-GATE (routing correctness) |
| Status checks | all CI jobs green, branch up to date (strict) | AUTO-GATE |
| Linear history + signed commits | squash/rebase only; GPG/SSH signature verification on `main` | AUTO-GATE |
| PR template DoD | every PR carries the `QUALITY-AND-METRICS-STANDARD` DoD checklist; merge blocked until checked | REVIEW-GATE |
| Self-merge | prohibited on `main` (no admin bypass) | AUTO-GATE |

Solo-maintainer note: most repos here have one human author. "≥1 review" is still enforced via branch protection; the maintainer satisfies it through an explicit self-review pass recorded in the PR plus all AUTO-GATEs green. The point of the gate is that *the checks ran and were acknowledged*, not headcount.

---

## 8. Architecture Decision Records (ADRs)

| Rule | Requirement | Gate |
|------|-------------|------|
| Location | `docs/adr/NNNN-title.md`, MADR format (Context / Decision / Consequences / Status) | REVIEW-GATE |
| When required | any choice that is expensive to reverse: language/runtime floor change, type-checker swap (mypy→pyright/pyrefly), Biome adoption, datastore, public API shape, security/PII boundary, **declaring a standard N/A** (§11) | REVIEW-GATE (checklist item; PR touching these without an ADR is rejected) |
| Immutability | ADRs are append-only; supersede, never edit silently (set `Status: superseded by NNNN`) | REVIEW-GATE |

---

## 9. The merge-gate list (Python)

A merge to `main` requires **every** AUTO-GATE green and **every** REVIEW-GATE attested. `make verify` reproduces all AUTO-GATEs locally and is byte-for-byte the CI body.

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

Line/branch coverage proves code *ran*, not that assertions *catch regressions*. For repos whose correctness is load-bearing (the AI/eval harnesses, `ledger`'s no-outing guarantee, `fare-assistant` grounding guards, civic RAG citation guards), a mutation-testing pass quantifies test strength.

| Metric | Target | Tool | Gate |
|--------|--------|------|------|
| Mutation score (core safety modules) | ≥70% killed | `mutmut` / `cosmic-ray` (Py), Stryker (TS) | REVIEW-GATE (nightly, not per-PR; surviving mutants triaged) |

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

**`self-osint-monitor` is the explicit exception:** it is spec-only (no CI, no `pyproject.toml`, no tests). Its M0/M1 deliverable is to *author* this standard as scaffold — root `pyproject.toml` with the §2 block, `make verify` == CI, `src/` layout, `uv.lock` — **before** any feature code, sequenced after its consent gate. The near-duplicate pair `queer-the-stacks` / `queer-specfic-reader` (same `queer_the_stacks` package) must be reconciled (merge or formally fork-with-ADR) so standards work is not double-counted and the two do not drift.

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
