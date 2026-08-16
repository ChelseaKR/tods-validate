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
`verify` workflow install with `uv sync --frozen --extra dev`. The lock was
verified against the full test suite on 3.11, 3.12, and 3.13 before the CI
matrix switched over. Runtime metadata stays standard PEP 621 in
`pyproject.toml`; `pip install tods-validate` users are unaffected.

**Correction (2026-08-16, v0.9.0).** This decision originally said that
`uv sync --frozen --extra dev` "fails on any lockfile drift". It does not.
`--frozen` means *install exactly what the lock says and do not re-resolve*,
which is the opposite of checking the lock: it exits 0 on a stale lock and
installs the stale pins. So CQ-09's stated gate, "lockfile-drift check +
frozen install", was only ever half implemented here, and the missing half
was the half that fails. Measured on this repo: with `pyproject.toml` at
0.9.0 and `uv.lock` still recording 0.8.0, `uv sync --frozen --extra dev`
exits 0, while `uv lock --check` exits 1 ("The lockfile at `uv.lock` needs to
be updated"). `uv lock --check` now runs as its own step before every
`uv sync` in CI and the release verify workflow, and as the `lockfile` gate
in `make verify`. The frozen install is retained: the two commands answer
different questions, and CQ-09 asks both.

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
