# Spec questions

Ambiguities and possible errata in TODS v2.1.0 (adopted 2025-04-16) found while
implementing this validator. Where the spec is ambiguous, the validator takes
the permissive interpretation noted under each entry, and the relevant rule ID
is given so the behavior is traceable. These are offered as candidates for
issues or discussion on the
[specification repository](https://github.com/MobilityData/transit-operational-data-standard),
not as assertions that the spec is wrong; happy to open PRs for the clear-cut
ones.

Each entry cites the spec section it refers to. Verified against the spec
reference (`docs/en/spec/index.md`) and `examples.md` on
`MobilityData/transit-operational-data-standard` `main`, which matches the
published spec at <https://tods-transit.org/>.

## 1. Packaging is undefined

The spec defines ten files but never says how a TODS dataset is packaged or
distributed: a zip, a directory, alongside the public GTFS feed or separate
from it, or under what filename conventions a consumer should discover it.

*Reference:* the [spec reference](https://tods-transit.org/spec/) lists the
files but contains no packaging or distribution section.
*Validator behavior:* accepts a directory or a .zip of top-level .txt files,
with or without GTFS files in the same package. If GTFS files are present they
are used as the companion feed.

## 2. The "Run as Directed" example appears to violate the primary key rule

In the spec's
[Run as Directed work example](https://tods-transit.org/spec/examples/#run-as-directed-work),
the last two rows of `run_events.txt` both use `event_sequence` 30 on run
(`weekday`, `10000`):

```csv
weekday,10000,30,BLOCK-A,run-as-directed,...
weekday,10000,30,BLOCK-A,deadhead,...
```

`run_events.txt` declares Primary Key `(service_id, run_id, event_sequence)`,
and the `event_sequence` field note says it "Must be unique within one
(`service_id`, `run_id`)", so this example data is invalid. Presumably the
second row should be sequence 40.

*Reference:* `run_events.txt` Primary Key and `event_sequence` field note
([spec](https://tods-transit.org/spec/#run_eventstxt)); the example
([examples](https://tods-transit.org/spec/examples/#run-as-directed-work)).
*Validator behavior:* reported as TODS-E204 (duplicate primary key).

## 3. Example CSVs contain padded values

Several example CSV snippets pad values with spaces for column alignment,
e.g. `weekday,10000,10,       ,sign-in        ,...`. GTFS-style CSV has no
trimming rule for values, so a literal reading produces `block_id` / `event_type`
values that include the spaces. Are consumers expected to trim?

*Reference:* the `run_events.txt` blocks in the
[Run as Directed work](https://tods-transit.org/spec/examples/#run-as-directed-work)
and "Jobs of entirely nonrevenue operations" examples.
*Validator behavior:* values are compared exactly; padding is flagged as a
warning (TODS-W206) because padded IDs will not match their referents.

## 4. `mid_trip` field names are inconsistent between prose and the field table

The `run_events.txt` field descriptions refer to `mid_trip_start` and
`mid_trip_end` in prose ("If `trip_id` is set (and `mid_trip_start` is not
`1`)...") while the field table defines the fields as `start_mid_trip` and
`end_mid_trip`. Presumably the same fields are meant.

*Reference:* the `start_location` / `start_time` field descriptions versus the
`start_mid_trip` / `end_mid_trip` rows in the `run_events.txt` field table
([spec](https://tods-transit.org/spec/#run_eventstxt)).

## 5. The `Time` type for `start_time`/`end_time` is undefined

`start_time` and `end_time` are typed `Time` in the `run_events.txt` field
table, but the spec never defines `Time`: there is no field-types or
term-definitions section, and the format is never stated. GTFS time allows
hours `>= 24:00:00` for service past midnight, but no example demonstrates that
case (the after-midnight "Jobs of entirely nonrevenue operations" example uses
00:45 to 03:00, and every example time stays under 24:00:00), so whether GTFS
time syntax is intended for these fields is left open. The spec also does not
state whether an event's `end_time` must be greater than or equal to its
`start_time` (zero-duration events are explicitly allowed; negative durations
are never mentioned).

*Reference:* the `Time`-typed `start_time` / `end_time` rows in the
`run_events.txt` field table ([spec](https://tods-transit.org/spec/#run_eventstxt));
the spec's only GTFS term-definitions link is for *service day* on
`vehicle_assignments.service_id`, not for `Time`. Field naming (not format) was
settled in
[issue #48](https://github.com/MobilityData/transit-operational-data-standard/issues/48).
*Validator behavior:* GTFS time syntax including hours `>= 24:00:00` is accepted
(malformed times are TODS-E203); `end_time` earlier than `start_time` is an
error (TODS-E401).

## 6. `employee_run_dates.txt` declares Primary Key `*`

A primary key of `*` (every field) would make exactly duplicated rows invalid,
but the prose only discusses run-and-date combinations appearing multiple times
for multiple employees. Whether a fully identical duplicate row (same employee,
run, and date twice) is valid is unstated.

*Reference:* `employee_run_dates.txt` Primary Key
([spec](https://tods-transit.org/spec/#employee_run_datestxt)).
*Validator behavior:* exact duplicates are a warning (TODS-W408), not an error.

## 7. How strictly should added supplement rows meet GTFS requirements

A supplement row that *adds* a new entity (e.g. a new trip) does not have to
carry all fields GTFS marks required, and the spec only says the merged result
"should form a valid GTFS dataset" with limited exceptions. It is unclear how
strictly consumers should hold added rows to GTFS requirements, e.g. a trip
added without a `service_id`.

*Reference:* the dataset-modification rules: "the resulting data
('TODS-Supplemented GTFS') should form a valid GTFS dataset, with the limited
exception of missing data that should be ignored"
([spec](https://tods-transit.org/spec/)).
*Validator behavior:* only the primary-key fields are required on supplement
rows; full GTFS validation is delegated to gtfs-validator run on the merged
feed.

## 8. `vehicle_assignments.service_id` condition reads as global, not per-row

`service_id` is "Required if `block_id`s are repeated between different
`service_id`s." Read literally, one repeated block anywhere in the feed makes
the field required on every row. The more useful reading is per-row: required
where that row's `block_id` is ambiguous.

*Reference:* the `vehicle_assignments.service_id` field condition
([spec](https://tods-transit.org/spec/#vehicle_assignmentstxt)).
*Validator behavior:* per-row interpretation (TODS-E205 fires only for rows
whose block is used by more than one service).
