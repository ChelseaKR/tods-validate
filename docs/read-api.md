# Read API

For callers who want the parsed feed data itself — a report generator, a
notebook, a data pipeline — rather than validation findings, `tods-validate`
exposes a small, stable read-only namespace: `tods_validate.read`.

```python
from tods_validate.read import load_package, build_companion, to_rows

tods = load_package("exports/tods")
gtfs = load_package("exports/gtfs")
companion = build_companion(gtfs, tods, source=tods.source)
rows = to_rows(tods.get("vehicles.txt"))
```

## `load_package(path, encoding=None)`

Loads all top-level files from a directory or `.zip` file and returns a
`Package`. Raises `PackageNotFoundError` when the path cannot be read at all.

## `Package`

| Member | Meaning |
|--------|---------|
| `source` | The path that was loaded. |
| `files` | `dict[str, FeedFile]`, keyed by file name (`"vehicles.txt"`, etc.). |
| `unparsed` | Names of entries present but not parsed (non-CSV, nested paths). |
| `get(name)` | `FeedFile` for `name`, or `None` if it was not present. |

## `FeedFile`

| Member | Meaning |
|--------|---------|
| `name` | The file name. |
| `headers` | Column names, in declaration order. |
| `rows` | `list[Row]`. |
| `problems` | Structural defects found while reading (bad encoding, ragged rows, and so on). |
| `column(name)` | `True` when `name` is a declared header. |

## `Row`

A dataclass: `line` (1-based line number, header counted as line 1),
`values` (`dict[str, str]`, header name to cell value), `extra_cells`
(values beyond the header width, if any).

## `to_rows(feed)`

Tabulates a `FeedFile` as `list[dict[str, str]]`, one dict per row — a
pandas-free view for callers who just want the values. Returns `[]` when
`feed` is `None` (the file was not present in the package).

## `to_dataframe(feed)`

Tabulates a `FeedFile` as a pandas `DataFrame`. Requires the `dataframe`
extra: `pip install tods-validate[dataframe]`. Raises `ImportError` with that
instruction if pandas is not installed.

## `CompanionGTFS` and `build_companion(gtfs, tods, source)`

`build_companion` merges the TODS supplement files onto the GTFS base files
(the spec's "TODS-Supplemented GTFS") and returns a `CompanionGTFS`: the
trip/stop/route/service lookups the rule engine itself resolves references
against. `gtfs` is the package holding the GTFS base files (may be the same
package as `tods` when a feed ships both together); supplements always come
from the TODS package.

## `merge_supplement(base, supplement, primary_key)`

The lower-level merge primitive `build_companion` is built on: computes
effective rows for one file, keyed by `primary_key`, applying the spec's
supplement evaluation order (delete, then overwrite, then add).

## Stability

These shapes follow the project's semantic-versioning promise: fields are
only added within a major version, never removed or renamed. The read
namespace is intentionally curated and kept separate from the top-level
package namespace (`from tods_validate import validate_feed`, documented in
[api.md](api.md)) so the stability commitment stays bounded to what is
re-exported here.
