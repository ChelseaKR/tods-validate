"""Write a (possibly transformed) TODS package back out as CSV files.

Shared by the ``anonymize`` and ``fix`` commands. Each file is re-serialized
from its loaded header and row values, so the output is a complete, normalized
package (UTF-8, ``\\n`` line endings, no BOM).
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Sequence
from pathlib import Path


def serialize_feed(headers: Sequence[str], rows: list[dict[str, str]]) -> bytes:
    """Serialize one feed file from its header and per-row value dicts."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(headers))
    for values in rows:
        writer.writerow([values.get(h, "") for h in headers])
    return buffer.getvalue().encode("utf-8")


def write_package(entries: dict[str, bytes], output: Path) -> None:
    """Write ``{filename: bytes}`` to a .zip file or a directory."""
    if output.suffix.lower() == ".zip":
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(entries):
                zf.writestr(name, entries[name])
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, data in entries.items():
            (output / name).write_bytes(data)
