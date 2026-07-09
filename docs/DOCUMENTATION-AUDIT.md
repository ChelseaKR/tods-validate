# Documentation Audit

Last reviewed: 2026-07-08. Base branch: `main`.

This audit records the documentation sweep and remediation loop for this repository. It checks the docs as a system: entry points, root-level process and legal files, project scope, setup and validation notes, safety and privacy posture, architecture and planning docs, local links, and the places where code, tests, workflows, and docs meet.

## Audit Results

| Area | Result | Evidence |
| --- | --- | --- |
| Entry docs | pass | `README.md` present |
| Security/process docs | pass | CONTRIBUTING.md, SECURITY.md, CHANGELOG.md |
| Architecture/planning docs | pass | 2 architecture/interface docs; 5 planning/research docs |
| Safety/privacy/audit docs | pass | 2 safety/privacy/accessibility/audit docs |
| Validation surface | pass | 31 test files; 11 workflow files |
| Local doc links | pass | 141 authored-doc links checked; 0 unresolved |

## Root-Level Documentation Audit

This section covers hand-authored documentation at the repository root and root-adjacent GitHub templates. It is separate from the `docs/` inventory so README, process, legal, release, and project-specific root files do not get hidden inside the larger docs tree.

| Surface | Result | Evidence |
| --- | --- | --- |
| Root README | pass | Present: `README.md` |
| Root process docs | pass | Present: `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` |
| Root legal, citation, and conduct docs | pass | Present: `LICENSE`, `NOTICE`, `CITATION.cff`, `CODE_OF_CONDUCT.md` |
| Other root project docs | info | `DEFINITION_OF_DONE.md` |
| Root-adjacent GitHub templates | pass | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS` |
| Root/template doc links | pass | 39 root-level/template links checked; 0 unresolved |

Root-level files checked:

- `CHANGELOG.md`
- `CITATION.cff`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `DEFINITION_OF_DONE.md`
- `LICENSE`
- `NOTICE`
- `README.md`
- `SECURITY.md`

Root-adjacent template files checked:

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/CODEOWNERS`

## Remediation In This PR

- Added missing root-level remediation docs found by the audit loop, including legal, conduct, contribution, or security files where absent.
- Added `docs/PROJECT-SCOPE.md` as the plain-language project and boundary map.
- Added this audit record so future doc changes have a dated baseline.
- Added or refreshed the docs index so scope, audit, and primary docs are easy to find.
- Fixed or added root/doc remediation files: `README.md`, `docs/authoring-rules.md`, `docs/ideation/02-large-scale-fixes.md`, `docs/mutation-testing.md`, `docs/standards/README.md`, `web/README.md`.

## Repo Surfaces Checked

Package and workspace metadata:

- Node workspace `editor/vscode/package.json` named `tods-validate` (scripts: compile, package, vscode:prepublish, watch).
- Python package `tods-validate` (>=3.11).

Source and operations surfaces seen at the repo root:

- `Dockerfile`
- `Makefile`
- `pyproject.toml`
- `scripts/`
- `src/`
- `tests/`
- `uv.lock`
- `web/`

Workflow files checked:

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

## Documentation Inventory

| Category | Count | Representative files |
| --- | ---: | --- |
| architecture and interfaces | 2 | `docs/api.md`, `docs/read-api.md` |
| entry points and repo process | 10 | `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`, `CHANGELOG.md`, `CITATION.cff`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `LICENSE`, `NOTICE`, plus 2 more |
| examples and guides | 101 | `examples/sample-feed/agency.txt`, `examples/sample-feed/calendar.txt`, `examples/sample-feed/calendar_dates_supplement.txt`, `examples/sample-feed/calendar_supplement.txt`, `examples/sample-feed/employee_run_dates.txt`, `examples/sample-feed/routes.txt`, `examples/sample-feed/routes_supplement.txt`, `examples/sample-feed/run_events.txt`, plus 93 more |
| operations and release | 15 | `examples/sample-feed/stops.txt`, `examples/sample-feed/stops_supplement.txt`, `tests/fixtures/invalid/TODS-E202/stops_supplement.txt`, `tests/fixtures/invalid/TODS-E304/stops_supplement.txt`, `tests/fixtures/invalid/TODS-E309/stops.txt`, `tests/fixtures/invalid/TODS-I108/stops_supplement.txt`, `tests/fixtures/invalid/TODS-I501/stops.txt`, `tests/fixtures/invalid/TODS-W305/stops_supplement.txt`, plus 7 more |
| other docs | 14 | `DEFINITION_OF_DONE.md`, `docs/BENCHMARKS.md`, `docs/CONFORMANCE-GAPS.md`, `docs/I18N.md`, `docs/PROJECT-SCOPE.md`, `docs/README.md`, `docs/authoring-rules.md`, `docs/conformance.md`, plus 6 more |
| planning and research | 5 | `docs/RESEARCH-ROADMAP.md`, `docs/USER-RESEARCH.md`, `docs/ideation/02-large-scale-fixes.md`, `docs/ideation/03-expansions.md`, `docs/roadmap.md` |
| safety, privacy, accessibility, and audits | 2 | `docs/DOCUMENTATION-AUDIT.md`, `docs/RESPONSIBLE-TECH-AUDITS.md` |
| grouped generated/source content | 12 | `docs/standards/` counted as a content group, not listed file by file |
| grouped generated/source content | 1 | `tests/fixtures/` counted as a content group, not listed file by file |

