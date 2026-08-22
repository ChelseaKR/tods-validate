# 0006 — Python floor raised to 3.12; supersedes 0001

- Status: accepted (2026-08-21)
- Date: 2026-08-21
- Supersedes: 0001 (`docs/adr/0001-python-311-floor.md`)

## Context

0001 kept `requires-python = ">=3.11"` as a declared, justified deviation
from `CODE-QUALITY-STANDARD.md`'s CQ-01 (which specifies `>=3.12`, 3.11
allowed only "EOL-track... with a justified ADR"). 0001 named two triggers
for revisiting that floor: a runtime dependency forcing it, or 3.11 leaving
upstream support.

Neither trigger has fired yet — CPython 3.11 security support runs to
October 2027, and `uv.lock` on `main` still resolved for 3.11 as of #72's
first review pass. What changed is CQ-01's own rationale: Python 3.10
reaches EOL October 2026, and CQ-01 already treats `>=3.12` (not `>=3.11`)
as the compliant floor, since 3.12 buys structural pattern matching and
`tomllib` everywhere and removes the conditional-import branches an older
floor keeps alive. #72 raised the floor to close that gap directly rather
than continue carrying it as a declared deviation.

A 2026-07-31 review of #72 (see the PR's review comments) blocked it as
written: mechanically clean, but it reversed 0001 without a superseding
ADR, without updating `README.md`/`CONTRIBUTING.md` (both still said
"Requires Python 3.11 or newer"), and without a CHANGELOG entry, and it
sequenced ahead of the then-held v0.9.0 release scope. The v0.9.0 hold has
since resolved (v0.9.0 shipped 2026-08-16); this ADR and the accompanying
doc/CHANGELOG updates close the three mechanical gaps the review named.

## Decision

- `requires-python = ">=3.12"` (landed in #72, merged 2026-08-21/22).
  `.python-version`, ruff `target-version`, mypy `python_version`,
  classifiers, and the CI test matrix (`3.12`, `3.13`) all agree with the
  new floor; `3.11` was dropped from the matrix in the same PR.
- This is a direct compliance with CQ-01's stated floor, not a new declared
  deviation — 0001's "declared deviation" framing no longer applies, and
  0001 is superseded rather than amended, so the record of why the
  deviation existed for over a month stays intact.
- `README.md` and `CONTRIBUTING.md` are updated to state "Requires Python
  3.12 or newer" (they were left saying 3.11 when #72 merged; fixed here).
  `CHANGELOG.md`'s Unreleased section gets a `Changed:` entry, since this is
  a user-facing floor raise the same way 0001 said it should be if it ever
  happened.

## Consequences

- Contributors and CI on Python 3.11 no longer install; 3.11 users on a
  pinned `tods-validate` release are unaffected (the floor only binds new
  installs/upgrades and local dev).
- `docs/CONFORMANCE-GAPS.md`'s CQ-01 entry is updated: it previously
  described CQ-01 as closed via 0001's declared deviation plus a
  `.python-version` pinned ahead of the floor; it is now closed by the
  floor itself matching the standard, with no deviation to declare.
- If the floor needs to move again, follow 0001's own precedent: a new ADR,
  not a silent `pyproject.toml` edit.
