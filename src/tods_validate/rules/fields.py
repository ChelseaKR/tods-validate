"""Field-value rules within a single file (TODS-x2xx)."""

from __future__ import annotations

import re
from collections.abc import Iterator

from ..findings import Finding, Severity
from ..loader import FeedFile
from ..schema import SPEC_URL, TABLES, FieldSpec, FieldType, Presence, TableSpec
from . import ValidationContext, rule

# GTFS Time: H:MM:SS or HH:MM:SS; hours may exceed 24 for service past midnight
# and have no upper bound in the spec, so the hour field is not width-capped.
_TIME_RE = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")
_DATE_RE = re.compile(r"^\d{8}$")


def parse_time(value: str) -> int | None:
    """Return seconds since noon-minus-12h, or None if not a valid GTFS time."""
    m = _TIME_RE.match(value)
    if m is None:
        return None
    hours, minutes, seconds = (int(g) for g in m.groups())
    return hours * 3600 + minutes * 60 + seconds


def _is_valid_date(value: str) -> bool:
    from ..gtfs_companion import parse_gtfs_date

    return _DATE_RE.match(value) is not None and parse_gtfs_date(value) is not None


def _tods_tables(context: ValidationContext) -> Iterator[tuple[TableSpec, FeedFile]]:
    for name, table in TABLES.items():
        feed = context.package.get(name)
        if feed is not None and feed.headers:
            yield table, feed


def _required_fields(table: TableSpec) -> tuple[FieldSpec, ...]:
    if table.kind == "supplement":
        names = set(table.primary_key or ())
        return tuple(f for f in table.fields if f.name in names)
    return tuple(f for f in table.fields if f.presence is Presence.REQUIRED)


@rule(
    id="TODS-E201",
    severity=Severity.ERROR,
    title="Required value is missing",
    description=(
        "A field the spec marks Required is empty (for supplement files: a primary-key "
        "field, without which the row cannot be matched to GTFS)."
    ),
    spec_section=SPEC_URL,
)
def missing_required_value(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        required = [f for f in _required_fields(table) if f.name in feed.headers]
        for row in feed.rows:
            for f in required:
                if row.values.get(f.name, "") == "":
                    yield Finding(
                        rule_id="TODS-E201",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name!r} is required but empty."
                        ),
                        suggestion=f"See {SPEC_URL}{table.spec_anchor}.",
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
                if value not in f.enum_values:
                    allowed = ", ".join(repr(v) for v in f.enum_values if v) or "'1'"
                    yield Finding(
                        rule_id="TODS-E202",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name} is {value!r}, "
                            f"but the only allowed values are blank or {allowed}."
                        ),
                        suggestion=f"See {SPEC_URL}{table.spec_anchor}.",
                    )


@rule(
    id="TODS-E203",
    severity=Severity.ERROR,
    title="Value has the wrong format",
    description=(
        "A value does not match its field type: times must be HH:MM:SS (hours may "
        "exceed 24 for service after midnight), dates must be YYYYMMDD, and "
        "event_sequence must be a non-negative whole number."
    ),
    spec_section=SPEC_URL,
    interpretation=(
        "permissive: GTFS time syntax with hours beyond 24:00:00 is accepted, though "
        "the spec's Time type does not state it explicitly (spec-questions #5)."
    ),
)
def invalid_format(context: ValidationContext) -> Iterator[Finding]:
    for table, feed in _tods_tables(context):
        typed = [
            f
            for f in table.fields
            if f.type in (FieldType.TIME, FieldType.DATE, FieldType.NON_NEGATIVE_INTEGER)
            and f.name in feed.headers
        ]
        for row in feed.rows:
            for f in typed:
                value = row.values.get(f.name, "")
                if value == "":
                    continue  # emptiness is TODS-E201's concern
                if f.type is FieldType.TIME and parse_time(value) is None:
                    yield Finding(
                        rule_id="TODS-E203",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name} is {value!r}, "
                            "which is not a valid time. Use HH:MM:SS, e.g. '09:45:00' "
                            "or '25:10:00' for 1:10 AM the next service day."
                        ),
                    )
                elif f.type is FieldType.DATE and not _is_valid_date(value):
                    yield Finding(
                        rule_id="TODS-E203",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name} is {value!r}, "
                            "which is not a valid date. Use YYYYMMDD, e.g. '20260315'."
                        ),
                    )
                elif f.type is FieldType.NON_NEGATIVE_INTEGER and not value.isdigit():
                    yield Finding(
                        rule_id="TODS-E203",
                        severity=Severity.ERROR,
                        file=table.filename,
                        row=row.line,
                        field=f.name,
                        message=(
                            f"{table.filename} row {row.line}: {f.name} is {value!r}, "
                            "which is not a non-negative whole number."
                        ),
                    )


@rule(
    id="TODS-E204",
    severity=Severity.ERROR,
    title="Duplicate primary key",
    description=(
        "Two rows in a TODS-specific file share the same primary key "
        "(run_events: service_id + run_id + event_sequence; vehicles: vehicle_id; "
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
    interpretation=(
        "per-row reading: fires only for rows whose block_id is ambiguous, not for "
        "every row once any block is shared (spec-questions #8)."
    ),
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
    interpretation=(
        "strict: values are compared exactly; the spec defines no trimming rule, so "
        "padded example values are flagged rather than silently trimmed (spec-questions #3)."
    ),
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
                    )
