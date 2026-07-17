"""Field-value rules within a single file (TODS-x2xx)."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterator

from ..findings import Finding, Severity
from ..loader import FeedFile
from ..run_events import parse_time as parse_time
from ..schema import (
    GTFS_REQUIRED_FIELDS,
    SPEC_URL,
    SPEC_VERSION,
    FieldSpec,
    FieldType,
    Presence,
    TableSpec,
    spec_link,
)
from . import ValidationContext, rule

# GTFS Time: H:MM:SS or HH:MM:SS; hours may exceed 24 for service past midnight
# and have no upper bound in the spec, so the hour field is not width-capped.
_DATE_RE = re.compile(r"^\d{8}$")

# parse_time itself lives in tods_validate.run_events (imported above) so that
# ValidationContext's derived-state parsing can use it without importing back
# into this package; re-imported here under its original name so existing
# `from .fields import parse_time` call sites are unaffected.


def _is_valid_date(value: str) -> bool:
    from ..gtfs_companion import parse_gtfs_date

    return _DATE_RE.match(value) is not None and parse_gtfs_date(value) is not None


# Spec Latitude/Longitude/Non-negative float are plain decimal degrees/numbers:
# an optional sign, digits, and a single decimal point. No exponent, underscore,
# whitespace, or the special float tokens inf/nan (which float() would accept).
_DECIMAL_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")


def _parse_decimal(value: str) -> float | None:
    if _DECIMAL_RE.match(value) is None:
        return None
    number = float(value)
    # A very long digit run parses to inf without raising; reject it too.
    return number if math.isfinite(number) else None


def _in_range(value: str, low: float, high: float) -> bool:
    number = _parse_decimal(value)
    return number is not None and low <= number <= high


def _is_non_negative(value: str) -> bool:
    number = _parse_decimal(value)
    return number is not None and number >= 0.0


def _tods_tables(context: ValidationContext) -> Iterator[tuple[TableSpec, FeedFile]]:
    for name, table in context.tables.items():
        feed = context.package.get(name)
        if feed is not None and feed.headers:
            yield table, feed


def _required_fields(table: TableSpec) -> tuple[FieldSpec, ...]:
    if table.kind == "supplement":
        names = set(table.primary_key or ())
        return tuple(f for f in table.fields if f.name in names)
    return tuple(f for f in table.fields if f.presence is Presence.REQUIRED)


def _is_added_supplement_row(
    context: ValidationContext, table: TableSpec, row_values: dict[str, str]
) -> bool:
    """Return whether a supplement row is known to add a GTFS row.

    A companion feed is required to distinguish an addition from an update.
    Without one, stay permissive rather than assuming every supplement row is
    an addition. Delete rows never need the added-row fields.
    """
    if (
        table.kind != "supplement"
        or table.gtfs_base is None
        or context.gtfs is None
        or row_values.get("TODS_delete", "") == "1"
    ):
        return False
    primary_key = table.primary_key or ()
    key = tuple(row_values.get(name, "") for name in primary_key)
    if not key or not all(key):
        return False
    return key not in context.gtfs.base_keys.get(table.gtfs_base, set())


@rule(
    id="TODS-E201",
    severity=Severity.ERROR,
    title="Required value is missing",
    description=(
        "A field the spec marks Required is empty. Supplement primary-key fields are "
        "always required; a row that adds a new GTFS entry must also provide every "
        "field GTFS marks Required for that file."
    ),
    spec_section=SPEC_URL,
)
def missing_required_value(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        for row in feed.rows:
            required = [f for f in _required_fields(table) if f.name in feed.headers]
            added_row = _is_added_supplement_row(context, table, row.values)
            if added_row and table.gtfs_base is not None:
                required_names = set(GTFS_REQUIRED_FIELDS[table.gtfs_base])
                required = [f for f in table.fields if f.name in required_names]
            for f in required:
                if row.values.get(f.name, "") == "":
                    added_detail = f" for an added {table.gtfs_base} row" if added_row else ""
                    yield Finding(
                        rule_id="TODS-E201",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name!r} is required"
                            f"{added_detail} but empty."
                        ),
                        suggestion=f"See {spec_link(table)}.",
                        data={"value": "", "field": f.name},
                    )


@rule(
    id="TODS-E202",
    severity=Severity.ERROR,
    title="Value is not an allowed option",
    description=(
        "An enum field has a value outside the options the spec allows "
        "(TODS_delete: blank or 1; start_mid_trip and end_mid_trip: blank, 0, 1, or 2)."
    ),
    spec_section=SPEC_URL,
)
def invalid_enum(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        enums = [f for f in table.fields if f.type is FieldType.ENUM and f.name in feed.headers]
        for row in feed.rows:
            for f in enums:
                value = row.values.get(f.name, "")
                if value == "":
                    # Blank on a Required enum is TODS-E201's concern; blank on an
                    # Optional enum is a legitimate empty value (its enum_values
                    # tuple already includes "" when the spec allows blank).
                    continue
                if value not in f.enum_values:
                    blank_allowed = "" in f.enum_values
                    allowed = ", ".join(repr(v) for v in f.enum_values if v) or "'1'"
                    allowed_values = ",".join(v for v in f.enum_values if v) or "1"
                    blank_clause = "blank or " if blank_allowed else ""
                    yield Finding(
                        rule_id="TODS-E202",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name} is {value!r}, "
                            f"but the only allowed values are {blank_clause}{allowed}."
                        ),
                        suggestion=f"See {spec_link(table)}.",
                        data={"value": value, "field": f.name, "allowed": allowed_values},
                    )


# Each entry maps a typed field to (is-value-valid predicate, message detail,
# expected-value label). Keeping it a table rather than an if/elif chain lets a
# new typed field be enforced by adding one row. isascii() guards the integer
# check because isdigit() alone accepts non-ASCII digits ("²", "１２３").
_FORMAT_CHECKS: dict[FieldType, tuple[Callable[[str], bool], str, str]] = {
    FieldType.TIME: (
        lambda v: parse_time(v) is not None,
        "which is not a valid time. Use HH:MM:SS, e.g. '09:45:00' "
        "or '25:10:00' for 1:10 AM the next service day.",
        "HH:MM:SS",
    ),
    FieldType.DATE: (
        _is_valid_date,
        "which is not a valid date. Use YYYYMMDD, e.g. '20260315'.",
        "YYYYMMDD",
    ),
    FieldType.NON_NEGATIVE_INTEGER: (
        lambda v: v.isascii() and v.isdigit(),
        "which is not a non-negative whole number.",
        "non-negative integer",
    ),
    FieldType.LATITUDE: (
        lambda v: _in_range(v, -90.0, 90.0),
        "which is not a valid latitude. Use a decimal degree between -90 and 90, e.g. '38.5449'.",
        "latitude -90..90",
    ),
    FieldType.LONGITUDE: (
        lambda v: _in_range(v, -180.0, 180.0),
        "which is not a valid longitude. Use a decimal degree "
        "between -180 and 180, e.g. '-121.7405'.",
        "longitude -180..180",
    ),
    FieldType.NON_NEGATIVE_FLOAT: (
        _is_non_negative,
        "which is not a non-negative decimal number, e.g. '1250.5'.",
        "non-negative decimal",
    ),
}


@rule(
    id="TODS-E203",
    severity=Severity.ERROR,
    title="Value has the wrong format",
    description=(
        "A value does not match its field type: times must be HH:MM:SS (hours may "
        "exceed 24 for service after midnight), dates must be YYYYMMDD, "
        "event_sequence must be a non-negative whole number, latitudes must be a "
        "decimal degree in -90..90, longitudes a decimal degree in -180..180, and "
        "shape_dist_traveled a non-negative decimal number."
    ),
    spec_section=SPEC_URL,
)
def invalid_format(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        typed = [f for f in table.fields if f.type in _FORMAT_CHECKS and f.name in feed.headers]
        for row in feed.rows:
            for f in typed:
                value = row.values.get(f.name, "")
                if value == "":
                    continue  # emptiness is TODS-E201's concern
                is_valid, detail, expected = _FORMAT_CHECKS[f.type]
                if is_valid(value):
                    continue
                yield Finding(
                    rule_id="TODS-E203",
                    severity=Severity.ERROR,
                    file=table.filename,
                    row=row.line,
                    field=f.name,
                    message=f"{table.filename} row {row.line}: {f.name} is {value!r}, {detail}",
                    data={"value": value, "field": f.name, "expected": expected},
                )


@rule(
    id="TODS-E204",
    severity=Severity.ERROR,
    title="Duplicate primary key",
    description=(
        "Two rows in a TODS-specific file share the same primary key "
        "(run_events: service_id + run_id + event_sequence; vehicles: vehicle_id; "
        "employee_run_dates: date + service_id + run_id + employee_id; "
        "vehicle_assignments: date + block_id + service_id). Consumers cannot tell "
        "the rows apart."
    ),
    spec_section=SPEC_URL,
)
def duplicate_primary_key(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        if table.kind != "tods" or table.primary_key is None:
            continue
        if any(f not in feed.headers for f in table.primary_key):
            continue  # TODS-E106 already reported the missing column
        # A blank *required* key field means the row is already malformed
        # (reported by TODS-E201), so skip it. But a blank optional/conditional
        # key field (e.g. vehicle_assignments.service_id) is a legitimate key
        # value and must still take part in the uniqueness check, otherwise two
        # rows that collide on the required components with a blank optional one
        # go undetected.
        required_key = {
            fs.name
            for fs in table.fields
            if fs.name in table.primary_key and fs.presence is Presence.REQUIRED
        }
        seen: dict[tuple[str, ...], int] = {}
        for row in feed.rows:
            key = tuple(row.values.get(f, "") for f in table.primary_key)
            if any(
                v == "" and f in required_key for f, v in zip(table.primary_key, key, strict=True)
            ):
                continue  # TODS-E201 already reported the blank required key field
            if key in seen:
                pretty = ", ".join(
                    f"{f}={v!r}" for f, v in zip(table.primary_key, key, strict=True)
                )
                yield Finding(
                    rule_id="TODS-E204",
                    severity=Severity.ERROR,
                    file=table.filename,
                    row=row.line,
                    message=(
                        f"{table.filename} row {row.line} repeats the primary key "
                        f"({pretty}) already used on row {seen[key]}. Each "
                        f"({', '.join(table.primary_key)}) combination may appear once."
                    ),
                    suggestion=(
                        "Remove the duplicate assignment row."
                        if table.filename == "employee_run_dates.txt"
                        else None
                    ),
                    data={
                        "value": pretty,
                        "field": ",".join(table.primary_key),
                        "referenced": f"{table.filename}#L{seen[key]}",
                    },
                )
            else:
                seen[key] = row.line


@rule(
    id="TODS-E205",
    severity=Severity.ERROR,
    title="vehicle_assignments needs service_id to be unambiguous",
    description=(
        "service_id in vehicle_assignments.txt is required when the same block_id is "
        "used by more than one service. Without it, the assignment cannot be matched "
        "to a single block."
    ),
    spec_section=f"{SPEC_URL}#vehicle_assignmentstxt",
    # Ambiguity is decided from which services use each block, read out of the
    # companion GTFS (trips.txt). Without it the check cannot run, so depend on
    # GTFS rather than silently passing.
    needs_gtfs=True,
    # vehicle_assignments.txt does not exist in TODS v1.0.0 (added in v2.1.0).
    spec_versions=(SPEC_VERSION,),
)
def vehicle_assignment_ambiguous(context: ValidationContext) -> Iterator[Finding]:
    feed = context.package.get("vehicle_assignments.txt")
    if feed is None or "block_id" not in feed.headers:
        return
    for row in feed.rows:
        if row.values.get("service_id", "") != "":
            continue
        block_id = row.values.get("block_id", "")
        if not block_id:
            continue
        services = context.gtfs.block_services.get(block_id, set()) if context.gtfs else set()
        if len(services) > 1:
            yield Finding(
                rule_id="TODS-E205",
                severity=Severity.ERROR,
                file="vehicle_assignments.txt",
                row=row.line,
                field="service_id",
                message=(
                    f"vehicle_assignments.txt row {row.line}: block_id {block_id!r} is "
                    f"used by {len(services)} different services in the GTFS feed "
                    f"({', '.join(sorted(services))}), so service_id is required here "
                    "to identify which block instance the vehicle covers."
                ),
                suggestion="Fill in the service_id the assignment applies to.",
                data={
                    "value": block_id,
                    "field": "service_id",
                    "expected": ",".join(sorted(services)),
                },
            )


@rule(
    id="TODS-W206",
    severity=Severity.WARNING,
    title="Value has leading or trailing spaces",
    description=(
        "A value is padded with spaces. IDs with stray spaces will not match the "
        "records they reference, and consumers are not required to trim them."
    ),
    spec_section=SPEC_URL,
    example=('Before: `stop_id` value is `"  1234  "`. After: trim on export — `1234`.'),
)
def padded_value(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        for row in feed.rows:
            for name, value in row.values.items():
                if value != value.strip():
                    yield Finding(
                        rule_id="TODS-W206",
                        severity=Severity.WARNING,
                        file=table.filename,
                        row=row.line,
                        field=name,
                        message=(
                            f"{table.filename} row {row.line}: {name} is {value!r}, "
                            "which has leading or trailing spaces."
                        ),
                        suggestion="Remove the padding so IDs match exactly.",
                        data={"value": value, "field": name, "expected": value.strip()},
                    )
