# Changelog

Notable changes to tods-validate. Rule IDs are never renumbered or reused;
new checks may be added in minor releases.

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
