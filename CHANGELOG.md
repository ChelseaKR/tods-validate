# Changelog

Notable changes to tods-validate. Rule IDs are never renumbered or reused;
new checks may be added in minor releases.

## Unreleased

- `tods-validate rules` lists the rule catalog from the tool itself
  (`--format json` for tooling).
- Published JSON Schema for the `--format json` report
  (docs/report.schema.json), enforced by tests.
- Dockerfile and a workflow publishing images to GHCR on each release.
- pre-commit hook definition (.pre-commit-hooks.yaml).

## v0.3.0 - 2026-06-12

- New `merge` subcommand writes the "TODS-Supplemented GTFS" dataset (the
  GTFS feed after supplement rows are applied) to a directory or .zip, with
  per-file counts of updated, added, and deleted rows. The merged feed can
  then be checked with MobilityData's gtfs-validator.
- New rule TODS-E314: a supplement row references a route, service, trip, or
  stop that does not exist in the supplemented feed.
- The CLI now has explicit `validate` and `merge` subcommands;
  `tods-validate PATH` without a subcommand still validates, so existing
  invocations and the GitHub Action are unaffected.

## v0.2.0 - 2026-06-12

- `--ignore RULE_ID` (repeatable) suppresses specific rules.
- Optional `tods-validate.toml` configuration file (`ignore`, `fail-on`),
  discovered in the working directory or passed with `--config`.
- `--format markdown`: a report suitable for pasting into an issue or a
  working-group thread.

## v0.1.0 - 2026-06-12

First release: 35 checks against TODS v2.1.0 covering file structure, field
values, references (including into the companion GTFS feed after supplements
are applied), and schedule semantics. CLI with text, JSON, and GitHub
annotation output, plus a composite GitHub Action.
