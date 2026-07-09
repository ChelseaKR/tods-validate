# 0005 — uv with a committed lockfile for dependency management

- Status: accepted (backfilled 2026-07-09; adopted 2026-07-05 in the conformance remediation)
- Date: 2026-07-09

## Context

Until 2026-07-05 CI installed with plain `pip install ".[dev]"`: no lockfile,
no drift detection, and the 2026-07-05 audit flagged the gap (CQ-09, SEC-11,
SEC-13). The fix needed reproducible resolution across the 3.11/3.12/3.13
matrix without making contributor setup harder.

## Decision

Adopt uv. `uv.lock` is committed; CI's lint/test/audit jobs and the release
`verify` workflow install with `uv sync --frozen --extra dev`, which fails on
any lockfile drift. The lock was verified against the full test suite on
3.11, 3.12, and 3.13 before the CI matrix switched over. Runtime metadata
stays standard PEP 621 in `pyproject.toml`; `pip install tods-validate`
users are unaffected.

Deliberate scope cut, still open: the `docs-drift`/`i18n`/`action-self-test`/
`merge-handoff` CI jobs remain on plain `pip install` (they do not consume
the dev extra), and dev dependencies still live in
`[project.optional-dependencies].dev` rather than PEP 735
`[dependency-groups]` (CQ-27). Both are tracked in
`docs/CONFORMANCE-GAPS.md`.

## Consequences

- Dependency changes are visible as lockfile diffs and gated by
  `pip-audit --strict`.
- Contributors need uv for the locked dev environment (CONTRIBUTING
  documents it); plain pip remains enough to install and use the tool.
- Renovate/Dependabot updates arrive as reviewable lockfile PRs.
