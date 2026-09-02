# Definition of Done

Instantiates `docs/standards/QUALITY-AND-METRICS-STANDARD.md`'s per-repo DoD
for `tods-validate`'s actual shape: a Python CLI/library + composite GitHub
Action + static playground, no service, no AI/LLM component, English-only.
Reviewed at each release; update this file in the same PR that changes what
"done" means (e.g. adding a new gate).

## AUTO-GATE (CI on every PR; `make verify` reproduces 1–5 locally)

1. **Format + lint** — `ruff check` + `ruff format --check`, zero errors.
2. **Type-check** — `mypy --strict` on `src/`, zero errors.
3. **Tests + coverage** — full suite green; line **and** branch coverage
   ≥ 90% (`--cov-fail-under=90`, `[tool.coverage.run] branch = true`);
   cyclomatic complexity ≤ 10 (`ruff` `C901`, `max-complexity = 10`).
4. **Security** — Semgrep (`ci --config auto`), CodeQL (`python` + `actions`),
   gitleaks (pre-commit + CI, no `continue-on-error`), `pip-audit --strict`
   (no mute pattern), Trivy image scan (`CRITICAL,HIGH`, blocking, in
   `docker.yml`); every `uses:` SHA-pinned; CycloneDX SBOM + cosign + SLSA
   provenance on every release artifact.
5. **Workflow SAST** — zizmor, blocking on High/Critical, on any PR touching
   `.github/workflows/**` or `action.yml`.
6. **Accessibility** — scoped to the `--format html` report and `web/`
   playground. **Not yet a blocking CI gate** (tracked:
   `docs/CONFORMANCE-GAPS.md#accessibility`); today this is enforced only by
   unit tests asserting lang/viewport/landmark/contrast properties
   (`tests/test_report_extras.py`).
7. **i18n** — N/A, declared (`docs/I18N.md`), CI-enforced
   (`scripts/check_i18n.py`).
8. **AI-eval** — N/A, no LLM/AI component (`docs/RESPONSIBLE-TECH-AUDITS.md`).
9. **Observability** — N/A beyond the Tier C declaration (README
   `## Observability`); no structured-log gate applicable (no `--log-format
   json` flag shipped yet).
10. **Performance** — `scripts/benchmark.py` exists; **not yet a CI budget
    gate** (tracked: `docs/CONFORMANCE-GAPS.md#quality-and-metrics`).
11. **Build** — `python -m build` (sdist + wheel) and the Docker image both
    build in the release workflows; the composite Action self-tests against
    the fixture feed on every PR (`action-self-test` in `ci.yml`).

`make verify` runs stages 1–5 locally, byte-for-byte identical to CI
(`ci.yml`, `.github/workflows/verify.yml`).

## REVIEW-GATE (human sign-off, committed as PR attestation + artifact)

- PR description states acceptance criteria and links an issue where one
  exists (see `.github/PULL_REQUEST_TEMPLATE.md`).
- A new rule ships a passing and failing fixture, and
  `docs/rules.md`/`docs/spec-questions.md` are updated if the rule
  interprets an ambiguous part of the spec (`docs/authoring-rules.md`).
- A change to a workflow, `action.yml`, or `Dockerfile` gets a threat-model
  read-through against `SECURITY.md` before merge (these paths are also
  routed through `.github/CODEOWNERS`).
- A new custom interactive surface in `web/` gets a keyboard + screen-reader
  pass before merge (informal today; see the accessibility gap above).
- `CHANGELOG.md` is updated when behavior changes (`CONTRIBUTING.md`).

## RELEASE-GATE

- `make verify` is green at the tagged commit (`.github/workflows/verify.yml`,
  called from `pypi-publish.yml`, `docker.yml`, `release-corpus.yml` before
  any publish step runs).
- Tag, `pyproject.toml` version, and `CITATION.cff` version agree, and
  `CHANGELOG.md` has a section for the released version (checked
  mechanically as part of `verify.yml`).
- The release tag is annotated and signed (`git tag -s vX.Y.Z -m "release:
  vX.Y.Z"`) — enforced by `verify.yml` going forward; see
  `docs/CONFORMANCE-GAPS.md#release-and-versioning` for the pre-existing
  tags this does not retroactively cover.
- SBOM + build provenance (PyPI) and SBOM + provenance + cosign signature
  (GHCR) are (re)generated as part of the publish workflow, never hand-built.
- `verify-published` (in `pypi-publish.yml` and `docker.yml`) re-downloads
  what was actually published and checks its attestation/signature before
  the release is considered done.

## Branch protection

Enabled as a live GitHub ruleset on 2026-09-01: `protect-main`, id 18752857.
It requires a pull request, sixteen status checks, and linear history; it
forbids force-push and deletion; and its `bypass_actors` list is empty, so it
binds the maintainer too. `docs/rulesets/main.json` is the export of what is
enforced, not a statement of intent, and `docs/rulesets/README.md` says how to
re-export it after any change.

Two things this DoD once assumed are deliberately not in it. Required
approvals are set to zero rather than one, and code-owner review is off,
because `CODEOWNERS` names one person and GitHub does not accept a
self-approval: requiring one on a solo repository blocks every merge rather
than reviewing anything. The PR requirement and thread resolution are the
parts that still bite with one maintainer, and those are on.
