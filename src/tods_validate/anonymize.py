"""Pseudonymize person-identifying fields in a TODS package.

``employee_run_dates.txt`` carries ``employee_id``, and ``vehicles.txt`` can
carry ``license_plate`` and ``vehicle_label`` (typically the painted fleet
number, which correlates 1:1 with a pseudonymized ``vehicle_id`` for anyone
with a photo of the bus) — all personal/operational data an agency may not
want to publish when sharing a feed for research or a bug report. This
rewrites those fields to stable pseudonyms so the operational structure is
preserved (the same employee stays the same pseudonym throughout) while the
real identifiers are removed. Callers can pseudonymize additional extension
columns with ``--also FILE:FIELD`` (CLI) or the ``also`` parameter (library).

Pseudonyms are a salted SHA-256 truncation. With a random salt (the default)
the mapping is irreversible and not comparable across runs; pass a fixed salt
to keep pseudonyms stable across exports. This is pseudonymization, not a
guarantee of anonymity: correlation with other data may still re-identify
individuals. Treat the output accordingly.

Because pseudonymization only ever covers a known list of fields, every run
also reports what it did *not* touch: ``AnonymizeResult.carried_through``
lists every column, outside that list, that still holds non-enum data after
the rewrite (per the field types in ``schema.py``) — including numeric-looking
data such as a badge number or phone number, which is just as re-identifying
as text — the residual risk a caller may still need to strip or review by
hand.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from ._pkgio import reject_unreadable, serialize_feed, write_package
from .loader import load_package
from .schema import TABLES, FieldType

_VEHICLE_PREFIX = "veh"

# Field types whose values are structured/enumerated rather than free text, so
# they are not reported as a residual re-identification risk even when left
# unpseudonymized (e.g. a NON_NEGATIVE_INTEGER sequence number).
_STRUCTURED_TYPES = frozenset(
    {
        FieldType.ID,
        FieldType.ENUM,
        FieldType.NON_NEGATIVE_INTEGER,
        FieldType.DATE,
        FieldType.TIME,
    }
)


@dataclass
class AnonymizeResult:
    written: list[str] = field(default_factory=list)
    replacements: dict[str, int] = field(default_factory=dict)
    # (file, column) pairs that still carry non-enum data after the rewrite,
    # numeric or not: the residual re-identification risk this run did not close.
    # Sorted for deterministic output.
    carried_through: list[tuple[str, str]] = field(default_factory=list)


def _pseudonym(prefix: str, value: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{prefix}:{value}".encode()).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _derive_prefix(field_name: str) -> str:
    """A generic, deterministic pseudonym prefix for a caller-supplied field."""
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in field_name.strip().lower())
    return cleaned or "field"


def _has_data(values: list[str]) -> bool:
    """True if at least one value is non-empty.

    Purely-numeric columns are *not* excluded here: a numeric extension
    identifier (a badge number, a phone number, a numeric employee ID not in
    the default map) is exactly the kind of re-identifying data the
    carried-through table exists to disclose, so it must not be suppressed
    just because it looks like a number.
    """
    return any(v for v in values)


class AlreadyProtectedError(ValueError):
    """Raised when ``--also``/``also`` targets a field already pseudonymized
    by default, so the caller doesn't silently lose that protection."""


def anonymize_package(  # noqa: C901 - the pseudonymization pass tracks several output buckets
    path: str | Path,
    output: Path,
    salt: str | None = None,
    encoding: str | None = None,
    also: dict[str, str] | list[tuple[str, str]] | None = None,
) -> AnonymizeResult:
    """Write a pseudonymized copy of the package at ``path`` to ``output``.

    ``also`` adds caller-supplied FILE:FIELD pairs (a ``{file: field}`` dict,
    or a list of ``(file, field)`` tuples for repeats/multiple fields per
    file) to the fields pseudonymized by default. Each gets a generic prefix
    derived from the field name. Raises ``AlreadyProtectedError`` if a pair
    names a field already in the default protected-field map, rather than
    silently overwriting (and potentially weakening or de-correlating) that
    protection.
    """
    salt = salt if salt is not None else secrets.token_hex(8)
    package = load_package(path, encoding=encoding)
    # An unreadable file has no headers and no rows, so it would be written out
    # empty *and* omitted from the "carried through unprotected" table -- the
    # disclosure this command exists to make would be silently incomplete.
    reject_unreadable(package.files, "anonymize")
    result = AnonymizeResult()

    # vehicle_id is pseudonymized consistently across vehicles.txt and
    # vehicle_assignments.txt so the assignment still resolves.
    field_prefix: dict[tuple[str, str], str] = {
        ("employee_run_dates.txt", "employee_id"): "emp",
        ("vehicles.txt", "license_plate"): "plate",
        ("vehicles.txt", "vehicle_label"): "vlbl",
        ("vehicles.txt", "vehicle_id"): _VEHICLE_PREFIX,
        ("vehicle_assignments.txt", "vehicle_id"): _VEHICLE_PREFIX,
    }
    default_protected = frozenset(field_prefix)

    also_pairs: list[tuple[str, str]]
    if also is None:
        also_pairs = []
    elif isinstance(also, dict):
        also_pairs = list(also.items())
    else:
        also_pairs = list(also)
    for fname, col in also_pairs:
        if (fname, col) in default_protected:
            raise AlreadyProtectedError(
                f"{fname}:{col} is already pseudonymized by default; --also/also is "
                "for extension columns, not for overriding the default protected fields."
            )
        field_prefix[(fname, col)] = _derive_prefix(col)

    entries: dict[str, bytes] = {}
    for name, feed in package.files.items():
        sensitive = {
            col: prefix
            for (fname, col), prefix in field_prefix.items()
            if fname == name and col in feed.headers
        }

        table_spec = TABLES.get(name)
        typed_columns = {f.name: f.type for f in table_spec.fields} if table_spec else {}
        for col in feed.headers:
            if col in sensitive or typed_columns.get(col) in _STRUCTURED_TYPES:
                continue
            col_values = [row.values.get(col, "") for row in feed.rows]
            if _has_data(col_values):
                result.carried_through.append((name, col))

        if not sensitive or not feed.headers:
            # Re-serialize unchanged files too, so output is a complete package.
            entries[name] = serialize_feed(feed.headers, [dict(r.values) for r in feed.rows])
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
        entries[name] = serialize_feed(feed.headers, rows)

    write_package(entries, output)
    result.written = sorted(entries)
    result.carried_through.sort()
    return result
