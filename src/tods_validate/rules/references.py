"""Cross-file reference rules (TODS-x3xx).

Rules that resolve IDs into the companion GTFS feed run against the
"TODS-Supplemented GTFS": the GTFS files after supplement rows are applied.
Each check is gated on its target data actually being available, so a missing
companion file produces one clear finding instead of a flood of broken
references.

That gating is declared, not re-implemented per rule: each rule lists the GTFS
files it reads in ``gtfs_tables``, and the registry skips it -- visibly, in the
coverage manifest -- when the companion feed does not have them. So a rule body
here can assume its own files are present, and a rule that could not check
anything is never counted as one that ran. Checks that read several files
independently (TODS-W302, TODS-E314) still ask per file with the helpers below.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..findings import Finding, Severity
from ..loader import FeedFile, Package, Row
from ..schema import SPEC_URL, SPEC_VERSION, TABLES
from . import (
    GTFS_CALENDARS,
    GTFS_ROUTES,
    GTFS_STOP_TIMES,
    GTFS_STOPS,
    GTFS_TRIPS,
    ValidationContext,
    rule,
)
from .fields import parse_time

_SUPPLEMENT_SECTION = f"{SPEC_URL}#supplement-files"
# These rules resolve IDs against the companion GTFS "TODS-Supplemented GTFS",
# a mechanism the v1.0.0 spec does not have (Supplement files were introduced
# in v2.0.0-alpha.1). Restricted to v2.1.0; see docs/spec-versions.md.
_V2_ONLY = (SPEC_VERSION,)

# Every GTFS base file a supplement file can target, as one alternatives group:
# TODS-W313 and TODS-E314 read whichever of them the package supplements, so
# they have something to check as long as one of these is in the companion.
_SUPPLEMENTABLE = GTFS_TRIPS + GTFS_STOPS + GTFS_ROUTES + GTFS_STOP_TIMES + GTFS_CALENDARS
# The four files TODS-E314 resolves supplement rows against.
_E314_TARGETS = GTFS_ROUTES + GTFS_CALENDARS + GTFS_TRIPS + GTFS_STOPS


def _rows(context: ValidationContext, filename: str) -> list[Row]:
    feed = context.package.get(filename)
    return feed.rows if feed is not None else []


def _present(package: Package, filename: str) -> bool:
    """Whether ``filename`` is in the package and was parsed successfully.

    A file that failed to parse (TODS-E103) is still in ``package.files``,
    but with no rows, so treating it as present would make a rule that reads
    its rows to resolve references find nothing and report every real ID as
    dangling. Everywhere a rule reads *another* file's rows to check *this*
    file's references, gate on this, not on ``package.get(...) is not None``
    (#125).
    """
    feed = package.get(filename)
    return feed is not None and feed.readable


def _run_pairs(context: ValidationContext) -> set[tuple[str, str]]:
    # Thin wrapper kept so call sites read the same as before; the set is
    # derived once per validation and cached on the context (see
    # ValidationContext.run_pairs / .events_by_run).
    return context.run_pairs


# A GTFS table is available to resolve references only when the companion feed
# actually carries it. A TODS supplement file is not a substitute: it modifies
# a GTFS table, so without that table the "supplemented" view holds nothing but
# the supplement's own rows and every real ID reads as missing. Rules gated on
# these are also skipped in the coverage manifest for the same reason (see
# Rule.gtfs_tables), so an unavailable table is disclosed, never reported clean.
def _trips_available(context: ValidationContext) -> bool:
    assert context.gtfs is not None
    return "trips.txt" in context.gtfs.present


def _stops_available(context: ValidationContext) -> bool:
    assert context.gtfs is not None
    return "stops.txt" in context.gtfs.present


def _calendar_available(context: ValidationContext) -> bool:
    assert context.gtfs is not None
    return bool(set(GTFS_CALENDARS) & context.gtfs.present)


def _routes_available(context: ValidationContext) -> bool:
    assert context.gtfs is not None
    return "routes.txt" in context.gtfs.present


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E301",
    severity=Severity.ERROR,
    title="Employee assignment points to a run that does not exist",
    description=(
        "A row in employee_run_dates.txt names a (service_id, run_id) pair that has no "
        "events in run_events.txt. The assignment cannot be matched to a run."
    ),
    spec_section=f"{SPEC_URL}#employee_run_datestxt",
)
def employee_run_missing(context: ValidationContext) -> Iterator[Finding]:
    feed = context.package.get("employee_run_dates.txt")
    if feed is None or not _present(context.package, "run_events.txt"):
        return  # absence (or unreadability) of run_events.txt is TODS-W302's concern
    pairs = _run_pairs(context)
    for row in feed.rows:
        service_id = row.values.get("service_id", "")
        run_id = row.values.get("run_id", "")
        if not service_id or not run_id:
            continue
        if (service_id, run_id) not in pairs:
            yield Finding(
                rule_id="TODS-E301",
                severity=Severity.ERROR,
                file="employee_run_dates.txt",
                row=row.line,
                message=(
                    f"employee_run_dates.txt row {row.line}: run "
                    f"(service_id {service_id!r}, run_id {run_id!r}) has no events in "
                    "run_events.txt. Runs are identified by the service_id and run_id "
                    "pair, so both must match exactly."
                ),
                suggestion=(
                    "Check both IDs against run_events.txt; a run_id that exists under "
                    "a different service_id is a different run."
                ),
                data={
                    "service_id": service_id,
                    "run_id": run_id,
                    "referenced": "run_events.(service_id,run_id)",
                },
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W302",
    severity=Severity.WARNING,
    title="Referenced file is missing or unreadable, references not checked",
    description=(
        "A file references another file that is not in the package (or, for GTFS "
        "targets, not in the companion feed) or that could not be read (TODS-E103), "
        "so those references could not be validated."
    ),
    spec_section=SPEC_URL,
)
def referenced_file_missing(context: ValidationContext) -> Iterator[Finding]:
    package = context.package
    targets: list[tuple[str, str, str]] = [
        ("employee_run_dates.txt", "run_events.txt", "service_id and run_id values"),
        ("vehicle_assignments.txt", "vehicles.txt", "vehicle_id values"),
    ]
    for source, target, what in targets:
        if package.get(source) is None:
            continue
        target_feed = package.get(target)
        if target_feed is None:
            message = (
                f"{source} is present but {target} is not, so its {what} could not be checked."
            )
        elif not target_feed.readable:
            message = (
                f"{source} is present but {target} could not be read (see TODS-E103), "
                f"so its {what} could not be checked."
            )
        else:
            continue
        yield Finding(
            rule_id="TODS-W302",
            severity=Severity.WARNING,
            file=source,
            message=message,
            suggestion=f"Include a readable {target} in the package.",
        )
    if context.gtfs is not None:
        gtfs_needs: list[tuple[str, bool, str]] = [
            (
                "run_events.txt",
                _trips_available(context) or not _uses_column(package, "run_events.txt", "trip_id"),
                "trips.txt",
            ),
            ("run_events.txt", _stops_available(context), "stops.txt"),
            (
                "run_events.txt",
                _calendar_available(context),
                "calendar.txt or calendar_dates.txt",
            ),
            # vehicle_assignments.txt resolves block_id into trips and service_id
            # into the calendars (rules E311/E312). Without those companion files
            # the checks quietly no-op, so disclose the gap here too.
            (
                "vehicle_assignments.txt",
                _trips_available(context)
                or not _uses_column(package, "vehicle_assignments.txt", "block_id"),
                "trips.txt",
            ),
            (
                "vehicle_assignments.txt",
                _calendar_available(context)
                or not _uses_column(package, "vehicle_assignments.txt", "service_id"),
                "calendar.txt or calendar_dates.txt",
            ),
        ]
        for source, available, target in gtfs_needs:
            if package.get(source) is not None and not available:
                unreadable = [
                    name for name in target.split(" or ") if name in context.gtfs.unreadable
                ]
                if unreadable:
                    reasons = "; ".join(context.gtfs.unreadable[name] for name in unreadable)
                    message = (
                        f"The companion GTFS feed's {' and '.join(unreadable)} could not be "
                        f"read ({reasons}), so {source} references into it could not be checked."
                    )
                else:
                    message = (
                        f"The companion GTFS feed has no {target}, so {source} "
                        "references into it could not be checked."
                    )
                yield Finding(
                    rule_id="TODS-W302",
                    severity=Severity.WARNING,
                    file=source,
                    message=message,
                )


def _uses_column(package: Package, filename: str, column: str) -> bool:
    feed = package.get(filename)
    return feed is not None and any(row.values.get(column, "") for row in feed.rows)


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E303",
    severity=Severity.ERROR,
    title="Vehicle assignment points to a vehicle that does not exist",
    description=(
        "A row in vehicle_assignments.txt names a vehicle_id that is not defined in vehicles.txt."
    ),
    spec_section=f"{SPEC_URL}#vehicle_assignmentstxt",
)
def vehicle_missing(context: ValidationContext) -> Iterator[Finding]:
    assignments = context.package.get("vehicle_assignments.txt")
    vehicles = context.package.get("vehicles.txt")
    if assignments is None or vehicles is None or not vehicles.readable:
        return  # absence (or unreadability) of vehicles.txt is TODS-W302's concern
    known = {row.values.get("vehicle_id", "") for row in vehicles.rows} - {""}
    for row in assignments.rows:
        vehicle_id = row.values.get("vehicle_id", "")
        if vehicle_id and vehicle_id not in known:
            yield Finding(
                rule_id="TODS-E303",
                severity=Severity.ERROR,
                file="vehicle_assignments.txt",
                row=row.line,
                field="vehicle_id",
                message=(
                    f"vehicle_assignments.txt row {row.line}: vehicle_id "
                    f"{vehicle_id!r} is not defined in vehicles.txt."
                ),
                suggestion="Add the vehicle to vehicles.txt or correct the ID.",
                data={"value": vehicle_id, "referenced": "vehicles.vehicle_id"},
            )


def _supplement_groups(
    feed: FeedFile, primary_key: tuple[str, ...]
) -> dict[tuple[str, ...], list[Row]]:
    groups: dict[tuple[str, ...], list[Row]] = {}
    if any(f not in feed.headers for f in primary_key):
        return {}
    for row in feed.rows:
        key = tuple(row.values.get(f, "") for f in primary_key)
        if any(v == "" for v in key):
            continue
        groups.setdefault(key, []).append(row)
    return groups


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E304",
    severity=Severity.ERROR,
    title="Supplement both deletes and redefines the same row",
    description=(
        "A supplement file contains a delete (TODS_delete=1) and another row with the "
        "same primary key. The spec prohibits this because supplement rows are not "
        "processed in order, so the result is undefined."
    ),
    spec_section=_SUPPLEMENT_SECTION,
)
def delete_and_readd(context: ValidationContext) -> Iterator[Finding]:
    for name, table in TABLES.items():
        if table.kind != "supplement":
            continue
        feed = context.package.get(name)
        if feed is None or table.primary_key is None:
            continue
        for key, rows in _supplement_groups(feed, table.primary_key).items():
            if len(rows) < 2:
                continue
            deletes = [r for r in rows if r.values.get("TODS_delete", "") == "1"]
            others = [r for r in rows if r.values.get("TODS_delete", "") != "1"]
            if deletes and others:
                pretty = ", ".join(
                    f"{f}={v!r}" for f, v in zip(table.primary_key, key, strict=True)
                )
                yield Finding(
                    rule_id="TODS-E304",
                    severity=Severity.ERROR,
                    file=name,
                    row=others[0].line,
                    message=(
                        f"{name}: the row with ({pretty}) is deleted on row "
                        f"{deletes[0].line} and defined again on row {others[0].line}. "
                        "Deleting and re-adding the same primary key in one supplement "
                        "file is prohibited because rows are not processed in order."
                    ),
                    suggestion=(
                        "Keep one row: either delete the GTFS row, or update its values, not both."
                    ),
                    data={
                        "value": pretty,
                        "referenced": f"{name}#L{deletes[0].line}",
                    },
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W305",
    severity=Severity.WARNING,
    title="Supplement updates the same row more than once",
    description=(
        "A supplement file contains multiple non-delete rows with the same primary "
        "key. Supplement rows are not processed in order, so which values win is "
        "undefined."
    ),
    spec_section=_SUPPLEMENT_SECTION,
)
def duplicate_supplement_update(context: ValidationContext) -> Iterator[Finding]:
    for name, table in TABLES.items():
        if table.kind != "supplement":
            continue
        feed = context.package.get(name)
        if feed is None or table.primary_key is None:
            continue
        for key, rows in _supplement_groups(feed, table.primary_key).items():
            others = [r for r in rows if r.values.get("TODS_delete", "") != "1"]
            if len(others) > 1:
                pretty = ", ".join(
                    f"{f}={v!r}" for f, v in zip(table.primary_key, key, strict=True)
                )
                lines = ", ".join(str(r.line) for r in others)
                yield Finding(
                    rule_id="TODS-W305",
                    severity=Severity.WARNING,
                    file=name,
                    row=others[1].line,
                    message=(
                        f"{name}: rows {lines} all update the row with ({pretty}). "
                        "Files are processed non-sequentially, so which values apply "
                        "is undefined."
                    ),
                    suggestion="Combine the updates into a single row.",
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W306",
    severity=Severity.WARNING,
    title="Deleted supplement row carries values that will be ignored",
    description=(
        "A supplement row sets TODS_delete=1 and also fills in other fields. The spec "
        "says the row is removed and the other values are ignored."
    ),
    spec_section=_SUPPLEMENT_SECTION,
)
def delete_with_values(context: ValidationContext) -> Iterator[Finding]:
    for name, table in TABLES.items():
        if table.kind != "supplement":
            continue
        feed = context.package.get(name)
        if feed is None or table.primary_key is None:
            continue
        keys = set(table.primary_key) | {"TODS_delete"}
        for row in feed.rows:
            if row.values.get("TODS_delete", "") != "1":
                continue
            ignored = sorted(f for f, v in row.values.items() if f not in keys and v != "")
            if ignored:
                yield Finding(
                    rule_id="TODS-W306",
                    severity=Severity.WARNING,
                    file=name,
                    row=row.line,
                    message=(
                        f"{name} row {row.line} deletes a row (TODS_delete=1) but also "
                        f"fills in {', '.join(ignored)}. Those values are ignored when "
                        "a row is deleted."
                    ),
                    suggestion=(
                        "Leave the other fields blank, or remove TODS_delete if the "
                        "intent was to update the row."
                    ),
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E307",
    severity=Severity.ERROR,
    title="Run event points to a trip that does not exist",
    description=(
        "A run event names a trip_id that is not in the companion GTFS trips.txt after "
        "supplements are applied."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_TRIPS,),
    example=(
        "Before: `run_events.txt` row has `trip_id=T-1042`, but the companion "
        "`trips.txt` was re-exported without `T-1042`. After: re-export the companion "
        "GTFS alongside the TODS feed, or update `trip_id` to the current trips.txt value."
    ),
)
def run_event_trip_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    for row in _rows(context, "run_events.txt"):
        trip_id = row.values.get("trip_id", "")
        if trip_id and trip_id not in context.gtfs.trip_service:
            yield Finding(
                rule_id="TODS-E307",
                severity=Severity.ERROR,
                file="run_events.txt",
                row=row.line,
                field="trip_id",
                message=(
                    f"run_events.txt row {row.line}: trip_id {trip_id!r} does not "
                    "exist in the companion GTFS trips.txt (after applying "
                    "trips_supplement.txt). Run events that represent work on a trip "
                    "must reference a scheduled trip."
                ),
                suggestion=(
                    "Correct the trip_id, or add the trip via trips_supplement.txt if "
                    "it is non-revenue service."
                ),
                data={"value": trip_id, "referenced": "trips.trip_id"},
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E308",
    severity=Severity.ERROR,
    title="Run uses a service that does not exist",
    description=(
        "A run event names a service_id that is not defined in the companion GTFS "
        "calendar.txt or calendar_dates.txt after supplements are applied."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_CALENDARS,),
    example=(
        "Before: `run_events.txt` uses `service_id=WKDY-OLD`, but calendars were "
        "regenerated with `service_id=WKDY-2026`. After: update the run event's "
        "service_id, or define `WKDY-OLD` in `calendar_supplement.txt`."
    ),
)
def run_event_service_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    reported: set[str] = set()
    for row in _rows(context, "run_events.txt"):
        service_id = row.values.get("service_id", "")
        if service_id and service_id not in context.gtfs.service_ids:
            if service_id in reported:
                continue
            reported.add(service_id)
            yield Finding(
                rule_id="TODS-E308",
                severity=Severity.ERROR,
                file="run_events.txt",
                row=row.line,
                field="service_id",
                message=(
                    f"run_events.txt row {row.line}: service_id {service_id!r} is not "
                    "defined in calendar.txt or calendar_dates.txt (after applying "
                    "supplements), so the dates this run operates are unknown."
                ),
                suggestion=(
                    "Define the service in calendar_supplement.txt or "
                    "calendar_dates_supplement.txt if the crew schedule uses its own "
                    "service days."
                ),
                data={"value": service_id, "referenced": "calendar.service_id"},
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E309",
    severity=Severity.ERROR,
    title="Run event starts or ends at a stop that does not exist",
    description=(
        "A run event's start_location or end_location is not in the companion GTFS "
        "stops.txt after supplements are applied."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_STOPS,),
    example=(
        "Before: `run_events.txt` row has `start_location=STOP-99`, but `stops.txt` "
        "renumbered it to `STOP-0099`. After: update start_location/end_location to "
        "the current stop_ids, or add the stop via `stops_supplement.txt`."
    ),
)
def run_event_stop_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    for row in _rows(context, "run_events.txt"):
        for field_name in ("start_location", "end_location"):
            stop_id = row.values.get(field_name, "")
            if stop_id and stop_id not in context.gtfs.stop_ids:
                yield Finding(
                    rule_id="TODS-E309",
                    severity=Severity.ERROR,
                    file="run_events.txt",
                    row=row.line,
                    field=field_name,
                    message=(
                        f"run_events.txt row {row.line}: {field_name} {stop_id!r} does "
                        "not exist in the companion GTFS stops.txt (after applying "
                        "stops_supplement.txt)."
                    ),
                    suggestion=(
                        "Add non-public locations such as garages via stops_supplement.txt."
                    ),
                    data={
                        "value": stop_id,
                        "field": field_name,
                        "referenced": "stops.stop_id",
                    },
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E310",
    severity=Severity.ERROR,
    title="Run event block disagrees with the trip's block",
    description=(
        "A run event sets both block_id and trip_id, and the trip's block_id in the "
        "supplemented GTFS feed is different. The spec requires the two to match when "
        "both are set."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_TRIPS,),
)
def run_event_block_mismatch(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    for row in _rows(context, "run_events.txt"):
        block_id = row.values.get("block_id", "")
        trip_id = row.values.get("trip_id", "")
        if not block_id or not trip_id:
            continue
        trip_block = context.gtfs.trip_block.get(trip_id, "")
        if trip_block and trip_block != block_id:
            yield Finding(
                rule_id="TODS-E310",
                severity=Severity.ERROR,
                file="run_events.txt",
                row=row.line,
                field="block_id",
                message=(
                    f"run_events.txt row {row.line}: block_id is {block_id!r} but trip "
                    f"{trip_id!r} belongs to block {trip_block!r} in the supplemented "
                    "GTFS feed. When both are set they must not be different."
                ),
                data={
                    "value": block_id,
                    "expected": trip_block,
                    "trip_id": trip_id,
                    "referenced": "trips.block_id",
                },
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W315",
    severity=Severity.WARNING,
    title="Run event location does not match the trip's first or last stop",
    description=(
        "A run event works a trip end to end (trip_id set, the matching mid_trip flag "
        "not 1), but its start_location is not the trip's first stop, or its "
        "end_location is not the trip's last stop, in the supplemented stop_times.txt."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_STOP_TIMES,),
    interpretation=(
        "the spec says these locations 'should' be the trip endpoints, so a mismatch is "
        "a warning; skipped for mid-trip events and for trips with no stop_times."
    ),
)
def run_event_endpoint_mismatch(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    gtfs = context.gtfs
    feed = context.package.get("run_events.txt")
    if feed is None or "trip_id" not in feed.headers:
        return
    for row in feed.rows:
        trip_id = row.values.get("trip_id", "")
        if not trip_id or trip_id not in gtfs.trip_first_stop:
            continue
        endpoints = (
            ("start_location", "start_mid_trip", gtfs.trip_first_stop[trip_id], "first"),
            ("end_location", "end_mid_trip", gtfs.trip_last_stop[trip_id], "last"),
        )
        for loc_field, mid_field, expected, which in endpoints:
            if row.values.get(mid_field, "") == "1":
                continue  # a mid-trip event need not start or end at an endpoint
            actual = row.values.get(loc_field, "")
            if actual and expected and actual != expected:
                edge = "starts" if which == "first" else "ends"
                yield Finding(
                    rule_id="TODS-W315",
                    severity=Severity.WARNING,
                    file="run_events.txt",
                    row=row.line,
                    field=loc_field,
                    message=(
                        f"run_events.txt row {row.line}: {loc_field} {actual!r} is not the "
                        f"{which} stop of trip {trip_id!r} ({expected!r}) in stop_times.txt. "
                        f"If the event {edge} mid-trip, set {mid_field} to 1."
                    ),
                    suggestion=(
                        f"Use the trip's {which} stop as {loc_field}, or set {mid_field}=1 "
                        "for a mid-trip event."
                    ),
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W316",
    severity=Severity.WARNING,
    title="Run event time does not match the trip's scheduled time",
    description=(
        "A run event works a trip end to end (trip_id set, the matching mid_trip flag "
        "not 1), but its start_time is not the trip's first scheduled departure, or its "
        "end_time is not the trip's last scheduled arrival, in the supplemented "
        "stop_times.txt."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_STOP_TIMES,),
    interpretation=(
        "the companion of TODS-W315 for time: a run event claiming to work a whole trip "
        "should span the trip's scheduled times, so a mismatch is a warning; skipped for "
        "mid-trip events, for trips with no stop_times, and when either time is unparseable."
    ),
)
def run_event_time_mismatch(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    gtfs = context.gtfs
    feed = context.package.get("run_events.txt")
    if feed is None or "trip_id" not in feed.headers:
        return
    for row in feed.rows:
        trip_id = row.values.get("trip_id", "")
        if not trip_id or trip_id not in gtfs.trip_first_departure:
            continue
        endpoints = (
            ("start_time", "start_mid_trip", gtfs.trip_first_departure[trip_id], "departs"),
            ("end_time", "end_mid_trip", gtfs.trip_last_arrival[trip_id], "arrives"),
        )
        for time_field, mid_field, expected, verb in endpoints:
            if row.values.get(mid_field, "") == "1":
                continue  # a mid-trip event need not span the whole trip
            actual = row.values.get(time_field, "")
            # Compare parsed seconds so 24:00:00 and 00:00:00 are not confused, and
            # only when both sides actually parse (E203 flags the ones that do not).
            if not actual or not expected:
                continue
            actual_seconds = parse_time(actual)
            expected_seconds = parse_time(expected)
            if actual_seconds is None or expected_seconds is None:
                continue
            if actual_seconds != expected_seconds:
                yield Finding(
                    rule_id="TODS-W316",
                    severity=Severity.WARNING,
                    file="run_events.txt",
                    row=row.line,
                    field=time_field,
                    message=(
                        f"run_events.txt row {row.line}: {time_field} {actual!r} is not when "
                        f"trip {trip_id!r} {verb} ({expected!r}) in stop_times.txt. If the "
                        f"event works only part of the trip, set {mid_field} to 1."
                    ),
                    suggestion=(
                        f"Use the trip's scheduled time as {time_field}, or set {mid_field}=1 "
                        "for an event that does not span the whole trip."
                    ),
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E311",
    severity=Severity.ERROR,
    title="Vehicle assignment points to a block that does not exist",
    description=(
        "A vehicle assignment names a block_id that no trip uses in the companion "
        "GTFS feed after supplements are applied."
    ),
    spec_section=f"{SPEC_URL}#vehicle_assignmentstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_TRIPS,),
)
def vehicle_block_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    for row in _rows(context, "vehicle_assignments.txt"):
        block_id = row.values.get("block_id", "")
        if block_id and block_id not in context.gtfs.block_ids:
            yield Finding(
                rule_id="TODS-E311",
                severity=Severity.ERROR,
                file="vehicle_assignments.txt",
                row=row.line,
                field="block_id",
                message=(
                    f"vehicle_assignments.txt row {row.line}: block_id {block_id!r} is "
                    "not used by any trip in the companion GTFS feed (after applying "
                    "trips_supplement.txt)."
                ),
                data={"value": block_id, "referenced": "trips.block_id"},
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E312",
    severity=Severity.ERROR,
    title="Vehicle assignment uses a service that does not exist",
    description=(
        "A vehicle assignment names a service_id that is not defined in the companion "
        "GTFS calendars after supplements are applied."
    ),
    spec_section=f"{SPEC_URL}#vehicle_assignmentstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_CALENDARS,),
)
def vehicle_service_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    for row in _rows(context, "vehicle_assignments.txt"):
        service_id = row.values.get("service_id", "")
        if service_id and service_id not in context.gtfs.service_ids:
            yield Finding(
                rule_id="TODS-E312",
                severity=Severity.ERROR,
                file="vehicle_assignments.txt",
                row=row.line,
                field="service_id",
                message=(
                    f"vehicle_assignments.txt row {row.line}: service_id "
                    f"{service_id!r} is not defined in calendar.txt or "
                    "calendar_dates.txt (after applying supplements)."
                ),
                data={"value": service_id, "referenced": "calendar.service_id"},
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W313",
    severity=Severity.WARNING,
    title="Supplement deletes a row that is not in GTFS",
    description=(
        "A supplement row sets TODS_delete=1 but no row with that primary key exists "
        "in the companion GTFS file. Nothing is deleted; this usually means the ID is "
        "wrong or the GTFS feed changed."
    ),
    spec_section=_SUPPLEMENT_SECTION,
    needs_gtfs=True,
    gtfs_tables=(_SUPPLEMENTABLE,),
)
def delete_target_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    for name, table in TABLES.items():
        if table.kind != "supplement" or table.primary_key is None:
            continue
        feed = context.package.get(name)
        base_name = table.gtfs_base
        if feed is None or base_name is None or base_name not in context.gtfs.present:
            continue
        base_keys = context.gtfs.base_keys.get(base_name, set())
        for row in feed.rows:
            if row.values.get("TODS_delete", "") != "1":
                continue
            key = tuple(row.values.get(f, "") for f in table.primary_key)
            if not all(key):
                continue
            if key not in base_keys:
                pretty = ", ".join(
                    f"{f}={v!r}" for f, v in zip(table.primary_key, key, strict=True)
                )
                yield Finding(
                    rule_id="TODS-W313",
                    severity=Severity.WARNING,
                    file=name,
                    row=row.line,
                    message=(
                        f"{name} row {row.line} deletes ({pretty}), but no such row "
                        f"exists in the companion GTFS {base_name}. Nothing is "
                        "deleted."
                    ),
                    suggestion=(
                        "Check the ID against the GTFS feed; the row may have already "
                        "been removed in a newer GTFS export."
                    ),
                )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E314",
    severity=Severity.ERROR,
    title="Supplement row references a GTFS entity that does not exist",
    description=(
        "A supplement row names a route, service, trip, or stop that is not in the "
        "supplemented GTFS feed (for example, a trip added by trips_supplement.txt "
        "with a route_id that exists nowhere). The merged feed would not form valid "
        "GTFS."
    ),
    spec_section=_SUPPLEMENT_SECTION,
    needs_gtfs=True,
    gtfs_tables=(_E314_TARGETS,),
    example=(
        "Before: `trips_supplement.txt` adds a trip with `route_id=RT-77`, but no such "
        "route exists in `routes.txt` or `routes_supplement.txt`. After: use an existing "
        "route_id, or add `RT-77` to `routes_supplement.txt`."
    ),
)
def supplement_reference_missing(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    gtfs = context.gtfs
    # Trips deleted via trips_supplement (TODS_delete=1) leave the supplemented
    # feed. The spec says a deleted trip's stop_times "would thus be ignored,"
    # so a stop_times_supplement row pointing at a deleted trip is not a missing
    # reference and must not raise E314.
    deleted_trips = {
        key[0] for key in gtfs.base_keys.get("trips.txt", set()) if key[0] not in gtfs.trip_service
    }
    checks: list[tuple[str, str, bool, set[str], str]] = [
        (
            "trips_supplement.txt",
            "route_id",
            _routes_available(context),
            gtfs.route_ids,
            "routes.txt (after applying routes_supplement.txt)",
        ),
        (
            "trips_supplement.txt",
            "service_id",
            _calendar_available(context),
            gtfs.service_ids,
            "calendar.txt or calendar_dates.txt (after applying supplements)",
        ),
        (
            "stop_times_supplement.txt",
            "trip_id",
            _trips_available(context),
            set(gtfs.trip_service),
            "trips.txt (after applying trips_supplement.txt)",
        ),
        (
            "stop_times_supplement.txt",
            "stop_id",
            _stops_available(context),
            gtfs.stop_ids,
            "stops.txt (after applying stops_supplement.txt)",
        ),
    ]
    for filename, field_name, available, valid_ids, where in checks:
        feed = context.package.get(filename)
        if feed is None or not available or field_name not in feed.headers:
            continue
        for row in feed.rows:
            if row.values.get("TODS_delete", "") == "1":
                continue  # other values on a delete row are ignored
            value = row.values.get(field_name, "")
            if (
                filename == "stop_times_supplement.txt"
                and field_name == "trip_id"
                and value in deleted_trips
            ):
                continue  # spec: stop_times for a deleted trip are ignored
            if value and value not in valid_ids:
                yield Finding(
                    rule_id="TODS-E314",
                    severity=Severity.ERROR,
                    file=filename,
                    row=row.line,
                    field=field_name,
                    message=(
                        f"{filename} row {row.line}: {field_name} {value!r} does not "
                        f"exist in {where}. The merged feed would reference a missing "
                        "record."
                    ),
                    suggestion=(
                        f"Correct the {field_name}, or add the missing record via the "
                        "matching supplement file."
                    ),
                    data={"value": value, "field": field_name},
                )
