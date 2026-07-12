# Spec watch (advisory)

`src/tods_validate/schema.py` is transcribed by hand from the TODS
specification (`MobilityData/transit-operational-data-standard`,
`docs/en/spec/index.md`). Its own docstring says the rule plainly: "If the
spec and this file disagree, the spec wins." Nothing enforced that until now.
The standard is young and moving — v2.1.0 is over a year old and rosters,
runtimes, and chargers are live proposals — so `schema.py` can fall behind
without anyone noticing.

`scripts/spec_watch.py` is the tripwire. It fetches the spec markdown,
parses its field tables, and diffs them against `tods_validate.schema.TABLES`,
reporting any field that was added, removed, or changed type/presence/enum
values. It is **advisory**: it never runs on `pull_request` or `push`, and it
is not part of the CI gate (`ruff` + `mypy` + `pytest --cov-fail-under=90` +
`generate_rules_doc.py --check` + `check_i18n.py`), matching the same
belt-and-suspenders posture as [mutation testing](mutation-testing.md).

## Running it

```sh
# Against the live upstream spec (default: raw GitHub URL on `main`).
python scripts/spec_watch.py

# Against a local copy — e.g. a fork under review, or a fixture.
python scripts/spec_watch.py --spec-file path/to/index.md

# Markdown output, for pasting into an issue or PR.
python scripts/spec_watch.py --format markdown
```

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | in sync — no drift found |
| 1 | drift found (the advisory signal the CI workflow acts on) |
| 2 | the spec could not be fetched or parsed; comparison was skipped |

Network access is optional by design: a fetch failure prints a clear message
and exits 2, distinct from the "drift found" exit 1, so CI logs and any
scripting around this command can tell "no signal" apart from "signal:
drift."

## Scope

The spec spells out fields one table per `### `filename.txt`` heading, but
only for the TODS-specific files: `run_events.txt`, `employee_run_dates.txt`,
`vehicles.txt`, and `vehicle_assignments.txt`. Supplement files
(`*_supplement.txt`) are documented as "fields match the corresponding GTFS
file" plus a handful of `TODS_`-prefixed additions listed in one flat table
keyed by filename — `schema.py` synthesizes their `TableSpec.fields` from the
GTFS field inventory (`GTFS_FIELDS`) rather than transcribing them from a
spec table, so a line-by-line diff against a spec table isn't meaningful for
them. `spec_watch.py` only diffs tables it finds an actual field table for; a
spec table found under a name not already in `TABLES` is reported as a new
table (drift), since that would mean the spec introduced a new TODS-specific
file.

References (`FieldSpec.references`) are intentionally not diffed — the spec's
Type column mixes reference targets into prose ("ID referencing
`calendar.service_id`") in ways not worth round-tripping precisely; type,
presence, and enum values are the load-bearing comparison.

### A known, expected false positive

`vehicle_assignments.txt`'s `service_id` is transcribed in `schema.py` as
`Presence.CONDITIONAL` ("Required if `block_id`s are repeated between
different `service_id`s"), but the spec's Required *column* literally says
"Optional" — the condition lives only in the Description prose, which this
script does not parse for presence. Running `spec_watch.py` against the real
upstream spec today reports this one field as a presence change. That is a
correct read of the literal table cell, not a bug; it's flagged here so it
doesn't surprise the first person who runs this against the live spec. Fixing
it properly means parsing conditional language out of free-text
descriptions, which is out of scope for a table diff — see EXP-03 in
`docs/ideation/03-expansions.md` if that's worth doing later.

## The weekly workflow

`.github/workflows/spec-watch.yml` runs on `workflow_dispatch` and a weekly
cron (staggered from `mutation.yml`'s Monday 06:00 UTC run). It installs the
package, runs `spec_watch.py --format markdown`, and — only when drift is
found — opens or updates a GitHub issue titled "Spec drift detected" with the
rendered diff as the body, searching for an existing open issue first so
repeated weeks update one issue instead of piling up duplicates. The whole
job runs with `continue-on-error: true` and treats every command as `|| true`
so a spec-fetch hiccup or parse issue can never fail the workflow, let alone
block a merge.

## Testing

`tests/test_spec_watch.py` exercises the parser and diff functions directly
(loaded via `importlib`, the same pattern `tests/test_conformance_corpus.py`
uses for `scripts/build_conformance_corpus.py`) against two small fixtures
under `tests/fixtures/spec_watch/`:

- `in_sync.md` — a trimmed spec copy covering the four TODS-specific tables,
  kept field-for-field consistent with `schema.py`. Diffing it produces zero
  drift.
- `drifted.md` — the same fixture with exactly one field changed
  (`vehicles.txt`'s `vehicle_label` flipped from `Optional` to `Required`).
  Diffing it produces exactly one `changed` entry, rendered as a
  human-readable diff.

These are the network-free path; the fixtures never touch the real upstream
URL, so the tests are deterministic and offline.