Full hand-authored doc inventory checked by this pass:

- `.github/CODEOWNERS`
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
- `docs/DOCUMENTATION-AUDIT.md`
- `docs/I18N.md`
- `docs/PROJECT-SCOPE.md`
- `docs/README.md`
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
- `tests/fixtures/invalid/TODS-I501/stops.txt`
- `tests/fixtures/invalid/TODS-I501/trips.txt`
- `tests/fixtures/invalid/TODS-I502/calendar.txt`
- `tests/fixtures/invalid/TODS-I502/trips.txt`
- `tests/fixtures/invalid/TODS-I502/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-I502/vehicles.txt`
- `tests/fixtures/invalid/TODS-I601/run_events.txt`
- `tests/fixtures/invalid/TODS-W101/agency.txt`
- `tests/fixtures/invalid/TODS-W107/vehicles.txt`
- `tests/fixtures/invalid/TODS-W206/vehicles.txt`
- `tests/fixtures/invalid/TODS-W302/employee_run_dates.txt`
- `tests/fixtures/invalid/TODS-W305/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-W306/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-W313/stops.txt`
- `tests/fixtures/invalid/TODS-W313/stops_supplement.txt`
- `tests/fixtures/invalid/TODS-W315/calendar.txt`
- `tests/fixtures/invalid/TODS-W315/routes.txt`
- `tests/fixtures/invalid/TODS-W315/run_events.txt`
- `tests/fixtures/invalid/TODS-W315/stop_times.txt`
- `tests/fixtures/invalid/TODS-W315/stops.txt`
- `tests/fixtures/invalid/TODS-W315/trips.txt`
- `tests/fixtures/invalid/TODS-W316/calendar.txt`
- `tests/fixtures/invalid/TODS-W316/routes.txt`
- `tests/fixtures/invalid/TODS-W316/run_events.txt`
- `tests/fixtures/invalid/TODS-W316/stop_times.txt`
- `tests/fixtures/invalid/TODS-W316/stops.txt`
- `tests/fixtures/invalid/TODS-W316/trips.txt`
- `tests/fixtures/invalid/TODS-W403/run_events.txt`
- `tests/fixtures/invalid/TODS-W404/employee_run_dates.txt`
- `tests/fixtures/invalid/TODS-W404/run_events.txt`
- `tests/fixtures/invalid/TODS-W406/calendar.txt`
- `tests/fixtures/invalid/TODS-W406/employee_run_dates.txt`
- `tests/fixtures/invalid/TODS-W406/run_events.txt`
- `tests/fixtures/invalid/TODS-W407/calendar.txt`
- `tests/fixtures/invalid/TODS-W407/trips.txt`
- `tests/fixtures/invalid/TODS-W407/vehicle_assignments.txt`
- `tests/fixtures/invalid/TODS-W407/vehicles.txt`
- `tests/fixtures/invalid/TODS-W408/employee_run_dates.txt`
- `tests/fixtures/invalid/TODS-W408/run_events.txt`
- `tests/fixtures/invalid/TODS-W409/run_events.txt`
- `tests/fixtures/valid/gtfs/agency.txt`
- `tests/fixtures/valid/gtfs/calendar.txt`
- `tests/fixtures/valid/gtfs/routes.txt`
- `tests/fixtures/valid/gtfs/stop_times.txt`
- `tests/fixtures/valid/gtfs/stops.txt`
- `tests/fixtures/valid/gtfs/trips.txt`
- `tests/fixtures/valid/tods/calendar_dates_supplement.txt`
- `tests/fixtures/valid/tods/calendar_supplement.txt`
- `tests/fixtures/valid/tods/employee_run_dates.txt`
- `tests/fixtures/valid/tods/routes_supplement.txt`
- `tests/fixtures/valid/tods/run_events.txt`
- `tests/fixtures/valid/tods/stop_times_supplement.txt`
- `tests/fixtures/valid/tods/stops_supplement.txt`
- `tests/fixtures/valid/tods/trips_supplement.txt`
- `tests/fixtures/valid/tods/vehicle_assignments.txt`
- `tests/fixtures/valid/tods/vehicles.txt`
- `web/README.md`

Grouped content counts:

- `docs/standards/`: 12 files
- `tests/fixtures/`: 1 files

## Link Check

- Checked 141 local links in authored Markdown and MDX docs.
- Unresolved authored-doc links after remediation: 0.
- Root-level/template unresolved links after remediation: 0.

Audit scope notes:

- Generated sites, deployed app routes, raw third-party HTML captures, and golden fixture websites were inventoried as product or data surfaces but excluded from authored-doc link failure counts.
- Grouped content directories are counted so they stay visible without making the audit readable without hiding them.

## Validation Notes

- The audit was generated from a clean worktree based on `origin/main` for this PR branch.
- Ran a local relative-link check over hand-authored Markdown and MDX docs.
- Ran an explicit root-level documentation presence and link check for README, process, legal, project, and template docs.
- Ran `git diff --check` across the PR worktrees after remediation.
- Product test suites remain the authority for runtime behavior; this PR changes documentation only.
