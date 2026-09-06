# tods-validate

A validator for [Transit Operational Data Standard (TODS)](https://tods-transit.org/)
feeds, with a CLI and a GitHub Action.

Status: Beta

TODS is an open standard for describing scheduled transit operations: crew
runs, deadheads, vehicle assignments, and other non-public service that GTFS
does not cover. It works as an overlay on an agency's GTFS feed. The standard
was originally published by Cal-ITP as the Operational Data Standard (ODS)
and is now maintained with MobilityData under its current name. This
validator checks feeds against the current spec, TODS v2.1.0.

`tods-validate` reads a TODS package, checks it against the spec, and reports
findings in language a scheduler can act on. Each finding says what is wrong,
where, and what good looks like, and cites the spec section it comes from.

To try the validator without installing anything, use the
[browser playground](https://chelseakr.github.io/tods-validate/). Validation
runs locally in your browser; feed files are not uploaded.

## Choose a starting point

- **Try it:** open the
  [browser playground](https://chelseakr.github.io/tods-validate/) with a
  synthetic or approved feed.
- **Adopt it:** install the CLI below, use the container image, or add the
  [GitHub Action](#github-action) to a feed repository.
- **Contribute:** test a workflow, improve a finding, or add a spec-cited rule
  with passing and failing fixtures. Start with a
  [bounded open issue](https://github.com/ChelseaKR/tods-validate/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)
  and [CONTRIBUTING.md](CONTRIBUTING.md).

## Install

Requires Python 3.12 or newer.

```sh
pipx install tods-validate
```

or `pip install tods-validate` into an environment of your choice. For CI
environments without Python, a container image is published on releases:

```sh
docker run --rm -v "$PWD/feed:/feed:ro" ghcr.io/chelseakr/tods-validate /feed/tods --gtfs /feed/gtfs
```

There is also a [pre-commit](https://pre-commit.com) hook; see
[.pre-commit-hooks.yaml](.pre-commit-hooks.yaml) for usage.

## Usage

Point it at the directory or .zip file containing your TODS files. If your
GTFS feed lives in a separate file, pass it with `--gtfs` so trip, stop,
service, and block references can be checked:

```sh
tods-validate exports/tods/ --gtfs exports/gtfs.zip
```

When the TODS files sit next to the GTFS files in one package, the GTFS files
are picked up automatically — but only the files TODS IDs actually resolve
against (`trips.txt`, `stops.txt`, `stop_times.txt`, `routes.txt`,
`calendar.txt`, `calendar_dates.txt`). A package holding none of those is not
treated as its own companion feed, and a check that reads a file the companion
does not have is reported as skipped, never as a rule that ran clean. A stray
`agency.txt` cannot answer whether a `trip_id` exists, so it is not allowed to
look like it did. A complete sample feed ships in this repo, so you can try it
right after installing:

```console
$ tods-validate examples/sample-feed
tods-validate: examples/sample-feed (TODS v2.1.0)

No problems found.
Rule-set coverage: 41 of 44 checks ran. Checks skipped: 3 opt-in rule not enabled (use --enable).
  Not run, opt-in rule not enabled (use --enable) (3 INFO): TODS-I501, TODS-I502, TODS-I601
$ echo $?
0
```

A clean report always says what it covered; see
[Rule-set coverage](#rule-set-coverage).

On a feed with problems, each finding names the file, row, field, and what good
looks like:

```text
2 errors:
  ERROR TODS-E203 [run_events.txt, row 4, field 'end_time']
    run_events.txt row 4: end_time is '9:45', which is not a valid time. Use HH:MM:SS, e.g. '09:45:00' or '25:10:00' for 1:10 AM the next service day.
  ERROR TODS-E307 [run_events.txt, row 4, field 'trip_id']
    run_events.txt row 4: trip_id 'WKDY-1002' does not exist in the companion GTFS trips.txt (after applying trips_supplement.txt). Run events that represent work on a trip must reference a scheduled trip.
    Fix: Correct the trip_id, or add the trip via trips_supplement.txt if it is non-revenue service.

Summary: 2 error(s), 0 warning(s), 0 info.
```

The exit code is 0 when no errors are found, 1 when there are errors, and 2
when the package cannot be read at all. Warnings do not fail the run unless
you pass `--fail-on warning`.

## Rule-set coverage

Not every check applies to every run. A feed validated without a companion
GTFS feed cannot resolve a `trip_id`, so the 16 rules that read GTFS files do
not run; opt-in rules stay off until `--enable` turns them on; `--ignore`
withholds a rule's findings; `--spec-version` narrows the catalog.

Every report says which of those happened, and names the rules:

```console
$ tods-validate validate exports/tods
tods-validate: exports/tods (TODS v2.1.0)

No problems found.
Rule-set coverage: 27 of 44 checks ran. Checks skipped: 16 no companion GTFS feed was provided; 1 opt-in rule not enabled (use --enable).
  Not run, no companion GTFS feed was provided (9 ERROR, 5 WARNING, 2 INFO): TODS-I501, TODS-I502, TODS-E205, TODS-E307, TODS-E308, TODS-E309, TODS-E310, TODS-W315, TODS-W316, TODS-E311, TODS-E312, TODS-W313, TODS-E314, TODS-E405, TODS-W406, TODS-W407
  Not run, opt-in rule not enabled (use --enable) (1 INFO): TODS-I601
```

A run that skipped nothing says so, rather than staying silent: `Rule-set
coverage: Every applicable check ran (44 of 44).` Silence would be ambiguous,
so there is none.

**A skipped check does not change the exit code.** A partial run still exits
0, because that is what every release since 0.1.0 has done and pipelines gate
on it. Pass `--require-complete-run` to exit 1 instead when a check could not
run because an input was missing, such as a companion GTFS feed that was not
given. Skips you asked for (`--ignore`, opt-in rules left off, `--spec-version`
scoping) do not fail that gate; they are still disclosed.

Other output formats:

- `--format json` prints a stable JSON document for tooling. Its `coverage`
  block carries the same manifest, per rule, in machine form.
- `--format markdown` prints a report suitable for pasting into an issue
  (`--stamp` adds a provenance footer for a citable compliance artifact).
- `--format github` prints GitHub Actions workflow annotations. Each reason a
  check did not run becomes its own `::notice` annotation, so the disclosure
  appears in the pull request and not just in the log.
- `--format sarif` prints SARIF for GitHub code-scanning and security
  dashboards; the manifest rides under `invocations`.
- `--format html` prints a standalone, shareable report. Add `--timeline` to
  include a visual time rail and equivalent event table for each run.

On large feeds, `--max-findings N` caps how many findings are listed (the
summary is unaffected) and `--quiet` prints only the summary. Text and Markdown
reports group findings by rule and add a root-cause hint when one rule clusters.

New developers can also call the validator in-process; see
[docs/api.md](docs/api.md). Not a programmer? Start with
[docs/getting-started.md](docs/getting-started.md), or use the
[browser playground](https://chelseakr.github.io/tods-validate/).

## Fixing common problems

Some findings have a mechanical fix. Pass `--suggest` to list it after the
report, marked `auto` (safe and meaning-preserving) or `review` (derivable, but
worth a look because only you know the intent):

```console
$ tods-validate validate exports/tods --suggest
...
Suggestions (1 auto, 1 to review):
  [review] run_events.txt, row 4, field 'end_time': Write the time as HH:MM:SS: '9:45' -> '09:45:00'
  [auto] run_events.txt, row 2, field 'run_id': Trim the surrounding spaces so the value matches exactly: '10000 ' -> '10000'
Apply the auto fixes with: tods-validate fix PATH -o OUTPUT
```

A suggestion is only offered when its proposed value is one the validator would
accept and is reachable by adding leading zeros, a zero seconds field, or
removing date separators, so it never changes what a value means. `--suggest`
adds a prose block to text and Markdown output, and adds a structured
`suggestions` array to JSON output. The same suggestions are available from the
Python API as `tods_validate.suggest_fixes`.

The `auto` suggestions are the ones `tods-validate fix` applies across a whole
package without a human in the loop:

```sh
tods-validate fix exports/tods -o exports/tods-fixed
```

It trims whitespace padding (TODS-W206), drops entirely-blank rows, and drops
rows byte-identical to an earlier one (the TODS-W408 duplicate), re-encoding each
file as UTF-8 without a BOM. A row that shares a primary key but differs in any
value is a real conflict and is left for you. Without `-o` it is a dry run that
only reports what it would change. The `review` suggestions are never applied
automatically; correct those by hand.

To suppress findings your agency has decided to accept, pass
`--ignore TODS-W206` (repeatable), or put the policy in a
`tods-validate.toml` next to where you run the validator:

```toml
ignore = ["TODS-W206", "TODS-I108"]
fail-on = "warning"
```

Command-line flags win over the file. A config file in another location can
be passed with `--config path/to/file.toml`. A config may also `extends =
"../base.toml"` to inherit a shared house policy, and `profile = "strict"`
(or `lenient`) applies a named preset that other settings can still override.
A third preset, `ingest-ready`, is for a downstream CAD/AVL system deciding
whether to import a feed at all: it is at least as strict as `strict` (fails
on warnings, enables `coverage` and `advisory`) and adds no ignores, so it
doubles as a go/no-go gate rather than an authoring-time policy. Today it
resolves to exactly the same settings as `strict`; it is a separate name
because the two answer different questions, and a later change to one should
not silently move the other.

Some checks are off by default because they surface judgement calls rather than
spec violations. Turn them on with `--enable coverage` (which GTFS trips have no
run event; which blocks have no vehicle) or `--enable advisory` (e.g. long runs
with no break), or by rule ID. See [docs/rules.md](docs/rules.md).

References into GTFS are resolved after applying the supplement files, so a
trip added by `trips_supplement.txt` is a valid target for
`run_events.trip_id`, and a stop deleted by `stops_supplement.txt` is not.

## Validating against an older spec version

TODS changed shape substantially between v1.0.0 (2022) and the current
v2.1.0: file names were added and removed, and `run_events.txt` itself has
different, incompatible fields in each version. `tods-validate` defaults to
v2.1.0; pass `--spec-version 1.0.0` to validate a feed against the older
spec text instead:

```sh
tods-validate exports/tods/ --spec-version 1.0.0
```

Structure and field-value rules (required columns, required values, enum
values, value formats, duplicate primary keys) run against whichever
version's file/field inventory you asked for. Reference and semantic rules,
and the opt-in coverage/advisory categories, assume v2.1.0-only mechanisms
(the Supplement-file GTFS overlay; `vehicle_assignments.txt`) and are
skipped under `--spec-version 1.0.0`, disclosed in the report the same way
`--enable`-gated rules are. See [docs/spec-versions.md](docs/spec-versions.md)
for the full file/field inventory, spec citations, and exactly what does and
does not run under each version.

## Merging supplements into GTFS

The spec says that GTFS plus the supplement files should form a valid GTFS
dataset (the "TODS-Supplemented GTFS"). The `merge` subcommand materializes
that dataset so you can test the claim, or hand the operational feed to a
tool that only speaks GTFS:

```sh
tods-validate merge exports/tods/ --gtfs exports/gtfs.zip -o supplemented.zip
```

GTFS files without a supplement are copied through unchanged; supplemented
files get their rows deleted, updated, and added per the spec's evaluation
rules, and the command reports what changed per file. Validate the TODS
package first so the merge rests on clean inputs.

A CI job that checks the merged feed with MobilityData's gtfs-validator:

```yaml
- uses: ChelseaKR/tods-validate@v0.10.0
  with:
    path: feed/tods
    gtfs: feed/gtfs
- run: |
    pipx install tods-validate
    tods-validate merge feed/tods --gtfs feed/gtfs -o supplemented.zip
- run: |
    curl -fsSL -o gtfs-validator.jar \
      https://github.com/MobilityData/gtfs-validator/releases/download/v8.0.1/gtfs-validator-8.0.1-cli.jar
    echo "19293ddd9b6f954f216d4f12054bd8a3232921751c4484339e339764a91000e2  gtfs-validator.jar" | sha256sum -c -
    java -jar gtfs-validator.jar -i supplemented.zip -o validator-report
```

`tods-validate doctor feed/tods --gtfs feed/gtfs --gtfs-validator-jar gtfs-validator.jar`
runs that whole sequence — validate, merge, gtfs-validator on the merged
feed, stats — as one command with a single combined report. gtfs-validator is
never downloaded automatically: without java or a jar (`--gtfs-validator-jar`
or `GTFS_VALIDATOR_JAR`) already available, that stage is labeled SKIPPED
with the reason ("merged-feed GTFS validity NOT checked"), never silently
treated as a pass. A `report.json` gtfs-validator wrote but this version
cannot read is labeled FAILED, naming what it could not read, rather than
counted as zero notices; zero notices out of an unreadable document would
render exactly like a clean merged feed. The validate stage carries the same
`Rule-set coverage:` manifest a bare `tods-validate` run prints, in all three
formats, so a stage marked RAN also states how much of the rule set ran.
`doctor` exits non-zero on validate findings at `--fail-on` severity or a
gtfs-validator stage that actually failed to run, not on one that was honestly
skipped; `--require-complete-run` adds the same opt-in gate it provides on
`validate` and `batch`.

## Other subcommands

- `tods-validate stats feed/ --gtfs gtfs/` prints descriptive metrics (run
  events, distinct runs, revenue vs non-revenue minutes, employees, vehicles,
  and GTFS coverage) — facts about a feed, not a quality score. Give it
  several feeds (`tods-validate stats a/ b/ c/`) to get a cross-feed
  comparison table plus an aggregate totals/means/min/max summary
  (`--format json` for `{"feeds": [...], "aggregate": {...}}`); an unreadable
  path among several is reported in place rather than aborting the rest.
- `tods-validate diff old/ new/` validates two versions of a feed and reports
  which findings were fixed, newly introduced, or still present; it exits
  non-zero only on newly introduced errors, which is useful in review. An
  OLD finding absent from NEW is reported "fixed" only when its rule
  actually ran in NEW — one that stopped running (a dropped or newly
  unreadable companion GTFS feed, most often) lands in a separate "unknown"
  bucket instead, and any rule that ran in OLD but not NEW is named.
- `tods-validate drift old-gtfs/ new-gtfs/ --tods feed/` diagnoses the "your
  GTFS moved under your TODS" failure directly: given a TODS package and two
  versions of its companion GTFS feed, it reports exactly which referenced
  `trip_id`/`stop_id` values disappeared and which trips' `block_id` changed,
  with a conservative rename guess when exactly one new GTFS ID is an
  unambiguous close match (never applied automatically — a hint to review).
  Exits non-zero if anything broke, so it can gate a GTFS update before it
  reaches production.
- `tods-validate batch a/ b/ c/` validates several feeds and prints a roll-up
  table (`--format json` for tooling).
- `tods-validate batch a/ b/ --history .tods-history/` additionally appends
  one schema-versioned summary record per feed to
  `.tods-history/history.jsonl` (an append-only, artifact-shaped ledger —
  plain files in the repo, no hosted service). `tods-validate trend --history
  .tods-history/` then prints a text-first Markdown table, grouped by feed
  ("agency"), showing each run's counts and any per-rule regression since the
  same feed's previous run — "which agency regressed" answerable straight
  from CI history. **Privacy:** a history record stores only counts and rule
  IDs, never finding messages, since messages can carry stop, run, or
  employee/vehicle identifiers; see the docstring in `workspace.py`. Set
  `[workspace]` `history-dir` in `tods-validate.toml` to avoid repeating
  `--history` in every job (CLI flag still wins over the config value).
- `tods-validate anonymize feed/ -o feed-anon/` writes a copy with
  person-identifying fields (employee IDs, license plates, vehicle IDs)
  pseudonymized before sharing. This is pseudonymization, not guaranteed
  anonymity; see [SECURITY.md](SECURITY.md).

To fail CI only on findings introduced since a known-good run, capture a
baseline (`--format json > baseline.json`) and pass `--baseline baseline.json`.

## Editor integration

For a fast loop while editing a feed by hand:

- `tods-validate validate feed/ --watch` re-runs the validation whenever a file
  in the feed changes and reprints the report.
- `tods-validate lsp` runs a [Language Server Protocol](https://microsoft.github.io/language-server-protocol/)
  server over stdio. Point an LSP-capable editor at it for any TODS file and it
  re-validates the whole feed on open and save, underlining each finding at its
  row and (where one is named) its exact field. Hover a finding to see the rule's
  description and spec link; for the safely fixable ones it offers a quick fix
  ("Trim surrounding whitespace", "Delete duplicate row"). Install the server
  with the `lsp` extra:

  ```sh
  pip install 'tods-validate[lsp]'
  ```

  A minimal Neovim registration, as an example:

  ```lua
  vim.lsp.start({
    name = "tods-validate",
    cmd = { "tods-validate-lsp" },
    root_dir = vim.fn.getcwd(),
  })
  ```

  A thin VS Code client lives in [`editor/vscode/`](editor/vscode/). Install the
  Python server first with `pipx install 'tods-validate[lsp]'`; the extension
  finds `tods-validate-lsp` on `PATH` or accepts its full path in
  `tods-validate.serverPath`. CI builds a reviewable VSIX artifact, but the
  extension is not yet published to the Marketplace or Open VSX.

## GitHub Action

If your TODS export lives in a repository, this workflow validates it on
every pull request and annotates findings inline:

```yaml
name: Validate TODS feed
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ChelseaKR/tods-validate@v0.10.0
        with:
          path: feed/tods
          gtfs: feed/gtfs        # omit if GTFS files sit next to the TODS files
```

The action runs `--format github`, so the annotations it leaves on the pull
request include the checks that did not run and why (see
[Rule-set coverage](#rule-set-coverage)). Leaving `gtfs`
out is the case worth knowing about: the 16 checks that read GTFS files cannot
run, 9 of them ERROR-severity, and the job still passes. Add
`require-complete-run: "true"` to fail it instead.

The action installs `tods-validate` from a hash-verified
[`requirements-action.lock`](requirements-action.lock) (`pip install
--require-hashes`) followed by a `--no-deps` install of the checked-out
package itself, so no dependency is ever resolved unpinned from PyPI, and
`actions/setup-python`'s `cache: pip` warms the wheel cache across runs. An
alternative considered and dropped: run the published GHCR image pinned by
digest. That needs registry credentials and a digest bump on every release,
and only works on Linux runners, while the composite action above runs
anywhere `actions/setup-python` does.

## Rules

The full catalog of checks, with IDs, severities, and spec citations, is in
[docs/rules.md](docs/rules.md), or from the tool itself with
`tods-validate rules` (`--format json` for tooling). Rule IDs are stable: a
CI pipeline can safely filter or suppress specific IDs. The JSON report
format is described by [docs/report.schema.json](docs/report.schema.json).

For any one rule, `tods-validate explain RULE_ID` prints its full detail —
description, spec citation, and a worked before/after example — offline, with
`--format markdown` for pasting into an issue. It reads from the same rule
registry as `docs/rules.md` and editor hovers, so all three describe a rule
identically.

Ambiguities in the spec discovered while building the validator are tracked
in [docs/spec-questions.md](docs/spec-questions.md). What changed between
spec versions, and what `--spec-version` does and does not check, is in
[docs/spec-versions.md](docs/spec-versions.md).

## What this does not check

`tods-validate` validates the TODS files and their references into the
companion GTFS feed. It does not re-validate the GTFS feed itself, and it
does not check that the merged ("TODS-Supplemented") GTFS dataset is valid
GTFS. For those, run MobilityData's
[gtfs-validator](https://github.com/MobilityData/gtfs-validator), optionally
on the merged feed.

## Accessibility

Output is meant to be readable by everyone, including screen-reader and
non-color users.

- Severity is always carried by a word (`ERROR`, `WARNING`, `INFO`), never by
  color alone, so a finding's seriousness survives being piped to a file or read
  aloud.
- Terminal and machine outputs (text, JSON, Markdown, GitHub, SARIF) emit no
  ANSI color at all, so they are already plain under
  [`NO_COLOR`](https://no-color.org/); there is nothing to disable.
- The `--format html` report declares its language and a responsive viewport,
  uses `header`/`main` landmarks, gives the findings table a caption and
  column-scoped headers, and uses severity colors that clear WCAG AA contrast
  (4.5:1) on its background. Opt-in run timelines hide their decorative SVGs
  from assistive technology and repeat the full event sequence, times,
  locations, and findings in a table. They use a dashed outline and diamond
  marker in addition to color. The report ships as a single file with no
  external assets.

- The blocking WCAG 2.1 AA check (axe + HTML_CodeSniffer) runs against this
  repository's `web/index.html` and a generated HTML report on every pull
  request. The *deployed* playground is a separate artifact and is checked
  separately: after each deploy and weekly, the live page is compared against
  the page this repository publishes and audited with the same runners. A page
  that is accessible in the repository is not evidence about the page you open,
  so both are checked.

- The rule catalog published at `web/rules/` is audited by the same runners.
  It was not until 2026-08-27, and entering the gate it failed with 184 errors
  in one shared stylesheet; see the statement below for what and why.

[`docs/a11y/STATEMENT.md`](docs/a11y/STATEMENT.md) is the dated statement: the
WCAG 2.1 AA target, a surface-by-surface table of what has actually been
checked and by what, and the gaps automation cannot close. It deliberately
makes no conformance *claim*, because no assistive-technology evaluation has
been done.

If you hit an output that is hard to read with assistive technology, that is a
bug — please report it.

## Observability

Observability: Tier C. OpenTelemetry tracing is out of scope, because there is
no network surface to trace.

The tier also asks for an opt-in `--log-format json` flag, and that flag does
not exist. It is not an oversight that a release would quietly carry: the
package emits no log records at all (nothing under `src/` imports `logging`),
so a flag to choose their format would be a claim rather than a capability.
What is machine-readable here is the report, through `--format json`, `--format
sarif`, and the schema at [docs/report.schema.json](docs/report.schema.json).
That is a different thing from a log stream, and this section previously
conflated them. Tracked in
[docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#observability).

## Standards Conformance

`tods-validate` is developed against the fifteen portfolio standards below.
Applicability and current state:

| Standard | Applies? | State |
|---|---|---|
| CODE-QUALITY | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#code-quality) |
| Security & Supply-Chain | Applies (ships code, parses untrusted input) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#security-and-supply-chain) |
| CI-CD | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#ci-cd) |
| RELEASE-AND-VERSIONING | Applies (PyPI + GHCR + GitHub Releases + Action) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#release-and-versioning) |
| ACCESSIBILITY | Applies (scoped to the `--format html` report and the `web/` playground) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#accessibility) |
| OBSERVABILITY | Applies at Tier C (see `## Observability` above) | Applies — Tier C; tracing N/A (no network surface); the tier's `--log-format json` is a gap, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#observability) |
| INTERNATIONALIZATION | N/A — no user-facing strings requiring translation | N/A — see [docs/I18N.md](docs/I18N.md) |
| AI Development Measurement | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#ai-development-measurement) |
| AI Evaluation | N/A — no LLM/AI runtime | N/A — no LLM SDK or generative/agentic component anywhere in `src/` or `scripts/`; deterministic rule engine only |
| Data Governance | Applies (validates user-supplied transit data) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#data-governance) |
| DOCUMENTATION | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#documentation) |
| Incident Response | Applies (published CLI, Action, packages, and containers) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#incident-response) |
| Performance | Applies (CLI hot path and shipped HTML playground/report) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#performance) |
| QUALITY-AND-METRICS | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#quality-and-metrics) |
| Responsible-Tech Framework | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#responsible-tech) |

Gaps are tracked in [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md), a
dated ledger of open items per standard (this substitutes for individual
GitHub issues for now — converting a row to a real issue is a `gh issue
create` away; see that file's header).

## Development

```sh
git clone https://github.com/ChelseaKR/tods-validate
cd tods-validate
python -m venv .venv && . .venv/bin/activate
pip install -e . --group dev
pytest
```

Lint and type-check with `ruff check src tests scripts` and `mypy`. The rule
catalog is generated: after adding or changing a rule, run
`python scripts/generate_rules_doc.py` and commit the result; CI fails if it
drifts. To add a check, see [docs/authoring-rules.md](docs/authoring-rules.md),
which covers severity choice, ID allocation, message style, and the
fixture/conformance contract.

## License

Apache-2.0, matching the TODS specification repository.

## Support

This is independent, unpaid work. If it has been useful to you, you can
<a href='https://ko-fi.com/T6T6GMYTU' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi6.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
