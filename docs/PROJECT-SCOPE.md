# Project Scope

Last reviewed: 2026-07-08. Base branch: `main`.

This file is a plain-language map of the project as it exists on `main`. It does not replace the README, roadmap, audit docs, or source comments. It points to them so a reviewer can see the whole shape without reading every file first.

## What This Project Is

TODS Validate checks Transit Operational Data Standard packages and companion GTFS feeds. It reports rule findings with row, field, severity, and repair hints so agencies and vendors can fix schedule operations data.

Package metadata checked in this pass:

- Python package `tods-validate` for Python `>=3.11`.
- Node workspace `editor/vscode/package.json` named `tods-validate`.

## Who It Serves

- Transit agencies and vendors producing TODS files.
- Tooling authors who need a Python API, CLI, GitHub Action, or editor extension.
- Maintainers tracking conformance, schemas, rules, and spec questions.

## What It Covers

- A Python CLI and rules engine.
- Report schemas, rule docs, authoring guidance, sample feeds, and conformance notes.
- A GitHub Action and VS Code extension surface.
- Pages, Docker, release, mutation, security, and verification workflows.
- Tests for runner behavior, rule references, reports, and sample packages.

## How It Is Put Together

- src/tods_validate/ contains CLI, report, runner, schema, and rules code.
- docs/ contains rules, API, getting started, conformance, authoring, mutation, and spec-question docs.
- examples/sample-feed/ holds a complete sample TODS plus GTFS package.
- editor/vscode/ contains the editor extension.
- action.yml exposes CI use.

Observed source and operations surfaces:

- `Dockerfile`
- `Makefile`
- `action.yml`
- `editor/`
- `pyproject.toml`
- `scripts/`
- `src/`
- `web/`

GitHub workflow files checked:

- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/docker.yml`
- `.github/workflows/mutation.yml`
- `.github/workflows/pages.yml`
- `.github/workflows/pypi-publish.yml`
- `.github/workflows/release-corpus.yml`
- `.github/workflows/scorecard.yml`
- `.github/workflows/semgrep.yml`
- `.github/workflows/verify.yml`
- `.github/workflows/zizmor.yml`

## Trust Boundaries

- Findings should name the exact file, row, field, and repair direction.
- The companion GTFS check matters because TODS references scheduled transit data.
- Spec questions are documented when the standard leaves room for interpretation.

## Outside This Scope

- It validates packages; it does not certify an agency's operations.
- Warnings may need agency judgment before changes are made.
- Spec changes require rule updates and versioned docs.

## Docs And Evidence Checked

This pass checked 146 hand-authored doc or metadata files, 132 test files, and 11 workflow files on `main`. The count excludes vendored provider licenses, dependency folders, generated cache files, and large generated artifact history.

Large content groups were counted rather than listed file by file:

- `docs/standards/`: 12 files

Primary docs checked:

- `.github/PULL_REQUEST_TEMPLATE.md`
- `CHANGELOG.md`
- `CITATION.cff`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `DEFINITION_OF_DONE.md`
- `LICENSE`
- `NOTICE`
- `README.md`
- `SECURITY.md`
- `docs/BENCHMARKS.md`
- `docs/CONFORMANCE-GAPS.md`
- `docs/I18N.md`
- `docs/RESEARCH-ROADMAP.md`
- `docs/RESPONSIBLE-TECH-AUDITS.md`
- `docs/USER-RESEARCH.md`
- `docs/api.md`
- `docs/authoring-rules.md`
- `docs/conformance.md`
- `docs/getting-started.md`
- `docs/ideation/02-large-scale-fixes.md`
- `docs/ideation/03-expansions.md`
- `docs/mutation-testing.md`
- `docs/read-api.md`
- `docs/roadmap.md`
- `docs/rules.md`
- `docs/spec-questions.md`
- `editor/vscode/README.md`
- `examples/sample-feed/agency.txt`
- `examples/sample-feed/calendar.txt`
- `examples/sample-feed/calendar_dates_supplement.txt`
- `examples/sample-feed/calendar_supplement.txt`
- `examples/sample-feed/employee_run_dates.txt`
- `examples/sample-feed/routes.txt`
- `examples/sample-feed/routes_supplement.txt`
- `examples/sample-feed/run_events.txt`
- `examples/sample-feed/stop_times.txt`
- `examples/sample-feed/stop_times_supplement.txt`
- `examples/sample-feed/stops.txt`
- `examples/sample-feed/stops_supplement.txt`
- `examples/sample-feed/trips.txt`
- `examples/sample-feed/trips_supplement.txt`
- `examples/sample-feed/vehicle_assignments.txt`
- `examples/sample-feed/vehicles.txt`
- `tests/fixtures/invalid/TODS-E103/vehicles.txt`
- `tests/fixtures/invalid/TODS-E104/vehicles.txt`
- `tests/fixtures/invalid/TODS-E105/vehicles.txt`
- `tests/fixtures/invalid/TODS-E106/run_events.txt`
- `tests/fixtures/invalid/TODS-E201/run_events.txt`
- `tests/fixtures/invalid/TODS-E202/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-E203/run_events.txt`
- `tests/fixtures/invalid/TODS-E204/vehicles.txt`
- `tests/fixtures/invalid/TODS-E205/trips.txt`
- `tests/fixtures/invalid/TODS-E205/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-E205/vehicles.txt`
- Plus 91 more files in the same inventory.

Representative test files checked:

- `tests/conftest.py`
- `tests/fixtures/invalid/TODS-E103/vehicles.txt`
- `tests/fixtures/invalid/TODS-E104/vehicles.txt`
- `tests/fixtures/invalid/TODS-E105/vehicles.txt`
- `tests/fixtures/invalid/TODS-E106/run_events.txt`
- `tests/fixtures/invalid/TODS-E201/run_events.txt`
- `tests/fixtures/invalid/TODS-E202/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-E203/run_events.txt`
- `tests/fixtures/invalid/TODS-E204/vehicles.txt`
- `tests/fixtures/invalid/TODS-E205/trips.txt`
- `tests/fixtures/invalid/TODS-E205/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-E205/vehicles.txt`
- `tests/fixtures/invalid/TODS-E301/employee_run_dates.txt`
- `tests/fixtures/invalid/TODS-E301/run_events.txt`
- `tests/fixtures/invalid/TODS-E303/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-E303/vehicles.txt`
- `tests/fixtures/invalid/TODS-E304/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-E307/run_events.txt`
- `tests/fixtures/invalid/TODS-E307/trips.txt`
- `tests/fixtures/invalid/TODS-E308/calendar.txt`
- `tests/fixtures/invalid/TODS-E308/run_events.txt`
- `tests/fixtures/invalid/TODS-E309/run_events.txt`
- `tests/fixtures/invalid/TODS-E309/stops.txt`
- `tests/fixtures/invalid/TODS-E310/run_events.txt`
- `tests/fixtures/invalid/TODS-E310/trips.txt`
- `tests/fixtures/invalid/TODS-E311/trips.txt`
- `tests/fixtures/invalid/TODS-E311/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-E311/vehicles.txt`
- `tests/fixtures/invalid/TODS-E312/calendar.txt`
- `tests/fixtures/invalid/TODS-E312/trips.txt`
- `tests/fixtures/invalid/TODS-E312/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-E312/vehicles.txt`
- `tests/fixtures/invalid/TODS-E314/calendar.txt`
- `tests/fixtures/invalid/TODS-E314/routes.txt`
- `tests/fixtures/invalid/TODS-E314/trips_supplement.txt`
- `tests/fixtures/invalid/TODS-E401/run_events.txt`
- `tests/fixtures/invalid/TODS-E402/run_events.txt`
- `tests/fixtures/invalid/TODS-E405/calendar.txt`
- `tests/fixtures/invalid/TODS-E405/run_events.txt`
- `tests/fixtures/invalid/TODS-E405/trips.txt`
- `tests/fixtures/invalid/TODS-I102/notes.txt`
- `tests/fixtures/invalid/TODS-I102/run_events.txt`
- `tests/fixtures/invalid/TODS-I108/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-I501/calendar.txt`
- `tests/fixtures/invalid/TODS-I501/run_events.txt`
- Plus 87 more test files.

## Validation Notes

For this docs PR, validation means the scope file was generated from the clean `origin/main` worktree, reviewed against repo metadata and docs inventory, and checked with `git diff --check`. Project test suites are still the authority for code behavior, because this PR changes documentation only.
