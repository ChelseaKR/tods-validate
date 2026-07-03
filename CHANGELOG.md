# Changelog

Notable changes to tods-validate. Rule IDs are never renumbered or reused;
new checks may be added in minor releases.

## Unreleased

Added:

- `batch --format markdown`, alongside a new `batch --stamp` flag: renders one
  stamped fleet/portfolio compliance report across every feed passed to
  `batch`, instead of one report per feed. The report is a summary table
  (source, errors, warnings, infos, pass/fail/error status) plus a fleet
  totals line and, with `--stamp`, the same provenance footer (tool version,
  spec version, UTC timestamp) as `validate --stamp` — a citable artifact,
  not a hosted dashboard.
- TODS-W316: the time companion of W315. A run event that works a trip end to end
  should start at the trip's first scheduled departure and end at its last
  scheduled arrival; a mismatch is a warning, skipped for mid-trip events. Uses
  the stop_times the companion GTFS already ingests.
- TODS-W409: consecutive events in one run should connect in space — an event's
  end_location should be the next event's start_location, since an operator
  cannot teleport between locations. A gap is a warning (legitimate exceptions
  exist), and adjacencies with a blank endpoint are skipped. TODS-only, no
  companion GTFS needed.
- A language server (`tods-validate lsp`, or the `tods-validate-lsp` entry point)
  that re-validates the whole feed when you open or save any TODS file and shows
  each finding inline at its row and field. Findings name a field, so the
  diagnostic underlines the offending value, not just the line. Needs the new
  `lsp` extra (`pip install 'tods-validate[lsp]'`, which brings in pygls); the
  diagnostic-mapping core is pure and unit-tested without an editor.
- The language server now offers quick fixes and hovers. Hovering a finding
  shows the rule's title, description, and spec link; the fixable findings carry
  a code action — "Trim surrounding whitespace" (TODS-W206) and "Delete duplicate
  row" (TODS-W408) — that edits the document in place.
- A VS Code extension under `editor/vscode/` that launches the language server
  for TODS files, so the diagnostics, hovers, and quick fixes show up in the
  editor. It is a thin client (build it with `npm install && npm run compile`,
  press F5 to try it); it is not published to the Marketplace.
- `tods-validate validate --suggest` lists concrete fix suggestions for the
  mechanically-fixable findings after the report, each marked `auto` (safe and
  meaning-preserving, the kind `tods-validate fix` applies) or `review` (derivable
  but worth a human's confirmation, such as a time written `9:45` -> `09:45:00` or
  a date written `2026-03-15` -> `20260315`). A suggestion is only offered when its
  proposed value is one the validator would accept and is reachable by adding
  leading zeros, a zero seconds field, or removing date separators, so it never
  changes what a value means. Text and Markdown output only; the JSON report is
  left untouched so it stays a stable machine contract. The same suggestions are
  available programmatically via `tods_validate.suggest_fixes`.
- A test-helper module (`tods_validate.testing`) with `assert_feed_valid` and
  `assert_feed_produces`, so a TODS exporter can gate its own pytest suite on the
  same checks the CLI and Action run without shelling out. On failure they raise
  with the human-readable report rather than a stack trace. See docs/api.md.
- A contributor guide for authoring rules (docs/authoring-rules.md): how to pick
  a severity and allocate an ID, the scheduler-grade message style, and the
  fixture/conformance contract CI enforces.
- Reports now state their own scope. Every run records a coverage manifest —
  which rules ran, and which were skipped and why (no companion GTFS feed,
  opt-in rule not enabled, or suppressed by `--ignore`) — so "no problems
  found" is qualified by what was actually checked. The JSON report carries it
  as an additive `coverage` block (report schema 1.2.0, documented in
  docs/report.schema.json), SARIF records it under `invocations`, and the
  text/Markdown/HTML reports add a one-line "Checks skipped: …" disclosure
  (plus a coverage footer on stamped Markdown). Library callers can get the
  manifest via the new `tods_validate.runner.run_with_coverage`; `run` is
  unchanged.
- Reference findings (TODS-E301/E303/E307/E308/E309/E310/E311/E312/E314) now
  carry structured `data` parameters — the broken value and what it references
  — and the SARIF output is enriched from the rule registry: each descriptor
  gains the rule's title, description, and spec link (`helpUri`), and each
  result carries its finding's structured data in `properties`.
