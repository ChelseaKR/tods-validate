# Spec questions

Ambiguities and possible errata found in TODS v2.1.0 (reference dated
2025-04-16) while implementing this validator. Where the spec is ambiguous,
the validator takes the permissive interpretation noted under each entry.
These are candidates for issues or discussion topics on the
[specification repository](https://github.com/MobilityData/transit-operational-data-standard).

## 1. Packaging is undefined

The spec defines ten files but never says how a TODS dataset is packaged or
distributed: a zip, a directory, alongside the public GTFS feed or separate
from it, or under what filename conventions a consumer should discover it.

*Validator behavior:* accepts a directory or a .zip of top-level .txt files,
with or without GTFS files in the same package. If GTFS files are present they
are used as the companion feed.

## 2. The "Run as Directed" example appears to violate the primary key rule

In the spec's [Run as Directed example](https://tods-transit.org/spec/examples/#run-as-directed-work),
the last two rows of `run_events.txt` both use `event_sequence` 30 on run
(`weekday`, `10000`):

```csv
weekday,10000,30,BLOCK-A,run-as-directed,...
weekday,10000,30,BLOCK-A,deadhead,...
```

`event_sequence` "must be unique within one (service_id, run_id)", so this
example data is invalid (this validator reports it as TODS-E204). Presumably
the second row should be sequence 40.

## 3. Example CSVs contain padded values

Several example CSV snippets pad values with spaces for column alignment,
e.g. `daily,10000,10,       ,       ,Operator,...`. GTFS-style CSV has no
trimming rule for values, so a literal reading produces `piece_id` values of
seven spaces. Are consumers expected to trim?

*Validator behavior:* values are compared exactly; padding is flagged as a
warning (TODS-W206) because padded IDs will not match their referents.

## 4. `start_mid_trip` enum wording is inconsistent

`run_events.txt` field descriptions refer to `mid_trip_start` and
`mid_trip_end` in prose ("If `trip_id` is set (and `mid_trip_start` is not
`1`)...") while the field names are `start_mid_trip` and `end_mid_trip`.
Presumably the same fields are meant.

## 5. Time bounds for `start_time`/`end_time` are unstated

The `Time` type for `run_events.txt` `start_time`/`end_time` is never defined:
there is no field-types section, and the spec never states the format. GTFS
time allows hours `>= 24:00:00` for service past midnight, but no example
demonstrates that case (the after-midnight inspection example uses 00:45 to
03:00, and every example time stays under 24:00:00), so whether GTFS time
syntax is intended for these fields is left open. The spec also does not state
whether an event's `end_time` must be greater than or equal to its `start_time`
(zero-duration events are explicitly allowed, negative durations are never
mentioned).

*Validator behavior:* GTFS time syntax with hours beyond 24 is accepted;
`end_time` earlier than `start_time` is an error (TODS-E401).

## 6. `employee_run_dates.txt` says "Primary Key: `*`"

A primary key of `*` (every field) would make exactly duplicated rows
invalid, but the prose only discusses run-and-date combinations appearing
multiple times for multiple employees. Whether a fully identical duplicate
row (same employee, run, and date twice) is valid is unstated.

*Validator behavior:* exact duplicates are a warning (TODS-W408), not an
error.

## 7. Scope of "supplement" files relative to GTFS required fields

A supplement row that *adds* a new entity (e.g. a new trip) does not have to
carry all fields GTFS marks required, and the spec only says the merged
result "should form a valid GTFS dataset" with limited exceptions. It is
unclear how strictly consumers should hold added rows to GTFS requirements,
e.g. a trip added without a `service_id`.

*Validator behavior:* only the primary-key fields are required on supplement
rows; full GTFS validation is delegated to gtfs-validator run on the merged
feed.

## 8. `vehicle_assignments.service_id` condition is global, not per-row

`service_id` is "Required if `block_id`s are repeated between different
`service_id`s." Read literally, one repeated block anywhere in the feed makes
the field required on every row. The more useful reading is per-row: required
where that row's `block_id` is ambiguous.

*Validator behavior:* per-row interpretation (TODS-E205 fires only for rows
whose block is used by more than one service).
