"""Read a TODS package from a directory or .zip file.

Loading is deliberately forgiving: structural problems (bad encoding, ragged
rows, duplicate headers) are recorded as load problems for the structure rules
to report, rather than raised, so one bad file does not hide findings in the
rest of the package.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


class PackageNotFoundError(Exception):
    """The path does not exist or is not a directory or .zip file."""


# Input-safety limits. TODS packages are untrusted input (a CI job may validate
# a contributor's feed), so guard against resource-exhaustion archives.
MAX_FILE_BYTES = 512 * 1024 * 1024  # 512 MiB per member, decompressed
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB total, decompressed
MAX_COMPRESSION_RATIO = 200  # decompressed/compressed; flags zip bombs


class UnsafeArchiveError(PackageNotFoundError):
    """A .zip member is unsafe to extract (zip bomb or path traversal)."""


@dataclass
class Row:
    """One data row of a CSV file.

    ``line`` is the 1-based line number in the file, counting the header as
    line 1, so the first data row is line 2. ``values`` maps header name to
    the raw cell value ('' for cells missing from a short row).
    """

    line: int
    values: dict[str, str]
    # Cells beyond the header width, kept so rules can report them.
    extra_cells: tuple[str, ...] = ()


@dataclass
class LoadProblem:
    """A structural defect found while reading a file."""

    code: str  # "encoding" | "empty" | "ragged" | "duplicate_header" | "csv_error"
    message: str
    line: int | None = None


@dataclass
class FeedFile:
    name: str
    headers: tuple[str, ...] = ()
    rows: list[Row] = field(default_factory=list)
    problems: list[LoadProblem] = field(default_factory=list)

    def column(self, name: str) -> bool:
        return name in self.headers


@dataclass
class Package:
    """All files found in the package, parsed where possible."""

    source: str
    files: dict[str, FeedFile] = field(default_factory=dict)
    # Names of entries that are present but were not parsed (non-CSV, nested
    # directories inside a zip, etc.).
    unparsed: list[str] = field(default_factory=list)

    def get(self, name: str) -> FeedFile | None:
        return self.files.get(name)


def _guess_encoding(data: bytes) -> str | None:
    """Best-effort name of a likely non-UTF-8 encoding, for a helpful message."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "UTF-16"
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "UTF-32"
    try:
        data.decode("latin-1")
    except UnicodeDecodeError:
        return None
    return "Latin-1 (ISO-8859-1) or Windows-1252"


def _parse_csv(name: str, data: bytes, encoding: str | None = None) -> FeedFile:
    feed = FeedFile(name=name)
    # utf-8-sig transparently strips a BOM if present; an explicit --encoding is
    # an escape hatch for exporters that do not emit UTF-8.
    codec = encoding or "utf-8-sig"
    try:
        text = data.decode(codec)
    except UnicodeDecodeError as exc:
        guess = _guess_encoding(data)
        hint = (
            f" It looks like {guess}; re-export as UTF-8, or pass --encoding to override."
            if guess
            else " Re-export the file as UTF-8, or pass --encoding to override."
        )
        feed.problems.append(
            LoadProblem(
                code="encoding",
                message=(
                    f"{name} is not valid {codec} (byte {exc.start}). TODS files must be "
                    f"UTF-8 encoded, like GTFS.{hint}"
                ),
            )
        )
        return feed
    except LookupError:
        feed.problems.append(
            LoadProblem(
                code="encoding",
                message=f"{name}: unknown --encoding {codec!r}.",
            )
        )
        return feed

    if text.strip() == "":
        feed.problems.append(LoadProblem(code="empty", message=f"{name} is empty (no header row)."))
        return feed

    try:
        reader = csv.reader(io.StringIO(text))
        raw_rows = list(reader)
    except csv.Error as exc:
        feed.problems.append(
            LoadProblem(code="csv_error", message=f"{name} could not be parsed as CSV: {exc}.")
        )
        return feed

    header = [h.strip() for h in raw_rows[0]]
    feed.headers = tuple(header)

    seen: set[str] = set()
    for h in header:
        if h in seen:
            feed.problems.append(
                LoadProblem(
                    code="duplicate_header",
                    message=(
                        f"{name} declares the column {h!r} more than once. Each column "
                        "may appear only once; values in the duplicate column are ignored."
                    ),
                    line=1,
                )
            )
        seen.add(h)

    width = len(header)
    for i, raw in enumerate(raw_rows[1:], start=2):
        if raw == [] or all(cell == "" for cell in raw):
            continue  # skip blank lines
        if len(raw) != width:
            feed.problems.append(
                LoadProblem(
                    code="ragged",
                    message=(
                        f"{name} row {i} has {len(raw)} values but the header declares "
                        f"{width} columns. Every row must have one value per column "
                        "(use empty values for blanks)."
                    ),
                    line=i,
                )
            )
        # On a duplicate header, keep the first occurrence so the duplicate
        # column is genuinely ignored (as the TODS-E105 message states), rather
        # than silently letting a later duplicate column's value win.
        values: dict[str, str] = {}
        for j, h in enumerate(header):
            if h in values:
                continue
            values[h] = raw[j] if j < len(raw) else ""
        extra = tuple(raw[width:])
        feed.rows.append(Row(line=i, values=values, extra_cells=extra))

    return feed


