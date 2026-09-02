# 0005 — uv with a committed lockfile for dependency management

- Status: accepted (backfilled 2026-07-09; adopted 2026-07-05 in the conformance remediation)
- Amended 2026-08-27: development dependencies moved out of the `dev` extra
  into a PEP 735 `[dependency-groups]` table (CQ-27, #145), so the install
  command quoted below is now `uv sync --frozen --group dev`. The decision
  recorded here, uv with a committed lockfile, is unchanged; only the table
  the dev dependencies are declared in has moved.
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

Deliberate scope cut, still open: the `docs-drift`/`contract`/`i18n`/
`action-self-test`/`merge-handoff` CI jobs remain on plain `pip install`
(they do not consume the dev dependencies). Tracked in
`docs/CONFORMANCE-GAPS.md`.

**Correction (2026-09-02, CQ-27).** Until this correction the paragraph
above also named CQ-27, dev dependencies declared in
`[project.optional-dependencies]` instead of PEP 735 `[dependency-groups]`,
as a scope cut that was still open. It had not been open since 2026-08-27.
The dev dependencies moved in #145, `docs/CONFORMANCE-GAPS.md` records the
close, and `tests/test_packaging.py` is the gate that fails if development
tooling reappears as a published extra. The amendment note at the top of
this file recorded the move on the day it happened, so this document spent a
week asserting an open gap and its own close at the same time.
`tests/test_packaging.py` now also fails if any page under `docs/` names the
dev extra that no longer exists.

## Consequences

- Dependency changes are visible as lockfile diffs and gated by
  `pip-audit --strict`.
- Contributors need uv for the locked dev environment (CONTRIBUTING
  documents it); plain pip remains enough to install and use the tool.
- Renovate/Dependabot updates arrive as reviewable lockfile PRs.
