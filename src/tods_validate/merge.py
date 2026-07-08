"""Materialize the "TODS-Supplemented GTFS" feed.

The spec says that after applying supplement files, the resulting dataset
"should form a valid GTFS dataset". This module produces that dataset so the
claim can be tested with MobilityData's gtfs-validator, and so consumers that
only speak GTFS can use the operational trips.

GTFS files without a supplement are copied through byte-for-byte. Files with
a supplement are re-serialized from the merged rows: the header becomes the
base header plus any new supplement columns (except ``TODS_delete``, which is
processing instruction, not data), base row order is preserved, and added
rows follow in supplement order. TODS-specific files (run_events.txt and
friends) are not part of the output; they describe operations, not the feed.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .loader import Package, PackageNotFoundError, load_package
from .schema import GTFS_PRIMARY_KEYS, TABLES
from .supplement import apply_supplement


@dataclass
class MergeStats:
    """Per-file accounting for the merge report."""

    updated: int = 0
    added: int = 0
    deleted: int = 0
    skipped: int = 0  # supplement rows with blank primary-key fields


@dataclass
class MergeResult:
    written: list[str] = field(default_factory=list)
    stats: dict[str, MergeStats] = field(default_factory=dict)


def _iter_raw_files(path: Path) -> list[tuple[str, bytes]]:
    """Top-level files of a directory or .zip, as (name, bytes)."""
    if path.is_dir():
        return [
            (entry.name, entry.read_bytes())
            for entry in sorted(path.iterdir())
            if entry.is_file() and not entry.name.startswith(".")
        ]
    if path.is_file() and zipfile.is_zipfile(path):
        out = []
        with zipfile.ZipFile(path) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                name = info.filename
                if info.is_dir() or "/" in name.strip("/") or Path(name).name.startswith("."):
                    continue
                out.append((Path(name).name, zf.read(info)))
        return out
    raise PackageNotFoundError(f"{path} is not a directory or a .zip file.")


def _merge_file(  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    base_name: str,
    gtfs: Package,
    tods: Package,
    stats: MergeStats,
) -> bytes | None:
    """Serialize the supplemented version of one GTFS file, or None if there
    is neither a base file nor a supplement."""
    base = gtfs.get(base_name)
    supplement = tods.get(base_name.removesuffix(".txt") + "_supplement.txt")
    if supplement is None and base is None:
        return None
    if supplement is None:
        return None  # untouched; caller copies the original bytes through

    pk = GTFS_PRIMARY_KEYS[base_name]
    base_headers = list(base.headers) if base is not None else []
    extra_headers = [
        h for h in supplement.headers if h and h != "TODS_delete" and h not in base_headers
    ]
    headers = base_headers + extra_headers
    if not headers:
        return None

    # Keyed rows, base first (preserving order), then supplement evaluation.
    # Delegates to the shared engine in supplement.py (also used by
    # gtfs_companion.merge_supplement) so the materialized merge can never
    # disagree with the validation view about which keys survive.
    result = apply_supplement(base, supplement, pk)
    stats.updated += result.updated
    stats.added += result.added
    stats.deleted += result.deleted
    stats.skipped += result.skipped

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for values in result.rows.values():
        writer.writerow([values.get(h, "") for h in headers])
    return buffer.getvalue().encode("utf-8")


def merge_feeds(tods_path: Path, gtfs_path: Path | None, output: Path) -> MergeResult:
    """Write the TODS-Supplemented GTFS feed to ``output`` (directory or .zip).

    ``gtfs_path`` may be None when the TODS package ships its GTFS files in
    the same directory or zip.
    """
    tods = load_package(tods_path)
    source_path = gtfs_path if gtfs_path is not None else tods_path
    gtfs = load_package(source_path) if gtfs_path is not None else tods

    entries: dict[str, bytes] = {
        name: data for name, data in _iter_raw_files(source_path) if name not in TABLES
    }

    result = MergeResult()
    supplemented = [t.gtfs_base for t in TABLES.values() if t.gtfs_base is not None]
    for base_name in supplemented:
        stats = MergeStats()
        merged = _merge_file(base_name, gtfs, tods, stats)
        if merged is not None:
            entries[base_name] = merged
            result.stats[base_name] = stats

    if not entries:
        raise PackageNotFoundError(
            f"nothing to merge: no GTFS files or supplement files found in {tods_path}."
        )

    if output.suffix.lower() == ".zip":
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(entries):
                zf.writestr(name, entries[name])
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, data in entries.items():
            (output / name).write_bytes(data)

    result.written = sorted(entries)
    return result
