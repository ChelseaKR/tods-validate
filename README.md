# tods-validate

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

or `pip install tods-validate` into an environment of your choice.

## Usage

Point it at the directory or .zip file containing your TODS files. If your
GTFS feed lives in a separate file, pass it with `--gtfs` so trip, stop,
service, and block references can be checked:

```sh
tods-validate exports/tods/ --gtfs exports/gtfs.zip
```

When the TODS files sit next to the GTFS files in one package, the GTFS files
are picked up automatically:

```console
$ tods-validate /tmp/demo-feed
tods-validate: /tmp/demo-feed (TODS v2.1.0)

2 errors:
  ERROR TODS-E203 [run_events.txt, row 4, field 'end_time']
    run_events.txt row 4: end_time is '9:45', which is not a valid time. Use HH:MM:SS, e.g. '09:45:00' or '25:10:00' for 1:10 AM the next service day.
  ERROR TODS-E307 [run_events.txt, row 4, field 'trip_id']
    run_events.txt row 4: trip_id 'WKDY-1002' does not exist in the companion GTFS trips.txt (after applying trips_supplement.txt). Run events that represent work on a trip must reference a scheduled trip.
    Fix: Correct the trip_id, or add the trip via trips_supplement.txt if it is non-revenue service.

Summary: 2 error(s), 0 warning(s), 0 info.
$ echo $?
1
```

The exit code is 0 when no errors are found, 1 when there are errors, and 2
when the package cannot be read at all. Warnings do not fail the run unless
you pass `--fail-on warning`.

Other output formats:

- `--format json` prints a stable JSON document for tooling.
- `--format markdown` prints a report suitable for pasting into an issue.
- `--format github` prints GitHub Actions workflow annotations.

To suppress findings your agency has decided to accept, pass
`--ignore TODS-W206` (repeatable), or put the policy in a
`tods-validate.toml` next to where you run the validator:

```toml
ignore = ["TODS-W206", "TODS-I108"]
fail-on = "warning"
```

Command-line flags win over the file. A config file in another location can
be passed with `--config path/to/file.toml`.

References into GTFS are resolved after applying the supplement files, so a
trip added by `trips_supplement.txt` is a valid target for
`run_events.trip_id`, and a stop deleted by `stops_supplement.txt` is not.

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
      - uses: ChelseaKR/tods-validate@v0
        with:
          path: feed/tods
          gtfs: feed/gtfs        # omit if GTFS files sit next to the TODS files
```

## Rules

The full catalog of checks, with IDs, severities, and spec citations, is in
[docs/rules.md](docs/rules.md). Rule IDs are stable: a CI pipeline can safely
filter or suppress specific IDs.

Ambiguities in the spec discovered while building the validator are tracked
in [docs/spec-questions.md](docs/spec-questions.md).

## What this does not check

`tods-validate` validates the TODS files and their references into the
companion GTFS feed. It does not re-validate the GTFS feed itself, and it
does not check that the merged ("TODS-Supplemented") GTFS dataset is valid
GTFS. For those, run MobilityData's
[gtfs-validator](https://github.com/MobilityData/gtfs-validator), optionally
on the merged feed.

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
drifts.

## License

Apache-2.0, matching the TODS specification repository.
