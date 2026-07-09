# Authoring a rule

This guide is for contributors adding a check to `tods-validate`. It covers
where a rule lives, how to choose its ID and severity, how to write a message a
scheduler can act on, and the fixture-and-conformance contract CI enforces. The
catalog of existing rules is in [rules.md](rules.md); the conformance corpus is
described in [conformance.md](conformance.md).

If you are looking for a first contribution, the openings are at the end:
[good first rules](#good-first-rules).

## Rules are data plus a small function

A rule is not a plugin. It is a registry entry — an ID, a severity, a title, a
description, a spec citation — plus one check function that yields `Finding`s.
The registry and the `@rule` decorator live in
[`src/tods_validate/rules/__init__.py`](../src/tods_validate/rules/__init__.py).
Add your check to the module that matches its band (see below):

- `structure.py` — package and file structure (TODS-x1xx)
- `fields.py` — field values within one file (TODS-x2xx)
- `references.py` — references between files, including the companion GTFS (TODS-x3xx)
- `semantics.py` — checks across rows (TODS-x4xx)
- `coverage.py` — opt-in coverage/advisory checks (TODS-x5xx/x6xx)

A check receives a `ValidationContext` (the loaded `package`, and `gtfs` when a
companion feed is available) and yields `Finding`s. Here is the shape, modeled
on the real `TODS-E201`:

```python
from collections.abc import Iterator

from ..findings import Finding, Severity
from ..schema import SPEC_URL
from . import ValidationContext, rule


@rule(
    id="TODS-E2xx",
    severity=Severity.ERROR,
    title="Short noun phrase naming the problem",
    description=(
        "One or two sentences for the rule catalog, written for a feed producer. "
        "Say what the rule checks and why it matters."
    ),
    spec_section=SPEC_URL,  # link the exact spec section where you can
)
def my_check(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        for row in feed.rows:
            if _is_bad(row):
                yield Finding(
                    rule_id="TODS-E2xx",
                    severity=Severity.ERROR,
                    file=table.filename,
                    row=row.line,          # 1-based, header is line 1
                    field="the_field",     # name the field when you can
                    message="...",         # see "Message style" below
                )
```

Rules that resolve IDs into the companion GTFS feed set `needs_gtfs=True`; they
are skipped automatically when no companion feed is loaded, so you never need to
guard against `context.gtfs is None` yourself.

## Choosing a severity

Severity is the contract a CI gate keys on, so pick it deliberately. The
definitions, repeated from [rules.md](rules.md):

- **ERROR** — the feed violates the spec; a consumer may misread or drop data.
  A required field is missing; a referenced trip does not exist. ERRORs fail the
  default run.
- **WARNING** — probably a mistake, but the spec does not forbid it. Real
  schedules have legitimate edge cases, so do not make something an ERROR unless
  the spec actually requires it. WARNINGs do not fail the run unless a consumer
  opts in with `--fail-on warning`.
- **INFO** — worth knowing, no action required.

When the spec is ambiguous, implement the permissive reading and record the
choice: set the rule's `interpretation=` (it is surfaced in `rules --format
json` so consumers can audit it) and, if the ambiguity is real, add an entry to
[spec-questions.md](spec-questions.md). A judgement call that would be noise in a
default gate belongs in an opt-in category (`coverage` or `advisory`) with
`default_enabled=False`, not as a core WARNING.

## Allocating an ID

IDs are permanent: once a rule ships, its ID is never reused or renumbered, so
a downstream pipeline can filter or suppress it forever. Allocate the next free
number in the right band:

- The letter encodes severity: `E` error, `W` warning, `I` info.
- The first digit is the band: `1` structure, `2` field values, `3` references,
  `4` semantics, `5` coverage, `6` advisory.
- The remaining digits are sequential within the band.

So a new field-value error is the next free `TODS-E2xx`; a new advisory warning
is the next free `TODS-W6xx`. Skim [rules.md](rules.md) for the highest number
already used in your band and take the next one.

## Message style

The error message is the product. Write it for a transit scheduler, not a
programmer. A good finding says three things: what is wrong, where, and what
good looks like — and cites the spec when the answer is "because the spec says
so." Name the file, row, and field via the `Finding` fields (the renderers turn
those into the location prefix); put the rest in `message`.

- Bad: `foreign key violation in run_events`.
- Good: `run_events.txt row 14: trip_id 'WKDY-103' does not exist in the
  companion GTFS trips.txt (after applying trips_supplement.txt). Run events
  that represent work on a trip must reference a scheduled trip.`

If a fix is mechanical, set `suggestion=`; it renders as a `Fix:` line and, when
the value is one the validator would accept, can feed `tods-validate fix`. Match
the repo prose style: plain and concrete, no "simply" or
"just", at most one em dash.

## The fixture and conformance contract

Every rule needs a fixture, and CI enforces a one-to-one mapping between rules
and fixtures (`tests/test_conformance.py`):

1. Add a minimal feed under `tests/fixtures/invalid/<RULE_ID>/` — just enough
   rows to trip exactly your rule. If the rule needs a companion GTFS, put the
   GTFS files in the same directory; the runner picks them up.
2. The fixture must produce a finding with its own rule ID when validated with
   all opt-in categories enabled. It is fine if it also trips other rules; the
   contract only requires your rule to fire.
3. The reference feed in `tests/fixtures/valid/` must still validate with **zero**
   findings, even with opt-in rules on. If your new check fires on the valid
   feed, either the check or the reference feed is wrong — fix it before
   continuing.

Add a focused unit test in the matching `tests/test_<band>.py` too (the
conformance test proves the fixture trips the rule; a unit test pins the
message, location, and any edge cases). The `tests/conftest.py` helpers
`run_invalid_fixture` and `rule_ids` make this short.

The fixtures double as the published [conformance corpus](conformance.md): the
release archive maps each fixture to its expected rule IDs in
`expectations.json`, so an exporter or another validator can run them and diff.
Adding a fixture extends that shared suite for free.

## Before you open the PR

Run the same gates CI does:

```sh
ruff check src tests scripts
ruff format --check src tests scripts
mypy
pytest
python scripts/generate_rules_doc.py        # regenerate docs/rules.md
```

`docs/rules.md` is generated from the registry, so regenerate and commit it
after adding a rule — CI fails (`generate_rules_doc.py --check`) if it drifts.
Add a line to [CHANGELOG.md](../CHANGELOG.md) under "Unreleased" describing the
new check. Conventional-commit the change as its own PR-sized commit.

## Good first rules

Small, well-scoped checks that fit the existing bands and need no new
infrastructure:

- A field-value check (`TODS-x2xx`) for a column whose format the spec pins down
  but the validator does not yet enforce — mirror `TODS-E203`'s time-format
  check for another typed field.
- A structure warning (`TODS-x1xx`) for a recognized-but-unexpected file in the
  package, pointing the producer at the spec's file list.
- An advisory (`TODS-x6xx`, opt-in) that flags a pattern which is legal but
  usually a mistake, following the `coverage.py` rules as a template.

Pick one, open an issue describing the spec basis, and follow the contract
above. A rule lands in a day once the fixture and message are right.
