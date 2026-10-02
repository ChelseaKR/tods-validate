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


class OutputOverlapsInputError(Exception):
    """A package write was pointed at the package it was read from.

    ``anonymize`` and ``fix`` hold the whole input in memory and then write a
    transformed copy, so an output path that is the input (or lies inside an
    input directory) silently replaces the operator's feed. For ``anonymize``
    that loss cannot be undone: the default salt is random and single-use, so
    the original identifiers have no inverse. The tool reads a feed and writes
    nothing back to it (docs/data/README.md); this is what makes that true.
    """


def output_overlaps_input(source: str | Path, output: Path) -> bool:
    """True if writing to ``output`` would write over or into ``source``.

    That is: ``output`` is the input file or directory, or is inside the input
    directory. Paths are compared by file identity after resolving, so
    ``./feed``, ``feed/`` and a symlink to ``feed`` all count as the same
    package, as do two spellings that differ only in case on a
    case-insensitive filesystem. The output need not exist yet: its nearest
    existing ancestor is what decides "inside".
    """
    src = Path(source)
    if not src.exists():
        return False
    target = output.resolve()
    for candidate in (target, *target.parents):
        if candidate.exists() and candidate.samefile(src):
            return True
    return False


def reject_output_over_input(source: str | Path | None, output: Path, command: str) -> None:
    """Raise :class:`OutputOverlapsInputError` if ``output`` overlaps ``source``."""
    if source is None or not output_overlaps_input(source, output):
        return
    raise OutputOverlapsInputError(
        f"{command} will not write to {output}: it is the input package {source} or inside "
        "it, and writing there would replace the feed you read from. Choose an output path "
        "outside the input."
    )


def write_package(
    entries: dict[str, bytes],
    output: Path,
    *,
    source: str | Path | None,
    command: str = "tods-validate",
) -> None:
    """Write ``{filename: bytes}`` to a .zip file or a directory.

    ``source`` is the package the entries were read from, or ``None`` when they
    were built from scratch. It is keyword-only and required so that every
    writer has to say which input it must not overwrite: an ``output`` that is
    ``source`` or inside it raises :class:`OutputOverlapsInputError` before
    anything is written. ``command`` names the caller in that error.
    """
    reject_output_over_input(source, output, command)
    if output.suffix.lower() == ".zip":
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(entries):
                zf.writestr(name, entries[name])
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, data in entries.items():
            (output / name).write_bytes(data)
