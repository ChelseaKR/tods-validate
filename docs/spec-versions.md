# Spec versions

`tods-validate` validates against TODS v2.1.0 by default. Pass
`--spec-version 1.0.0` (or `spec-version = "1.0.0"` in `tods-validate.toml`)
to validate against the last version before the standard changed shape:
`SUPPORTED_SPEC_VERSIONS` in `src/tods_validate/schema.py` is the exact set
this build accepts; an unsupported value fails with exit code 2 rather than
silently validating against the wrong text.

This file exists so the two schemas, and what running each one actually
checks, are documented in one place instead of only in code comments. Every
field/file claim below is transcribed from a fetched spec source, cited
inline; see `src/tods_validate/schema.py` for the field-level transcription.

## Why v1.0.0 and not something in between

v1.0.0 (approved 2022-05-03) and v2.1.0 (approved 2025-04-16) are the two
endpoints of the standard's [revision
history](https://tods-transit.org/spec/revision-history/). v2.0.0-alpha.1
(2024-06-20) is the actual shape boundary — it removed `deadheads.txt`,
`ops_locations.txt`, and `deadhead_times.txt`, and introduced the
Supplement-file mechanism (`trips_supplement.txt` etc.) — but the source
repository does not preserve a browsable spec-text snapshot at that exact
tag; there is no git tag for any TODS release, only the prose revision-history
page. v1.0.0 is the last version whose spec text is cleanly recoverable at a
single, reproducible commit (see below), and it is on the far side of every
structural change v2 made, so validating against it exercises the full
delta rather than a partial one.

## Where each version's text comes from

- **v2.1.0**: the live spec at <https://tods-transit.org/spec/> and its
  source, `docs/en/spec/index.md` on
  [`MobilityData/transit-operational-data-standard`](https://github.com/MobilityData/transit-operational-data-standard)
  `main`. Same source `docs/rules.md` and `docs/spec-questions.md` already
  cite.
- **v1.0.0**: no longer published at a live URL — the current site only
  hosts the current spec text, and v1's three TODS-specific files were
  deleted from the spec source when v2.0.0-alpha.1 shipped. Its text is
  transcribed from the last commit that touched the spec before v2 work
  began:
  [`27d3694`](https://github.com/MobilityData/transit-operational-data-standard/blob/27d3694c8f73cbcf0ee349d8a9155d9d115b278e/docs/spec/index.md)
  ("rename duplicate `to_deadhead_id` field", 2022-10-18 — the commit
  immediately before
  [`41ac868`](https://github.com/MobilityData/transit-operational-data-standard/commit/41ac86864636d1138c9db6cf1b13f72314cfe30d)
  ("Reference for TODS \_supplement structure", 2024-02-27), the first
  v2-oriented change). That page states "last updated on April 14, 2022
  (v1.0)", consistent with the revision history's 2022-05-03 approval date.
  `schema.SPEC_URL_V1` points at this commit; every v1.0.0 finding's spec
  link resolves there, not to the live site.

## What changed between v1.0.0 and v2.1.0

| | v1.0.0 | v2.1.0 |
| --- | --- | --- |
| Files | 5 TODS-specific files | 6 Supplement files (overlaying GTFS) + 4 TODS-specific files |
| Non-revenue movement | `deadheads.txt` + `deadhead_times.txt` (own file pair, own `ops_locations.txt` stop-equivalent) | Folded into `trips_supplement.txt` / `stop_times_supplement.txt`; no separate deadhead files |
| Personnel schedule | `runs_pieces.txt` + `run_events.txt` (event-oriented: one row per event, keyed by `piece_id`) | `run_events.txt` only (trip/duty-oriented: one row per duty segment, keyed by `service_id`+`run_id`+`event_sequence`) — same filename, incompatible fields |
| Employee-to-run assignment | none | `employee_run_dates.txt` |
| Vehicles | none | `vehicles.txt` + `vehicle_assignments.txt` |
| "Primary Key" declared per file | No file states one (only `runs_pieces.txt` says a field "must be unique," in prose) | Every TODS-specific file states one (`employee_run_dates.txt` states `*`, meaning none) |
| GTFS overlay mechanism | none — v1 files reference GTFS directly (`deadheads.service_id` -> `calendar.service_id`, etc.) | Supplement files (`_supplement.txt`) add/modify/delete rows in a companion GTFS feed |

## File-by-file inventory

### v1.0.0 (5 files, all TODS-specific, all optional)

Field lists here are exact transcriptions of the historical spec's field
tables; see the module docstring in `schema.py` for the full citation and
the two documented gaps below.

**`deadheads.txt`** — `deadhead_id` (ID, Required), `service_id` (ID ->
`calendar.service_id`, Required), `block_id` (ID, Required), `shape_id` (ID
-> `shapes.shape_id`, Optional), `to_trip_id` / `from_trip_id` (ID ->
`trips.trip_id`, Conditionally Required), `to_deadhead_id` /
`from_deadhead_id` (ID -> `deadheads.deadhead_id`, Conditionally Required).

**`ops_locations.txt`** — `ops_location_id` (ID, Required),
`ops_location_code` (String, Optional), `ops_location_name` (String,
Required), `ops_location_desc` (String, Optional), `ops_location_lat`
(Latitude, Required), `ops_location_lon` (Longitude, Required).

**`deadhead_times.txt`** — `deadhead_id` (ID -> `deadheads.deadhead_id`,
Required), `arrival_time` / `departure_time` (Time, Required),
`ops_location_id` (ID -> `ops_locations.ops_location_id`, Conditionally
Required), `stop_id` (ID -> `stops.stop_id`, Conditionally Required —
exactly one of `ops_location_id`/`stop_id` per row), `location_sequence`
(Non-negative Integer, Required), `shape_dist_traveled` (Non-negative Float,
Optional).

**`runs_pieces.txt`** — `run_id` (ID, Required), `piece_id` (ID, Required;
"the piece_id field must be unique" — encoded as this file's primary key),
`start_type` / `end_type` (Enum: `0` Deadhead, `1` Trip, `2` Event,
Required), `start_trip_id` / `end_trip_id` (ID ->
`deadheads.deadhead_id` or `trips.trip_id` depending on `start_type`/
`end_type`, Required), `start_trip_position` / `end_trip_position`
(Non-negative Integer -> `deadhead_times.location_sequence` or
`stop_times.stop_sequence`, Optional).

**`run_events.txt`** (v1 shape) — `run_event_id` (ID, Required), `piece_id`
(ID -> `runs_pieces.piece_id`, Required), `event_type` (Enum: `0` Report
Time, `1` Pre-Trip Activity, `2` Post-Trip Activity, `3` Fueling, `4` Break,
`5` Availability, `6` Activity, `7` Other, Required), `event_name` (String,
Optional), `event_time` (Time, Required), `event_duration` (Non-negative
Integer, Required), `event_from_location_type` / `event_to_location_type`
(Enum: `0` Operational Location, `1` Stop, Optional),
`event_from_location_id` / `event_to_location_id` (ID ->
`ops_locations.ops_location_id` or `stops.stop_id`, Optional).

Two things the v1.0.0 text does not state, left as the spec leaves them
rather than guessed at (see `schema.py`'s module docstring):

1. **No "Primary Key" declared** for any file except the `piece_id` case
   above. Under a strict relational reading an exact-duplicate row would
   still be nonsensical, but the validator does not invent a key the spec
   never names — `TABLES_V1[...].primary_key` is `None` everywhere except
   `runs_pieces.txt`, so `TODS-E204` (duplicate primary key) only fires
   there under `--spec-version 1.0.0`.
2. **No packaging/transport format**, same open question
   `docs/spec-questions.md` #1 records for the current spec — v1.0.0 does
   not resolve it either.

### v2.1.0 (10 files: 6 Supplement, 4 TODS-specific, all optional)

Already documented in full in [`docs/rules.md`](rules.md) (the field-level
detail lives in each rule's spec citation) and `schema.py`'s `TABLES`. Not
repeated here.

## What `--spec-version 1.0.0` actually checks

The rule set is not two independent implementations. Structure and
field-value rules (`TODS-x1xx`, `TODS-x2xx` — required columns, required
values, enum values, value formats, duplicate primary keys, padded values)
are written generically over whichever file/field inventory
`ValidationContext.spec_version` selects
(`ValidationContext.tables`, `schema.tables_for_version()`), so the same
rule logic and the same rule IDs apply to both spec versions. A finding's
spec-citation link switches automatically (`schema.spec_link()`): v1.0.0
findings link to the historical commit above; v2.1.0 findings link to the
live site.

Reference rules (`TODS-x3xx`), semantic rules (`TODS-x4xx`), and the opt-in
coverage/advisory categories do not run under `--spec-version 1.0.0`. They
assume mechanisms and field names v1.0.0 does not have:

- The Supplement-file / "TODS-Supplemented GTFS" merge concept
  (`references.py`'s entire rule set) does not exist before v2.0.0-alpha.1.
- v2.1.0's `run_events.txt` fields (`service_id`, `run_id`,
  `event_sequence`, `start_time`, `end_time`) that `semantics.py` and
  `coverage.py` read do not exist on v1.0.0's `run_events.txt`, which uses
  `event_time`/`event_duration` and has no `service_id`/`run_id` at all.
- `vehicle_assignments.txt`, `vehicles.txt`, and `employee_run_dates.txt`
  (referenced by several `x3xx`/`x4xx`/coverage rules, plus field rule
  `TODS-E205`) do not exist in v1.0.0.

Each such rule is tagged `spec_versions=(SPEC_VERSION,)` in its module
(`rules/references.py`, `rules/semantics.py`, `rules/coverage.py`, and
`TODS-E205` in `rules/fields.py`) rather than silently misapplied to data it
was not written for. A `--spec-version 1.0.0` run's coverage manifest
(`--format json`'s `coverage` block, or the `Checks skipped:` summary line)
discloses these as `skipped:spec_version`, distinct from `skipped:disabled`
or `skipped:needs_gtfs`, so the report states its own scope rather than
implying a clean v1.0.0 run checked everything v2.1.0 does.

### Known scope limits (not fixed by this flag)

- `tods-validate merge`, `tods-validate init`, `tods-validate anonymize`,
  the language server (`tods-validate lsp`), and `--suggest`'s value-format
  suggestions (`TODS-E203`'s "review" suggestions in `suggest.py`) all read
  the v2.1.0 schema unconditionally; they do not accept `--spec-version`.
  `merge` in particular is inherently v2.1.0-only — the Supplement mechanism
  it materializes does not exist in v1.0.0. `--suggest` under
  `--spec-version 1.0.0` still runs (whitespace-trim and duplicate-row
  suggestions are schema-independent) but offers no format-normalization
  suggestions for v1-only field names, since it checks the proposed value
  against the v2.1.0 field-type table; it degrades to proposing nothing
  rather than a wrong fix.
- No fixture in the published conformance corpus
  (`docs/conformance.md`) targets v1.0.0; the corpus's one-fixture-per-rule
  contract is scoped to the default spec version. `tests/fixtures/spec_v1/`
  carries a small, separate set of v1.0.0 fixtures exercised by
  `tests/test_spec_versions.py`.

## Adding a third version

If TODS adopts a v3, the shape to follow is: add a `TableSpec` dict in
`schema.py` (transcribed from a real fetched spec source, cited the same
way), register it in `TABLES_BY_VERSION`, add the version string to
`SUPPORTED_SPEC_VERSIONS`, and decide per rule module whether its `x3xx`/
`x4xx`/coverage/advisory rules generalize or need `spec_versions` gating —
the `x1xx`/`x2xx` rules should not need any change, since they already read
the schema generically through `ValidationContext.tables`.