- `tods-validate explain RULE_ID`: an offline command that prints a rule's full
  detail — description, spec citation, and a worked before/after example — with
  `--format markdown` for pasting into an issue. Every core rule (and the
  opt-in coverage/advisory rules) now ships a worked example, sourced from one
  registry (`tods_validate.rules.EXAMPLES`) that `explain`, `docs/rules.md`,
  and LSP hovers all render through the same `render_rule_detail()`, so the
  three cannot drift from each other.

Changed:

- The `--format html` report is now an explicit accessibility pass: it declares
  its language and a responsive viewport, uses `header`/`main` landmarks, gives
  the findings table a caption and column-scoped headers, and lightens the info
  severity color so all three severities clear WCAG AA contrast on the white
  background. The README gained a short accessibility statement.
- `tods-validate fix` now does more than trim whitespace: it also drops
  entirely-blank rows (the `,,,` lines that otherwise raise a wall of E201) and
  removes rows that are byte-identical to an earlier one (the TODS-W408 duplicate
  assignment). A row that shares a primary key but differs in any value is a real
  conflict and is left untouched for a human. Still a dry run by default.

Fixed:

- The reported tool version (`toolVersion` in the JSON/HTML reports and
  `--version`) is now read from the installed package metadata instead of a
  hand-edited constant that had drifted to `0.4.0`.
- The README and `merge`-recipe GitHub Action snippets now reference the current
  `@v0.6.0` instead of the stale `@v0.4.0` they were pinned at.
- TODS-W302 now also discloses when `vehicle_assignments.txt` references could
  not be checked: block_id resolution needs the companion feed's `trips.txt`
  and service_id resolution needs `calendar.txt`/`calendar_dates.txt`; when a
  used column's target file is missing, those checks used to no-op silently.

Security / process (2026-07-05 standards-conformance remediation):

- The release pipeline (`pypi-publish.yml`, `docker.yml`, `release-corpus.yml`)
  no longer publishes anything without first re-running the full gate set
  (`make verify`, new) at the tagged commit, plus a version-consistency check
  and an annotated/signed-tag check; a `verify-published` job now re-checks
  the published artifact's provenance/signature after publish.
- Fixed template-injection-shaped patterns in `action.yml` and the release
  workflows (`${{ }}` no longer interpolated directly into `run:` shells).
- Added Semgrep, CodeQL (`python` + `actions`), zizmor, gitleaks (pre-commit
  + CI), and a blocking `pip-audit` gate; adopted `uv` with a committed
  `uv.lock`; added a Trivy CVE scan and a digest-pinned base image to the
  Docker build; the Dockerfile now runs as a non-root user.
- Added a `README.md` Standards Conformance table, `docs/CONFORMANCE-GAPS.md`,
  `docs/RESPONSIBLE-TECH-AUDITS.md`, `DEFINITION_OF_DONE.md`,
  `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS`, and a vendored
  copy of the engineering standards this project is held to
  (`docs/standards/`).
- No user-facing behavior changed in this entry; see `docs/CONFORMANCE-GAPS.md`
  for the full list of what closed and what remains open.

## v0.6.0 - 2026-06-29

New surfaces for working with a feed live (`--watch`, browser playground),
acting on findings (`fix`), and sharing results (`stats --format markdown`,
conformance corpus), plus a new cross-feed operational check (TODS-W315).

Added:

- `tods-validate validate --watch` re-validates whenever the feed changes
  (polls the files), the cheap interim ahead of editor/LSP integration.
- A browser playground (`web/`) that validates a feed entirely in the browser
  via Pyodide, with no upload, deployable to GitHub Pages. The Python it calls
  is guarded by tests; the page itself needs a browser to verify.
- TODS-W315: a run event that works a trip end to end should start at the
  trip's first stop and end at its last stop (in the supplemented
  `stop_times.txt`); a mismatch is a warning, skipped for mid-trip events. The
  companion GTFS now ingests `stop_times`, so this checks an operational
  consistency constraint no GTFS-only validator can see.
