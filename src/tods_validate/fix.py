"""Apply safe, deterministic fixes to a TODS package.

The bar for a fix here is that its result is unambiguous and meaning-preserving,
so it can run unattended in a pipeline. Today that is exactly one transform:
trimming leading and trailing whitespace from values, the TODS-W206 padding that
stops IDs from matching their referents (the spec's own examples use it for
column alignment). Re-serializing also normalizes encoding to UTF-8 without a
BOM. Anything whose correct value a human must choose is left untouched and
reported by ``validate`` instead.
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
    # filenames written when an output path was given (empty on a dry run)
    written: list[str] = field(default_factory=list)

    @property
    def total_trimmed(self) -> int:
        return sum(self.trimmed.values())

    @property
    def changed_any(self) -> bool:
        return bool(self.trimmed)


def fix_package(
    path: str | Path, output: Path | None = None, encoding: str | None = None
) -> FixResult:
    """Trim whitespace padding across a package; write the result if ``output`` is set.

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
        rows: list[dict[str, str]] = []
        for row in feed.rows:
            values: dict[str, str] = {}
            for header in feed.headers:
                raw = row.values.get(header, "")
                stripped = raw.strip()
                if stripped != raw:
                    trimmed += 1
                values[header] = stripped
            rows.append(values)
        if trimmed:
            result.trimmed[name] = trimmed
        entries[name] = serialize_feed(feed.headers, rows)
    if output is not None:
        write_package(entries, output)
        result.written = sorted(entries)
    return result
