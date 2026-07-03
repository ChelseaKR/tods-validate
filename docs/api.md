# Python API

For callers who want to validate a feed in-process rather than shelling out to
the CLI — for example, a TODS exporter's test suite — `tods-validate` exposes a
small, stable API.

```python
from tods_validate import validate_feed

result = validate_feed("exports/tods", gtfs="exports/gtfs.zip")

if not result.ok:                       # ok is True when there are no errors
    for finding in result.errors:
        print(finding.rule_id, finding.location(), finding.message)

print(result.error_count, "errors;", len(result.warnings), "warnings")
```

## `validate_feed(path, gtfs=None, *, enable=(), encoding=None)`

- `path`: the TODS package (directory or `.zip`).
- `gtfs`: companion GTFS feed to resolve references against. Omit when the GTFS
  files sit alongside the TODS files.
- `enable`: opt-in rules to turn on, by rule ID or category (`"coverage"`,
  `"advisory"`, `"experimental"`).
- `encoding`: override UTF-8 decoding for non-conforming exports.

Returns a `ValidationResult`. Raises
`tods_validate.loader.PackageNotFoundError` when the package cannot be read at
all.

## `ValidationResult`

| Member | Meaning |
|--------|---------|
| `source` | The path that was validated. |
| `findings` | All findings, ordered by file, then row, then rule ID. |
| `errors` / `warnings` / `infos` | Findings filtered by severity. |
| `error_count` | Number of errors. |
| `counts` | `Counter[Severity]` of all findings. |
| `ok` | `True` when there are no errors (warnings and info do not count). |

## `Finding`

A frozen dataclass: `rule_id`, `severity`, `message`, `file`, `row`, `field`,
`suggestion`. Helpers: `location()` (human string) and `pointer()` (a stable
`file.txt#L4/field` identifier). `to_dict()` matches
[docs/report.schema.json](report.schema.json).

## `suggest_fixes(path, gtfs=None, *, enable=(), encoding=None)`

Validates the feed and returns a `list[Suggestion]`: one entry per finding the
validator knows how to fix mechanically. Arguments mirror `validate_feed`.

```python
from tods_validate import suggest_fixes

for s in suggest_fixes("exports/tods"):
    if s.kind == "auto":                # safe; `tods-validate fix` applies it
        print(s.location(), s.current, "->", s.proposed)
    else:                               # "review": derivable, confirm by hand
        print("review:", s.location(), s.description)
```

A `Suggestion` is a frozen dataclass: `rule_id`, `kind` (`"auto"` or `"review"`),
`description`, `file`, `row`, `field`, `current`, `proposed`. `current` and
`proposed` are the before and after of a value change, or both `None` for a
structural fix such as deleting a duplicate row. Helpers: `location()` and
`to_dict()`. Suggestions never change the feed; applying them is up to the
caller.

## Test helpers

`tods_validate.testing` packages `validate_feed` as two pytest-friendly
assertions, for exporter teams who want a CI gate against the same checks the
CLI runs. They are kept out of the top-level namespace so importing the library
never pulls in test-only code; import them from `tods_validate.testing`.

### `assert_feed_valid(path, gtfs=None, *, enable=(), encoding=None, fail_on="error", ignore=())`

Asserts the feed has no findings at or above `fail_on` (`"error"` by default,
`"warning"` to gate on warnings; a `Severity` is also accepted). `ignore` is a
set of rule IDs to accept. Raises `AssertionError` carrying the rendered report;
returns the `ValidationResult` on success.

### `assert_feed_produces(path, expected, gtfs=None, *, enable=(), encoding=None, exactly=False)`

Asserts that validating `path` produces the `expected` rule ID(s) — a single ID
or an iterable. A subset check by default; pass `exactly=True` to require the
produced set to match with nothing extra. This is the helper for
regression-testing that a known-bad input keeps tripping the right rule.

```python
from tods_validate.testing import assert_feed_valid, assert_feed_produces

assert_feed_valid("exports/tods", gtfs="exports/gtfs")          # clean, or raises
assert_feed_produces("fixtures/bad-trip", "TODS-E307")          # still caught
```

## Reading feed data directly

For callers who want the parsed feed data itself rather than validation
findings — a report generator, a notebook, a data pipeline — see
[docs/read-api.md](read-api.md) for the curated `tods_validate.read`
namespace (`load_package`, `build_companion`, `to_rows`, and friends).

## Stability

These shapes follow the project's semantic-versioning promise: fields are only
added within a major version, never removed or renamed. Rule IDs are likewise
stable. The lower-level `tods_validate.runner.run` is available too, but
`validate_feed` is the supported entry point.
