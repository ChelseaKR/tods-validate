"""Write a (possibly transformed) TODS package back out as CSV files.

Shared by the ``anonymize`` and ``fix`` commands. Each file is re-serialized
from its loaded header and row values, so the output is a complete, normalized
package (UTF-8, ``\\n`` line endings, no BOM).
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, types only
    from .loader import FeedFile

# Loader problem codes that mean the file's contents never reached memory: the
# decode or the CSV parse failed, so the loader holds no headers and no rows for
# it. Every other problem code ("empty", "ragged", "duplicate_header") still
# yields real parsed content.
UNREADABLE_CODES = frozenset({"encoding", "csv_error"})


class UnreadableFileError(Exception):
    """A package cannot be rewritten because a file in it could not be read.

    ``serialize_feed`` builds its output from the loader's headers and rows, and
    a file that failed to decode or parse has neither. Re-serializing it yields
    a lone newline, so writing the package would replace the user's data with an
    empty file while every counter stayed at zero and the command reported that
    it had changed nothing. Refusing to write is the only outcome that cannot
    destroy the input.
    """


def unreadable_files(files: Mapping[str, FeedFile]) -> list[str]:
    """Names of files the loader could not read, sorted; empty when all parsed."""
    return sorted(
        name
        for name, feed in files.items()
        if any(problem.code in UNREADABLE_CODES for problem in feed.problems)
    )


def reject_unreadable(files: Mapping[str, FeedFile], command: str) -> None:
    """Raise :class:`UnreadableFileError` if any file could not be read."""
    unreadable = unreadable_files(files)
    if not unreadable:
        return
    names = ", ".join(unreadable)
    raise UnreadableFileError(
        f"{command} will not write this package: {names} could not be read, and rewriting "
        f"the package would replace {'them' if len(unreadable) > 1 else 'it'} with an empty "
        "file. Run `tods-validate validate` to see the read error (TODS-E103), fix the "
        "file's encoding or CSV syntax, then re-run. `--encoding` overrides the decoder if "
        "the file is deliberately in another encoding."
    )


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
