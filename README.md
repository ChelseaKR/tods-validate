# tods-validate

Status: Beta

A validator for [Transit Operational Data Standard (TODS)](https://tods-transit.org/)
feeds, with a CLI and a GitHub Action.

TODS is an open standard for describing scheduled transit operations: crew
runs, deadheads, vehicle assignments, and other non-public service that GTFS
does not cover. It works as an overlay on an agency's GTFS feed. The standard
was originally published by Cal-ITP as the Operational Data Standard (ODS)
and is now maintained with MobilityData under its current name. This
validator checks feeds against the current spec, TODS v2.1.0.

`tods-validate` reads a TODS package, checks it against the spec, and reports
findings in language a scheduler can act on. Each finding says what is wrong,
where, and what good looks like, and cites the spec section it comes from.

## Install

Requires Python 3.11 or newer.

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
are picked up automatically. A complete sample feed ships in this repo, so you
can try it right after installing:

```console
$ tods-validate examples/sample-feed
tods-validate: examples/sample-feed (TODS v2.1.0)

No problems found.
$ echo $?
0
```

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

Other output formats:

- `--format json` prints a stable JSON document for tooling.
- `--format markdown` prints a report suitable for pasting into an issue
  (`--stamp` adds a provenance footer for a citable compliance artifact).
- `--format github` prints GitHub Actions workflow annotations.
- `--format sarif` prints SARIF for GitHub code-scanning and security
  dashboards.
- `--format html` prints a standalone, shareable report.

On large feeds, `--max-findings N` caps how many findings are listed (the
summary is unaffected) and `--quiet` prints only the summary. Text and Markdown
reports group findings by rule and add a root-cause hint when one rule clusters.

New developers can also call the validator in-process; see
[docs/api.md](docs/api.md). Not a programmer? Start with
[docs/getting-started.md](docs/getting-started.md).

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
affects text and Markdown output; the JSON report is left unchanged so it stays
a stable machine contract, and the same suggestions are available from the
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
doubles as a go/no-go gate rather than an authoring-time policy.

Some checks are off by default because they surface judgement calls rather than
spec violations. Turn them on with `--enable coverage` (which GTFS trips have no
run event; which blocks have no vehicle) or `--enable advisory` (e.g. long runs
with no break), or by rule ID. See [docs/rules.md](docs/rules.md).

References into GTFS are resolved after applying the supplement files, so a
trip added by `trips_supplement.txt` is a valid target for
`run_events.trip_id`, and a stop deleted by `stops_supplement.txt` is not.

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
- uses: ChelseaKR/tods-validate@v0.6.0
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
  non-zero only on newly introduced errors, which is useful in review.
- `tods-validate batch a/ b/ c/` validates several feeds and prints a roll-up
  table (`--format json` for tooling; `--format markdown --stamp` for a single
  stamped fleet/portfolio compliance report — one artifact covering every
  feed, with a pass/fail/error summary table, fleet totals, and a provenance
  footer).
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
      - uses: ChelseaKR/tods-validate@v0.6.0
        with:
          path: feed/tods
          gtfs: feed/gtfs        # omit if GTFS files sit next to the TODS files
```

## Rules

The full catalog of checks, with IDs, severities, and spec citations, is in
[docs/rules.md](docs/rules.md), or from the tool itself with
`tods-validate rules` (`--format json` for tooling). Rule IDs are stable: a
CI pipeline can safely filter or suppress specific IDs. The JSON report
format is described by [docs/report.schema.json](docs/report.schema.json).

Ambiguities in the spec discovered while building the validator are tracked
in [docs/spec-questions.md](docs/spec-questions.md).

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
  (4.5:1) on its background. It ships as a single file with no external assets.

If you hit an output that is hard to read with assistive technology, that is a
bug — please report it.

## Observability

Observability: Tier C — OTel tracing out-of-scope (no network surface). Opt-in
--log-format json only.

## Standards Conformance

`tods-validate` is developed against a shared set of engineering standards
(code quality, security & supply chain, CI/CD, release & versioning,
accessibility, observability, documentation, quality & metrics,
responsible-tech, internationalization, AI-evaluation). Applicability and
current state:

| Standard | Applies? | State |
|---|---|---|
| CODE-QUALITY | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#code-quality) |
| SECURITY-AND-SUPPLY-CHAIN | Applies (ships code, parses untrusted input) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#security-and-supply-chain) |
| CI-CD | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#ci-cd) |
| RELEASE-AND-VERSIONING | Applies (PyPI + GHCR + GitHub Releases + Action) | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#release-and-versioning) |
| ACCESSIBILITY | Applies, scoped to `--format html` report + `web/` playground | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#accessibility) |
| OBSERVABILITY | Applies at Tier C (see `## Observability` above) | Applies — Tier C, N/A tracing declared above |
| INTERNATIONALIZATION | N/A — no user-facing strings requiring translation | N/A — see [docs/I18N.md](docs/I18N.md) |
| AI-EVALUATION | N/A — no LLM/AI runtime | N/A — no LLM SDK or generative/agentic component anywhere in `src/` or `scripts/`; deterministic rule engine only |
| DOCUMENTATION | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#documentation) |
| QUALITY-AND-METRICS | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#quality-and-metrics) |
| RESPONSIBLE-TECH | Applies | Applies — gap tracked, see [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md#responsible-tech) |

Gaps are tracked in [docs/CONFORMANCE-GAPS.md](docs/CONFORMANCE-GAPS.md), a
dated ledger of open items per standard (this substitutes for individual
GitHub issues for now — converting a row to a real issue is a `gh issue
create` away; see that file's header).

## Development

```sh
git clone https://github.com/ChelseaKR/tods-validate
cd tods-validate
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
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
