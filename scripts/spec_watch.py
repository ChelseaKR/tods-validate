#!/usr/bin/env python3
"""Diff the upstream TODS spec against `schema.py`'s hand transcription.

`schema.py` is transcribed by hand from the TODS specification
(`MobilityData/transit-operational-data-standard`, `docs/en/spec/index.md`).
Its own docstring says "If the spec and this file disagree, the spec wins" —
this script is the tripwire that catches disagreement before a human has to
notice it. It fetches (or reads) the spec markdown, parses its per-table
field definitions into `FieldSpec`-shaped records, and diffs them against
`tods_validate.schema.TABLES`, reporting added fields, removed fields, and
fields whose type/presence/enum values changed.

Scope: the spec spells out fields, one table per `### `filename.txt`` heading,
only for the TODS-specific files (today: `run_events.txt`,
`employee_run_dates.txt`, `vehicles.txt`, `vehicle_assignments.txt`).
Supplement files (`*_supplement.txt`) are documented as "fields match GTFS"
plus a handful of `TODS_`-prefixed additions listed in a separate flat table
keyed by filename, not a per-table field list — `schema.py` synthesizes their
`TableSpec.fields` from the GTFS field inventory, so a line-by-line diff
against a spec table isn't meaningful for them. This script only diffs
tables it actually finds a `### `filename.txt`` field table for; anything
else in `TABLES` is silently out of scope, and a spec table found for a name
not in `TABLES` is reported as a newly-introduced table (drift).

Usage:
    python scripts/spec_watch.py
    python scripts/spec_watch.py --spec-file tests/fixtures/spec_watch/in_sync.md
    python scripts/spec_watch.py --format markdown

Exit codes:
    0  in sync
    1  drift found (advisory signal for CI; never used to block a merge gate)
    2  the spec could not be fetched or parsed (advisory: comparison skipped)
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tods_validate.schema import TABLES, FieldSpec, FieldType, Presence

DEFAULT_SPEC_URL = (
    "https://raw.githubusercontent.com/MobilityData/"
    "transit-operational-data-standard/main/docs/en/spec/index.md"
)

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_ADVISORY = 2

_HEADING_RE = re.compile(r"^#{2,3}\s+(.*?)\s*$")
_TABLE_FILENAME_RE = re.compile(r"^[\w]+\.txt$")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEP_CELL_RE = re.compile(r"^:?-+:?$")

_HEADER_ALIASES = {
    "field name": "name",
    "name": "name",
    "type": "type",
    "presence": "presence",
    "required": "presence",
    "description": "description",
}


class SpecFetchError(RuntimeError):
    """The spec text could not be obtained (network, filesystem, ...)."""


class SpecParseError(RuntimeError):
    """The spec text was obtained but a field table could not be parsed."""


@dataclass(frozen=True)
class SpecTable:
    name: str
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class FieldDiff:
    kind: str  # "added" | "removed" | "changed"
    table: str
    field: str
    detail: str


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def fetch_spec_text(spec_file: str | None, spec_url: str) -> str:
    """Read the spec markdown from a local path, or fetch it over HTTP(S)."""
    if spec_file:
        try:
            return Path(spec_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise SpecFetchError(f"could not read spec file {spec_file!r}: {exc}") from exc
    try:
        with urllib.request.urlopen(spec_url, timeout=20) as resp:  # noqa: S310
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise SpecFetchError(f"could not fetch spec from {spec_url!r}: {exc}") from exc


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _strip_code(cell: str) -> str:
    """Pull the inline-code content out of a cell, e.g. "`vehicle_id`" -> "vehicle_id"."""
    cell = cell.strip()
    match = _CODE_SPAN_RE.search(cell)
    return match.group(1).strip() if match else cell


def _normalize_type(cell: str) -> FieldType:
    """Map a spec Type cell to a `FieldType`.

    The spec's Type column often carries extra prose, e.g. "ID referencing
    `calendar.service_id`" or "ID, primary key" — normalize by prefix so that
    prose doesn't defeat the match. references= is intentionally not
    diffed (see module docstring's diff scope).
    """
    low = re.sub(r"[`*]", "", cell).strip().lower()
    if low.startswith("non-negative integer"):
        return FieldType.NON_NEGATIVE_INTEGER
    if low.startswith("id"):
        return FieldType.ID
    if low.startswith("text"):
        return FieldType.TEXT
    if low.startswith("enum"):
        return FieldType.ENUM
    if low.startswith("time"):
        return FieldType.TIME
    if low.startswith("date"):
        return FieldType.DATE
    raise SpecParseError(f"unrecognized field type {cell!r}")


def _normalize_presence(cell: str) -> Presence:
    low = re.sub(r"[`*]", "", cell).strip().lower()
    if "conditional" in low:
        return Presence.CONDITIONAL
    if low.startswith("required"):
        return Presence.REQUIRED
    if low.startswith("optional"):
        return Presence.OPTIONAL
    raise SpecParseError(f"unrecognized presence {cell!r}")


def _extract_enum_values(description: str) -> tuple[str, ...]:
    """Recover enum values from a Description cell for an Enum-typed field.

    The spec writes enum members as inline code in the description (e.g.
    "`0` (or blank) - ...`1` - ..."), with "blank"/"(blank)" standing in for
    the empty string. This is a best-effort heuristic, not a strict grammar.
    """
    seen: list[str] = []
    for value in _CODE_SPAN_RE.findall(description):
        value = value.strip()
        if value not in seen:
            seen.append(value)
    if re.search(r"\bblank\b", description, re.IGNORECASE) and "" not in seen:
        seen.insert(0, "")
    return tuple(seen)


def _split_row(line: str) -> list[str] | None:
    match = _TABLE_ROW_RE.match(line)
    if not match:
        return None
    return [cell.strip() for cell in match.group(1).split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(_SEP_CELL_RE.match(cell.replace(" ", "")) for cell in cells)


def _map_header(cells: list[str]) -> dict[str, int] | None:
    idx: dict[str, int] = {}
    for i, cell in enumerate(cells):
        key = re.sub(r"\*+", "", cell).strip().lower()
        mapped = _HEADER_ALIASES.get(key)
        if mapped:
            idx[mapped] = i
    if {"name", "type", "presence"} <= idx.keys():
        return idx
    return None


def _cell(cells: list[str], idx: dict[str, int], key: str) -> str:
    pos = idx.get(key)
    if pos is None or pos >= len(cells):
        return ""
    return cells[pos]


def parse_spec_tables(text: str) -> dict[str, SpecTable]:
    """Parse `### `filename.txt`` sections' field tables into `SpecTable`s."""
    lines = text.splitlines()
    tables: dict[str, SpecTable] = {}
    current_name: str | None = None
    i = 0
    n = len(lines)
    while i < n:
        heading = _HEADING_RE.match(lines[i])
        if heading:
            candidate = _strip_code(heading.group(1))
            current_name = candidate if _TABLE_FILENAME_RE.fullmatch(candidate) else None
            i += 1
            continue

        if current_name is not None:
            header_cells = _split_row(lines[i])
            col_idx = _map_header(header_cells) if header_cells is not None else None
            if col_idx is not None and i + 1 < n:
                sep_cells = _split_row(lines[i + 1])
                if sep_cells is not None and _is_separator_row(sep_cells):
                    fields: list[FieldSpec] = []
                    j = i + 2
                    while j < n:
                        row_cells = _split_row(lines[j])
                        if row_cells is None:
                            break
                        name = _strip_code(_cell(row_cells, col_idx, "name"))
                        field_type = _normalize_type(_cell(row_cells, col_idx, "type"))
                        presence = _normalize_presence(_cell(row_cells, col_idx, "presence"))
                        description = _cell(row_cells, col_idx, "description")
                        enum_values = (
                            _extract_enum_values(description)
                            if field_type is FieldType.ENUM
                            else ()
                        )
                        fields.append(
                            FieldSpec(
                                name=name,
                                type=field_type,
                                presence=presence,
                                enum_values=enum_values,
                            )
                        )
                        j += 1
                    tables[current_name] = SpecTable(name=current_name, fields=tuple(fields))
                    current_name = None
                    i = j
                    continue
        i += 1
    return tables


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------


def diff_tables(spec_tables: dict[str, SpecTable]) -> list[FieldDiff]:
    diffs: list[FieldDiff] = []
    for table_name in sorted(spec_tables):
        spec_table = spec_tables[table_name]
        table_spec = TABLES.get(table_name)
        if table_spec is None:
            diffs.append(
                FieldDiff(
                    "added",
                    table_name,
                    "*",
                    "table appears in the spec but has no entry in schema.py TABLES",
                )
            )
            continue

        schema_fields = {f.name: f for f in table_spec.fields}
        spec_fields = {f.name: f for f in spec_table.fields}

        for name in sorted(set(spec_fields) - set(schema_fields)):
            f = spec_fields[name]
            diffs.append(
                FieldDiff(
                    "added",
                    table_name,
                    name,
                    f"in the spec ({f.type.value}, {f.presence.value}) but not in schema.py",
                )
            )
        for name in sorted(set(schema_fields) - set(spec_fields)):
            diffs.append(
                FieldDiff(
                    "removed",
                    table_name,
                    name,
                    "in schema.py but not in the spec",
                )
            )
        for name in sorted(set(schema_fields) & set(spec_fields)):
            s, p = schema_fields[name], spec_fields[name]
            changes = []
            if s.type != p.type:
                changes.append(f"type: schema.py={s.type.value!r} spec={p.type.value!r}")
            if s.presence != p.presence:
                changes.append(
                    f"presence: schema.py={s.presence.value!r} spec={p.presence.value!r}"
                )
            if s.enum_values != p.enum_values:
                changes.append(f"enum_values: schema.py={s.enum_values!r} spec={p.enum_values!r}")
            if changes:
                diffs.append(FieldDiff("changed", table_name, name, "; ".join(changes)))
    return diffs


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_diff(diffs: list[FieldDiff], fmt: str) -> str:
    if not diffs:
        return (
            "spec-watch: schema.py is in sync with the upstream spec.\n"
            if fmt == "text"
            else "# Spec drift check\n\nNo drift: `schema.py` matches the upstream spec.\n"
        )

    by_table: dict[str, list[FieldDiff]] = {}
    for d in diffs:
        by_table.setdefault(d.table, []).append(d)

    lines: list[str] = []
    if fmt == "markdown":
        lines.append("# Spec drift detected")
        lines.append("")
        lines.append(
            "`schema.py`'s hand-transcribed field tables differ from the upstream TODS "
            "spec. Per `schema.py`'s own docstring, *the spec wins* — review the fields "
            "below and update the transcription (or, if the parse is wrong, fix "
            "`scripts/spec_watch.py`)."
        )
        lines.append("")
        for table in sorted(by_table):
            lines.append(f"## `{table}`")
            lines.append("")
            for d in by_table[table]:
                lines.append(f"- **{d.kind}** `{d.field}`: {d.detail}")
            lines.append("")
    else:
        lines.append("Spec drift detected:")
        lines.append("")
        for table in sorted(by_table):
            lines.append(f"{table}:")
            for d in by_table[table]:
                lines.append(f"  - {d.kind} {d.field}: {d.detail}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diff the upstream TODS spec's field tables against schema.py."
    )
    parser.add_argument(
        "--spec-file",
        help="local path to the spec markdown (e.g. a forked copy, for tests/CI)",
    )
    parser.add_argument(
        "--spec-url",
        default=DEFAULT_SPEC_URL,
        help="raw spec markdown URL (default: upstream main)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "markdown"),
        default="text",
        help="output format (default: text)",
    )
    args = parser.parse_args(argv)

    try:
        text = fetch_spec_text(args.spec_file, args.spec_url)
    except SpecFetchError as exc:
        print(f"spec-watch: {exc}", file=sys.stderr)
        print(
            "spec-watch: could not compare against the upstream spec (advisory only).",
            file=sys.stderr,
        )
        return EXIT_ADVISORY

    try:
        spec_tables = parse_spec_tables(text)
    except SpecParseError as exc:
        print(f"spec-watch: could not parse the spec markdown: {exc}", file=sys.stderr)
        return EXIT_ADVISORY

    diffs = diff_tables(spec_tables)
    print(render_diff(diffs, args.format))
    return EXIT_DRIFT if diffs else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
