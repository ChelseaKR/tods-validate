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

*Upstream:* [MobilityData/transit-operational-data-standard#151](https://github.com/MobilityData/transit-operational-data-standard/issues/151)

The spec names the ten files and their filename conventions (the `_supplement`
suffix and the exact filenames), but never says how a TODS dataset is
physically packaged or distributed: a zip, a directory, or how a consumer
discovers and retrieves the files. It frames TODS as a typically non-public
layer separate from the public GTFS feed, but the packaging and transport
format is never formalized.

*Reference:* the Files table ([spec](https://tods-transit.org/spec/)) defines
the filenames and the `_supplement` suffix; no section specifies a packaging,
bundling, or discovery format.
*Validator behavior:* accepts a directory or a .zip of top-level .txt files,
with or without GTFS files in the same package. If GTFS files are present they
are used as the companion feed.

## 2. The "Run as Directed" example appears to violate the primary key rule

*Upstream:* fixed by [MobilityData/transit-operational-data-standard#147](https://github.com/MobilityData/transit-operational-data-standard/pull/147).

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

*Upstream:* resolution agreed in
[MobilityData/transit-operational-data-standard#152](https://github.com/MobilityData/transit-operational-data-standard/issues/152).
The documentation patch is under upstream review in
[PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156)
and is not yet merged.

Several example CSV snippets pad values with spaces for column alignment,
e.g. `weekday,10000,10,       ,sign-in        ,...`. GTFS-style CSV has no
trimming rule for values, so a literal reading produces `block_id` / `event_type`
values that include the spaces. The issue discussion confirmed that GTFS
requires extra spaces to be removed and that the examples should lose their
alignment padding.

*Reference:* the `run_events.txt` blocks in the
[Run as Directed work](https://tods-transit.org/spec/examples/#run-as-directed-work)
and "Jobs of entirely nonrevenue operations" examples.
*Validator behavior:* values are compared exactly; padding is flagged as a
warning (TODS-W206) because padded IDs will not match their referents.

## 4. `mid_trip` field names are inconsistent between prose and the field table

*Upstream:* prose correction agreed in
[MobilityData/transit-operational-data-standard#152](https://github.com/MobilityData/transit-operational-data-standard/issues/152).
The documentation patch is under upstream review in
[PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156)
and is not yet merged.

The `run_events.txt` field descriptions refer to `mid_trip_start` and
`mid_trip_end` in prose ("If `trip_id` is set (and `mid_trip_start` is not
`1`)...") while the field table defines the fields as `start_mid_trip` and
`end_mid_trip`. Presumably the same fields are meant.

*Reference:* the `start_location` / `start_time` field descriptions versus the
`start_mid_trip` / `end_mid_trip` rows in the `run_events.txt` field table
([spec](https://tods-transit.org/spec/#run_eventstxt)).

## 5. The `Time` type for `start_time`/`end_time` is undefined

*Upstream:* fixed by
[MobilityData/transit-operational-data-standard#150](https://github.com/MobilityData/transit-operational-data-standard/pull/150),
following
[issue #148](https://github.com/MobilityData/transit-operational-data-standard/issues/148).

`start_time` and `end_time` previously used an undefined `Time` type. PR #150
now defines them using GTFS Time and includes a post-midnight example, resolving
the syntax question. The spec still does not expressly discuss negative event
durations; zero-duration events are allowed.

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

*Upstream:* explicit four-field key agreed in
[MobilityData/transit-operational-data-standard#152](https://github.com/MobilityData/transit-operational-data-standard/issues/152).
The documentation patch is under upstream review in
[PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156)
and is not yet merged.

`employee_run_dates.txt` declares `Primary Key: *`, but TODS never defines what
`*` means: it has no conventions or terms section, and it states GTFS field
inheritance only for Supplement files, not for its TODS-Specific files. Under
GTFS's `*` convention (all fields jointly form the key) an exactly-duplicated
row would be invalid, but because TODS does not state this for its own files,
the status of a fully identical duplicate row (same employee, run, and date
twice) is left implicit. The prose only discusses run-and-date combinations
recurring across different employees, which have distinct keys.

*Reference:* `employee_run_dates.txt` Primary Key
([spec](https://tods-transit.org/spec/#employee_run_datestxt)); TODS states
GTFS-convention inheritance only for Supplement files and has no section
defining `*`.
*Validator behavior:* exact duplicates are primary-key errors (TODS-E204).
TODS-W408 remains as a grouped compatibility signal for existing machine
consumers that tracked the earlier warning ID.

## 7. How strictly should added supplement rows meet GTFS requirements

*Upstream:* added-row requirement agreed in
[MobilityData/transit-operational-data-standard#152](https://github.com/MobilityData/transit-operational-data-standard/issues/152).
The documentation patch is under upstream review in
[PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156)
and is not yet merged.

A supplement row that *adds* a new entity (e.g. a new trip) does not have to
carry all fields GTFS marks required, and the spec only says the merged result
"should form a valid GTFS dataset" with limited exceptions. It is unclear how
strictly consumers should hold added rows to GTFS requirements, e.g. a trip
added without a `service_id`.

*Reference:* the dataset-modification rules: "the resulting data
('TODS-Supplemented GTFS') should form a valid GTFS dataset, with the limited
exception of missing data that should be ignored"
([spec](https://tods-transit.org/spec/)).
*Validator behavior:* primary-key fields are always required. When a companion
GTFS proves that a non-delete supplement row is an addition, TODS-E201 also
requires every field marked Required in the corresponding GTFS file. Without a
companion feed, the validator stays permissive because it cannot distinguish an
addition from an update. Conditional GTFS requirements and full merged-feed
validity remain delegated to gtfs-validator.

## 8. `vehicle_assignments.service_id` condition reads as global, not per-row

*Upstream:* per-row wording agreed in
[MobilityData/transit-operational-data-standard#152](https://github.com/MobilityData/transit-operational-data-standard/issues/152).
The documentation patch is under upstream review in
[PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156)
and is not yet merged.

`service_id` is "Required if `block_id`s are repeated between different
`service_id`s." Read literally, one repeated block anywhere in the feed makes
the field required on every row. The more useful reading is per-row: required
where that row's `block_id` is ambiguous.

*Reference:* the `vehicle_assignments.service_id` field condition
([spec](https://tods-transit.org/spec/#vehicle_assignmentstxt)).
*Validator behavior:* per-row interpretation (TODS-E205 fires only for rows
whose block is used by more than one service).
