"""Pseudonymize person-identifying fields in a TODS package.

``employee_run_dates.txt`` carries ``employee_id``, and ``vehicles.txt`` can
carry ``license_plate`` — both are personal/operational data an agency may not
want to publish when sharing a feed for research or a bug report. This rewrites
those fields to stable pseudonyms so the operational structure is preserved
(the same employee stays the same pseudonym throughout) while the real
identifiers are removed.

Pseudonyms are a salted SHA-256 truncation. With a random salt (the default)
the mapping is irreversible and not comparable across runs; pass a fixed salt
to keep pseudonyms stable across exports. This is pseudonymization, not a
guarantee of anonymity: correlation with other data may still re-identify
individuals. Treat the output accordingly.
"""

from __future__ import annotations

import csv
import hashlib
import io
import secrets
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .loader import load_package

_VEHICLE_PREFIX = "veh"


@dataclass
class AnonymizeResult:
    written: list[str] = field(default_factory=list)
    replacements: dict[str, int] = field(default_factory=dict)


def _pseudonym(prefix: str, value: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{prefix}:{value}".encode()).hexdigest()[:12]
    return f"{prefix}_{digest}"


def anonymize_package(
    path: str | Path, output: Path, salt: str | None = None, encoding: str | None = None
) -> AnonymizeResult:
    """Write a pseudonymized copy of the package at ``path`` to ``output``."""
    salt = salt if salt is not None else secrets.token_hex(8)
    package = load_package(path, encoding=encoding)
    result = AnonymizeResult()

    # vehicle_id is pseudonymized consistently across vehicles.txt and
    # vehicle_assignments.txt so the assignment still resolves.
    field_prefix: dict[tuple[str, str], str] = {
        ("employee_run_dates.txt", "employee_id"): "emp",
        ("vehicles.txt", "license_plate"): "plate",
        ("vehicles.txt", "vehicle_id"): _VEHICLE_PREFIX,
        ("vehicle_assignments.txt", "vehicle_id"): _VEHICLE_PREFIX,
    }

    entries: dict[str, bytes] = {}
    for name, feed in package.files.items():
        sensitive = {
            col: prefix
            for (fname, col), prefix in field_prefix.items()
            if fname == name and col in feed.headers
        }
        if not sensitive or not feed.headers:
            # Re-serialize unchanged files too, so output is a complete package.
            entries[name] = _serialize(feed.headers, [dict(r.values) for r in feed.rows])
            continue
        counts = dict.fromkeys(sensitive, 0)
        rows = []
        for row in feed.rows:
            values = dict(row.values)
            for col, prefix in sensitive.items():
                if values.get(col, ""):
                    values[col] = _pseudonym(prefix, values[col], salt)
                    counts[col] += 1
            rows.append(values)
        for col, count in counts.items():
            result.replacements[f"{name}:{col}"] = count
        entries[name] = _serialize(feed.headers, rows)

    _write(entries, output)
    result.written = sorted(entries)
    return result


def _serialize(headers: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for values in rows:
        writer.writerow([values.get(h, "") for h in headers])
    return buffer.getvalue().encode("utf-8")


def _write(entries: dict[str, bytes], output: Path) -> None:
    if output.suffix.lower() == ".zip":
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(entries):
                zf.writestr(name, entries[name])
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, data in entries.items():
            (output / name).write_bytes(data)
