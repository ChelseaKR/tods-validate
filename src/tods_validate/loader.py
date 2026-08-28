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


# Problem codes that stop parsing outright, so the file has no headers and no
# rows (see the early `return feed` for each in _parse_csv). "ragged" and
# "duplicate_header" are per-row/per-column defects on an otherwise-parsed
# file, so they leave FeedFile.readable True. This is the single source of
# truth for that split: TODS-E103 reports the file, and anything that reads
# another file's rows to resolve a reference (gtfs_companion.build_companion,
# TODS-E301/E303/W302) must treat a False here as absent, not present-but-
# empty -- see #125.
BLOCKING_PROBLEM_CODES = frozenset({"encoding", "empty", "csv_error"})

# Codes that leave the file parsed but not fully read: the header and rows are
# there, but some values did not survive the read. "ragged" means a row's
# values do not line up with the header, so any field of that row may hold a
# neighbouring column's value or nothing at all; "duplicate_header" means a
# column was declared twice and the second column's values were dropped. On a
# TODS file these are findings in their own right (TODS-E104, TODS-E105).
# On a file whose rows another check reads to resolve a reference, they are
# something else: the reader's view of that file is incomplete, and an ID it
# did not read is indistinguishable from an ID the feed does not contain. See
# ADR 0007 and FeedFile.fully_read.
DEGRADING_PROBLEM_CODES = frozenset({"ragged", "duplicate_header"})

# Every code _parse_csv can record is in exactly one of the two sets above.
# tests/test_loader.py asserts that against the codes the parser actually
# emits, so a code added later cannot quietly default to "harmless": it has to
# be classified, and until it is, the assertion fails.
PROBLEM_CODES = BLOCKING_PROBLEM_CODES | DEGRADING_PROBLEM_CODES


@dataclass
class LoadProblem:
    """A structural defect found while reading a file."""

    code: str  # "encoding" | "empty" | "ragged" | "duplicate_header" | "csv_error"
    message: str
    line: int | None = None
    # Structured context for the rules that surface this problem as a Finding,
    # so they need not regex their own generated message. ``column`` is set for
    # "duplicate_header"; ``expected``/``actual`` (declared vs. actual value
    # count) are set for "ragged".
    column: str | None = None
    expected: int | None = None
    actual: int | None = None


@dataclass
class FeedFile:
    name: str
    headers: tuple[str, ...] = ()
    rows: list[Row] = field(default_factory=list)
    problems: list[LoadProblem] = field(default_factory=list)

    def column(self, name: str) -> bool:
        return name in self.headers

    @property
    def readable(self) -> bool:
        """False if the file could not be parsed at all: see BLOCKING_PROBLEM_CODES."""
        return not any(p.code in BLOCKING_PROBLEM_CODES for p in self.problems)

    @property
    def fully_read(self) -> bool:
        """False if any value in this file did not survive the read.

        Strictly weaker than :attr:`readable`: a file can parse and still have
        lost values, which is the case ``readable`` alone cannot express. The
        test is "were any problems recorded", not "were any *known* degrading
        problems recorded", so a problem code introduced later counts as
        incomplete until someone decides otherwise, rather than the other way
        round.
        """
        return not self.problems


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


def _parse_csv(name: str, data: bytes, encoding: str | None = None) -> FeedFile:  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
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
                    # _parse_csv reads both the TODS package and (via
                    # gtfs_companion) a companion GTFS feed, so this must not
                    # claim either format by name -- see #125.
                    f"{name} is not valid {codec} (byte {exc.start}). Transit data files "
                    f"must be UTF-8 encoded.{hint}"
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
                    column=h,
                )
            )
        seen.add(h)

    width = len(header)
    # One shared instance per distinct cell value in this file. Transit data is
    # overwhelmingly repetitive in the columns that matter -- service_id,
    # route_id, event_type, dates, times -- so most cells are a value the file
    # has already used, and holding one string instead of thousands of equal
    # ones is where the memory goes. Measured on the 10,000-trip synthetic
    # benchmark: peak traced memory falls from 36.6x the input bytes to 30.5x,
    # with throughput unchanged (65.9k vs 65.0k rows/CPU-s, inside the noise).
    #
    # The trade is real and bounded: on a file whose every cell is distinct the
    # pool shares nothing and costs its own entries, measured at 6% more peak
    # (10.9x to 11.5x). That is the shape of data this tool does not validate.
    #
    # A per-file dict, not sys.intern: interned strings live until the
    # interpreter exits, which in the long-running LSP server would turn every
    # feed a user opens into a permanent leak. This pool is dropped when the
    # file is parsed, and only the values the rows actually hold survive.
    pool: dict[str, str] = {}
    for i, raw in enumerate(raw_rows[1:], start=2):
        # Skip genuinely empty lines (a bare newline). An all-blank ",,," data
        # row is kept so TODS-E201 reports its missing required values instead
        # of the row being silently dropped.
        if raw == []:
            continue
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
                    expected=width,
                    actual=len(raw),
                )
            )
        # On a duplicate header, keep the first occurrence so the duplicate
        # column is genuinely ignored (as the TODS-E105 message states), rather
        # than silently letting a later duplicate column's value win.
        values: dict[str, str] = {}
        for j, h in enumerate(header):
            if h in values:
                continue
            cell = raw[j] if j < len(raw) else ""
            values[h] = pool.setdefault(cell, cell)
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


def load_package(path: str | Path, encoding: str | None = None) -> Package:  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
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