- `tods-validate fix` applies safe, deterministic fixes — currently trimming the
  TODS-W206 whitespace padding that stops IDs from matching. It is a dry run by
  default and writes a cleaned, UTF-8/no-BOM package with `-o`.
- `tods-validate stats --format markdown` prints a feed profile (now including a
  date range and a file-presence list) suitable for pasting into an issue or a
  working-group thread.
- A downloadable conformance corpus, attached to each release: every fixture
  plus an `expectations.json` mapping each to the rule IDs it should produce, so
  another validator can run the suite without cloning the repo
  (`scripts/build_conformance_corpus.py`).

## v0.5.0 - 2026-06-22

Correctness fixes (no rule IDs changed), a runnable bundled sample feed with a
fixed quickstart, and a conformance check that runs the spec's own examples.

Fixed (no rule IDs changed):

- TODS-E204 now detects duplicate `vehicle_assignments` primary keys when the
  optional `service_id` is blank (the common case). Previously a blank optional
  key component silently suppressed the whole uniqueness check, so real
  duplicate keys passed clean and coalesced during `merge`.
- Time values with hours `>= 100:00:00` are now accepted (GTFS time has no upper
  hour bound). They previously raised a false TODS-E203 and were dropped from the
  time-based semantic checks (E401/E402/W403).
- TODS-E314 no longer fires on a `stop_times_supplement` row whose trip was
  deleted via `trips_supplement` (`TODS_delete=1`); the spec says such
  stop_times are ignored, not an error.
- Duplicate header columns now keep the first occurrence's value (matching the
  TODS-E105 message that the duplicate column is ignored) instead of letting a
  later duplicate column silently win.
- All-blank data rows (a stray `,,,` line past the header) are no longer
  silently dropped; their missing required values are now reported (TODS-E201).
- TODS-E205 (vehicle_assignments block ambiguity) is now marked as requiring a
  companion GTFS feed, so a TODS-only run reports it as unchecked instead of
  silently passing the check.

Other:

- Bundled a runnable sample feed at `examples/sample-feed/` and pointed the
  README quickstart at it, so a new install has something that passes on the
  first run. The GitHub Action now sets up Python explicitly.

## v0.4.0 - 2026-06-20

Distribution, reporting, and analysis surfaces. No rule IDs changed; the JSON
report gained fields (it is now `reportVersion` 1.1.0) without removing any.

Added:

- `tods-validate rules` lists the rule catalog from the tool itself
  (`--format json` for tooling, now including category, default-enabled, and
  spec-interpretation metadata).
- Published JSON Schema for the `--format json` report
  (docs/report.schema.json), enforced by tests.
- Dockerfile and a workflow publishing images to GHCR on each release.
- pre-commit hook definition (.pre-commit-hooks.yaml).
- New report formats: `--format sarif` (GitHub code-scanning / security
  dashboards) and `--format html` (a standalone, shareable report).
- JSON report now carries `toolVersion`, `reportVersion`, a per-rule
  `summary.byRule` breakdown, and a stable `location` pointer per finding.
- Text and Markdown reports group findings by rule, show the shortest path to a
  clean run, and add root-cause hints when one rule clusters.
- New flags on `validate`: `--enable` (opt-in rules/categories), `--profile`
  (default/strict/lenient presets), `--spec-version`, `--baseline` (fail only
  on findings new since a previous JSON report), `--max-findings`, `--quiet`,
  `--stamp` (citable Markdown footer), and `--encoding`.
- New subcommands: `diff` (compare two feeds), `batch` (validate many feeds
  with a roll-up table), `stats` (descriptive feed metrics), and `anonymize`
  (pseudonymize person-identifying fields).
- `merge` now writes a `merge-report.json` manifest alongside the merged feed.
- The GitHub Action exposes `error-count`, `warning-count`, and `info-count`
  outputs and accepts an `enable` input.
- New opt-in rules: TODS-I501 / TODS-I502 (coverage) and TODS-I601 (advisory).
- Public Python API: `from tods_validate import validate_feed`.
- Input-safety hardening of zip ingestion (zip-bomb and path-traversal
  defenses, size limits) and a `SECURITY.md`.
- `scripts/benchmark.py` for throughput measurement on large synthetic feeds.

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
