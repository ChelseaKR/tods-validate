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
| `problems` | `list[LoadProblem]`: structural defects found while reading (bad encoding, ragged rows, and so on). |
| `column(name)` | `True` when `name` is a declared header. |
| `readable` | `False` when the file could not be parsed at all. Check it before reading anything into an empty `rows`: nothing could be read is a different fact from the file was empty. |

## `LoadProblem`

One entry in `FeedFile.problems`, reached through that field rather than
exported from this namespace. A dataclass: `code` (`"encoding"`, `"empty"`,
`"ragged"`, `"duplicate_header"` or `"csv_error"`), `message`, `line`,
`column` (set for `"duplicate_header"`), and `expected` / `actual` (declared
and actual value counts, set for `"ragged"`). The first three codes are the
ones that make `readable` false. This page previously documented the
`problems` field without naming its element type, which left the field
unusable from the page alone.

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

---

Last verified: 2026-08-28, against tods-validate 0.10.0. Every member and
signature on this page was checked against `loader.py`, `gtfs_companion.py`
and `read.py`, and against `tods_validate.read.__all__`, which is the list the
v1 contract freezes. This page documents ten of the nineteen names in
`docs/v1-contract-candidate.json` and until now carried no currency stamp at
all, so `make docs-check` had nothing to fail on when it drifted.
Recheck cadence: every release, and whenever this page changes;
`make docs-check` fails if the page is edited without a fresh verification.

<!-- doc-currency: sha256=4fbafd6913ab -->
