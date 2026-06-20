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

## Stability

These shapes follow the project's semantic-versioning promise: fields are only
added within a major version, never removed or renamed. Rule IDs are likewise
stable. The lower-level `tods_validate.runner.run` is available too, but
`validate_feed` is the supported entry point.
