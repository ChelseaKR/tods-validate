# Roadmap

Planned direction for tods-validate. Dates are intentions, not promises;
items move earlier when users ask for them. Feedback and feature requests
are welcome as GitHub issues.

## v0.2.0 — Suppression and reporting

- `--ignore TODS-Wxxx` (repeatable) and a `tods-validate.toml` config file so
  agencies can encode local policy and run the validator in CI without
  fighting warnings they have decided to accept.
- `--format markdown`: a report suitable for pasting into an issue or a
  working-group thread.
- Fixes from validating real-world feeds. If you produce or consume TODS and
  can share a feed (privately is fine), please open an issue.

## v0.3.0 — The merge pipeline

- `tods-validate merge feed/ -o supplemented.zip`: materialize the
  "TODS-Supplemented GTFS" the spec describes, so the result can be checked
  with MobilityData's gtfs-validator. The spec says the merged dataset should
  form a valid GTFS feed; this makes that property testable.
- Supplement-internal reference checks (for example,
  `stop_times_supplement.txt:trip_id` resolving against supplemented trips).
- A documented CI recipe chaining merge and gtfs-validator.

## v0.4.0 — Distribution surfaces

- Docker image on GHCR for CI environments without Python.
- `--list-rules --format json` and a published JSON Schema for the report
  format, so dashboards can consume findings without scraping text.
- A pre-commit hook definition.
- Performance benchmarks on large feeds.

## v0.5.0 — Spec tracking

- `--spec-version` flag. TODS changed substantially between v1 and v2; the
  validator should be explicit about which spec text it enforces.
- Validation for spec additions as they are adopted upstream (the spec
  repository currently has open proposals for rosters, runtimes, and
  electrification files such as chargers and energy consumption).
- Offering this project's fixture feeds upstream as a conformance suite.

## v1.0.0 — Stability commitments

Gated on the rule set proving out against multiple production feeds and on
no rule-ID churn for two consecutive releases. v1.0 means semantic-versioning
guarantees on rule IDs, exit codes, and the JSON report schema, plus an
acceptance-test corpus in CI.

## Out of scope

Validating GTFS itself (use
[gtfs-validator](https://github.com/MobilityData/gtfs-validator)),
GTFS-realtime correlation, and feed editing or repair beyond the merge
described above.
