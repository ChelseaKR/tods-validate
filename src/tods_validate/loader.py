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


def _parse_csv(name: str, data: bytes) -> FeedFile:
    feed = FeedFile(name=name)
    try:
        # utf-8-sig transparently strips a BOM if present.
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        feed.problems.append(
            LoadProblem(
                code="encoding",
                message=(
                    f"{name} is not valid UTF-8 (byte {exc.start}). TODS files must be "
                    "UTF-8 encoded, like GTFS. Re-export the file as UTF-8."
                ),
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
        values = {h: (raw[j] if j < len(raw) else "") for j, h in enumerate(header)}
        extra = tuple(raw[width:])
        feed.rows.append(Row(line=i, values=values, extra_cells=extra))

    return feed


def load_package(path: str | Path) -> Package:
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
                pkg.files[entry.name] = _parse_csv(entry.name, entry.read_bytes())
            else:
                pkg.unparsed.append(entry.name)
        return pkg

    if p.is_file() and zipfile.is_zipfile(p):
        pkg = Package(source=str(p))
        with zipfile.ZipFile(p) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                if info.is_dir():
                    continue
                name = info.filename
                base = Path(name).name
                if "/" in name.strip("/"):
                    # Files nested in subdirectories are outside the spec's
                    # flat-package shape; surface them rather than guessing.
                    pkg.unparsed.append(name)
                    continue
                if base.startswith("."):
                    continue
                if Path(base).suffix.lower() in (".txt", ".csv"):
                    pkg.files[base] = _parse_csv(base, zf.read(info))
                else:
                    pkg.unparsed.append(name)
        return pkg

    raise PackageNotFoundError(
        f"{p} is not a directory or a .zip file. Pass the folder or zip that "
        "contains the TODS .txt files."
    )