def _read_zip_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Read a zip member, refusing zip bombs and oversized files."""
    if info.file_size > MAX_FILE_BYTES:
        raise UnsafeArchiveError(
            f"{info.filename} declares {info.file_size} bytes uncompressed, over the "
            f"{MAX_FILE_BYTES}-byte limit; refusing to extract."
        )
    if info.compress_size > 0 and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
        raise UnsafeArchiveError(
            f"{info.filename} has a {info.file_size // max(info.compress_size, 1)}:1 "
            "compression ratio, which looks like a zip bomb; refusing to extract."
        )
    return zf.read(info)


def load_package(path: str | Path, encoding: str | None = None) -> Package:
    """Load all top-level files from a directory or .zip file."""
    p = Path(path)
    if p.is_dir():
        pkg = Package(source=str(p))
        for entry in sorted(p.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                pkg.unparsed.append(entry.name + "/")
                continue
            if entry.suffix.lower() in (".txt", ".csv"):
                pkg.files[entry.name] = _parse_csv(entry.name, entry.read_bytes(), encoding)
            else:
                pkg.unparsed.append(entry.name)
        return pkg

    if p.is_file() and zipfile.is_zipfile(p):
        pkg = Package(source=str(p))
        total = 0
        with zipfile.ZipFile(p) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                if info.is_dir():
                    continue
                name = info.filename
                # Reject path traversal and absolute paths outright; a flat
                # TODS package never needs them.
                if name.startswith("/") or ".." in Path(name).parts:
                    raise UnsafeArchiveError(
                        f"{name}: zip member escapes the package directory; refusing to read."
                    )
                base = Path(name).name
                if "/" in name.strip("/"):
                    # Files nested in subdirectories are outside the spec's
                    # flat-package shape; surface them rather than guessing.
                    pkg.unparsed.append(name)
                    continue
                if base.startswith("."):
                    continue
                if Path(base).suffix.lower() in (".txt", ".csv"):
                    total += info.file_size
                    if total > MAX_TOTAL_BYTES:
                        raise UnsafeArchiveError(
                            f"{p}: package exceeds the {MAX_TOTAL_BYTES}-byte total "
                            "decompressed limit; refusing to read."
                        )
                    pkg.files[base] = _parse_csv(base, _read_zip_member(zf, info), encoding)
                else:
                    pkg.unparsed.append(name)
        return pkg

    if p.exists():
        raise PackageNotFoundError(
            f"{p} exists but is not a directory or a .zip file. Pass the folder or "
            ".zip that contains the TODS .txt files (run_events.txt, vehicles.txt, "
            "the *_supplement.txt files, and so on)."
        )
    raise PackageNotFoundError(
        f"{p} does not exist. Looked for a directory or a .zip file at that path; "
        f"check the path is relative to the current directory ({Path.cwd()})."
    )
