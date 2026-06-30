"""Apply safe, deterministic fixes to a TODS package.

The bar for a fix here is that its result is unambiguous and meaning-preserving,
so it can run unattended in a pipeline. Three transforms clear that bar:

- Trim leading and trailing whitespace from values (the TODS-W206 padding that
  stops IDs from matching their referents; the spec's own examples use it for
  column alignment).
- Drop rows that are entirely blank (a stray ``,,,`` past the header, which
  otherwise reports a wall of TODS-E201 missing-value errors).
- Drop rows that are byte-identical to an earlier row in the same file (pure
  redundancy, e.g. the TODS-W408 duplicate assignment). A row that shares a
  primary key but differs in any value is a real conflict and is left untouched.

Re-serializing also normalizes encoding to UTF-8 without a BOM. Anything whose
correct value a human must choose is left alone and reported by ``validate``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ._pkgio import serialize_feed, write_package
from .loader import load_package


@dataclass
class FixResult:
    source: str
    # filename -> number of values whose whitespace was trimmed
    trimmed: dict[str, int] = field(default_factory=dict)
    # filename -> number of entirely-blank rows dropped
    blank_rows_dropped: dict[str, int] = field(default_factory=dict)
    # filename -> number of exact-duplicate rows dropped
    duplicate_rows_dropped: dict[str, int] = field(default_factory=dict)
    # filenames written when an output path was given (empty on a dry run)
    written: list[str] = field(default_factory=list)

    @property
    def total_trimmed(self) -> int:
        return sum(self.trimmed.values())

    @property
    def total_blank_dropped(self) -> int:
        return sum(self.blank_rows_dropped.values())

    @property
    def total_duplicates_dropped(self) -> int:
        return sum(self.duplicate_rows_dropped.values())

    @property
    def changed_any(self) -> bool:
        return bool(self.trimmed or self.blank_rows_dropped or self.duplicate_rows_dropped)


def fix_package(
    path: str | Path, output: Path | None = None, encoding: str | None = None
) -> FixResult:
    """Apply the safe fixes across a package; write the result if ``output`` is set.

    With ``output`` as ``None`` this is a dry run: the package is analyzed and the
    counts reported, but nothing is written. Files are re-serialized to their
    declared header columns; a ragged row's extra cells (already a validation
    error) are dropped.
    """
    package = load_package(path, encoding=encoding)
    result = FixResult(source=package.source)
    entries: dict[str, bytes] = {}
    for name, feed in package.files.items():
        trimmed = 0
        blank_dropped = 0
        duplicate_dropped = 0
        rows: list[dict[str, str]] = []
        seen: set[tuple[str, ...]] = set()
        for row in feed.rows:
            values: dict[str, str] = {}
            for header in feed.headers:
                raw = row.values.get(header, "")
                stripped = raw.strip()
                if stripped != raw:
                    trimmed += 1
                values[header] = stripped
            if all(value == "" for value in values.values()):
                blank_dropped += 1
                continue
            signature = tuple(values[header] for header in feed.headers)
            if signature in seen:
                duplicate_dropped += 1
                continue
            seen.add(signature)
            rows.append(values)
        if trimmed:
            result.trimmed[name] = trimmed
        if blank_dropped:
            result.blank_rows_dropped[name] = blank_dropped
        if duplicate_dropped:
            result.duplicate_rows_dropped[name] = duplicate_dropped
        entries[name] = serialize_feed(feed.headers, rows)
    if output is not None:
        write_package(entries, output)
        result.written = sorted(entries)
    return result
