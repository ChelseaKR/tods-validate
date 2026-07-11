"""Semantic rules across rows (TODS-x4xx).

These checks are deliberately conservative where the spec is permissive. Real
schedules have legitimate edge cases (zero-minute events, overnight times,
overlapping non-trip events), and the spec allows them; only constraints the
spec actually states are errors here.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..findings import Finding, Severity
from ..gtfs_companion import parse_gtfs_date
from ..loader import Row
from ..run_events import _Event
from ..schema import SPEC_URL, SPEC_VERSION
from . import ValidationContext, rule

_RUN_EVENTS_SECTION = f"{SPEC_URL}#run_eventstxt"
# These checks assume v2.1.0's run_events.txt field names (start_time/end_time,
# service_id+run_id+event_sequence) and vehicle_assignments.txt/
# employee_run_dates.txt, none of which v1.0.0 has in this shape (v1's
# run_events.txt uses event_time/event_duration instead, and has no service_id/
# run_id columns at all -- see docs/spec-versions.md). Restricted to v2.1.0.
_V2_ONLY = (SPEC_VERSION,)


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E401",
    severity=Severity.ERROR,
    title="Event ends before it starts",
    description=(
        "A run event's end_time is earlier than its start_time. Equal times are fine "
        "(the spec allows zero-duration events such as a report time); for work past "
        "midnight, use hours of 24 or more rather than wrapping around."
    ),
    spec_section=_RUN_EVENTS_SECTION,
    interpretation=(
        "the spec is silent on end<start; this treats it as an error and equal "
        "times as valid (spec-questions #5)."
    ),
)
def event_ends_before_start(context: ValidationContext) -> Iterator[Finding]:
    for event in context.events:
        if event.start is not None and event.end is not None and event.end < event.start:
            yield Finding(
                rule_id="TODS-E401",
                severity=Severity.ERROR,
                file="run_events.txt",
                row=event.row.line,
                field="end_time",
                message=(
                    f"run_events.txt row {event.row.line}: end_time "
                    f"{event.row.values.get('end_time', '')!r} is earlier than "
                    f"start_time {event.row.values.get('start_time', '')!r}."
                ),
                suggestion=(
                    "If the event runs past midnight, keep counting hours upward: "
                    "write 1:10 AM the next day as '25:10:00'."
                ),
                data={
                    "value": event.row.values.get("end_time", ""),
                    "expected": event.row.values.get("start_time", ""),
                },
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E402",
    severity=Severity.ERROR,
    title="Two trip events in one run overlap in time",
    description=(
        "Within one run, two events that both reference trips overlap in time. The "
        "spec prohibits this: an employee cannot be on two trips at once. Touching "
        "end-to-start (zero-minute overlap) is allowed."
    ),
    spec_section=f"{SPEC_URL}#event_sequence-and-event-times",
)
def overlapping_trip_events(context: ValidationContext) -> Iterator[Finding]:
    for events in context.events_by_run.values():
        trip_events = [e for e in events if e.trip_id and e.start is not None and e.end is not None]
        trip_events.sort(key=lambda e: (e.start or 0, e.end or 0))
        # Sweep with the latest-ending event seen so far, so an event that
        # spans several later ones is compared against each of them.
        previous: _Event | None = None
        for current in trip_events:
            if (
                previous is not None
                and current.start is not None
                and previous.end is not None
                and current.start < previous.end
            ):
                yield Finding(
                    rule_id="TODS-E402",
                    severity=Severity.ERROR,
                    file="run_events.txt",
                    row=current.row.line,
                    message=(
                        f"run_events.txt row {current.row.line}: trip "
                        f"{current.trip_id!r} starts at "
                        f"{current.row.values.get('start_time', '')} but the same "
                        f"run is still on trip {previous.trip_id!r} until "
                        f"{previous.row.values.get('end_time', '')} (row "
                        f"{previous.row.line}). Trip events in one run must not "
                        "overlap; an employee cannot work two trips at once."
                    ),
                    data={
                        "value": current.row.values.get("start_time", ""),
                        "expected": previous.row.values.get("end_time", ""),
                        "referenced": f"run_events.txt#L{previous.row.line}",
                    },
                )
            if previous is None or (current.end or 0) > (previous.end or 0):
                previous = current


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W403",
    severity=Severity.WARNING,
    title="Event order disagrees with event times",
    description=(
        "Within one run, event_sequence does not increase with start_time. The spec "
        "says sequence values should increase throughout the day; out-of-order values "
        "usually mean the sequence or a time is wrong."
    ),
    spec_section=f"{SPEC_URL}#event_sequence-and-event-times",
)
def sequence_disagrees_with_time(context: ValidationContext) -> Iterator[Finding]:
    for events in context.events_by_run.values():
        timed = [e for e in events if e.sequence is not None and e.start is not None]
        timed.sort(key=lambda e: e.sequence or 0)
        for previous, current in zip(timed, timed[1:], strict=False):
            if previous.start is None or current.start is None:
                continue  # filtered above; keeps the type-checker satisfied
            if current.start < previous.start:
                yield Finding(
                    rule_id="TODS-W403",
                    severity=Severity.WARNING,
                    file="run_events.txt",
                    row=current.row.line,
                    field="event_sequence",
                    message=(
                        f"run_events.txt row {current.row.line}: event_sequence "
                        f"{current.sequence} starts at "
                        f"{current.row.values.get('start_time', '')}, earlier than "
                        f"event_sequence {previous.sequence} (row {previous.row.line}, "
                        f"{previous.row.values.get('start_time', '')}) in the same "
                        "run. Sequence values should increase through the day."
                    ),
                    data={
                        "value": str(current.sequence),
                        "expected": str(previous.sequence),
                        "referenced": f"run_events.txt#L{previous.row.line}",
                    },
                )
                break  # one finding per run is enough to point at the problem


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W404",
    severity=Severity.WARNING,
    title="Employee is assigned to overlapping runs on the same date",
    description=(
        "An employee is assigned to two runs on the same date whose events overlap in "
        "time. Real schedules have legitimate exceptions, so this is a warning, not "
        "an error."
    ),
    spec_section=f"{SPEC_URL}#employee_run_datestxt",
)
def employee_double_booked(context: ValidationContext) -> Iterator[Finding]:  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    assignments = context.package.get("employee_run_dates.txt")
    if assignments is None:
        return
    spans: dict[tuple[str, str], tuple[int, int]] = {}
    for run, events in context.events_by_run.items():
        times = [(e.start, e.end) for e in events if e.start is not None and e.end is not None]
        if times:
            spans[run] = (min(t[0] for t in times), max(t[1] for t in times))

    by_employee_date: dict[tuple[str, str], list[tuple[tuple[str, str], Row]]] = {}
    for row in assignments.rows:
        employee_id = row.values.get("employee_id", "")
        day = row.values.get("date", "")
        run = (row.values.get("service_id", ""), row.values.get("run_id", ""))
        if employee_id and day and all(run):
            by_employee_date.setdefault((employee_id, day), []).append((run, row))

    for (employee_id, day), entries in by_employee_date.items():
        for i, (run_a, _row_a) in enumerate(entries):
            for run_b, row_b in entries[i + 1 :]:
                if run_a == run_b or run_a not in spans or run_b not in spans:
                    continue
                start_a, end_a = spans[run_a]
                start_b, end_b = spans[run_b]
                if start_b < end_a and start_a < end_b:
                    yield Finding(
                        rule_id="TODS-W404",
                        severity=Severity.WARNING,
                        file="employee_run_dates.txt",
                        row=row_b.line,
                        message=(
                            f"employee_run_dates.txt row {row_b.line}: employee "
                            f"{employee_id!r} is assigned to run "
                            f"(service_id {run_b[0]!r}, run_id {run_b[1]!r}) on "
                            f"{day}, which overlaps in time with their assignment to "
                            f"run (service_id {run_a[0]!r}, run_id {run_a[1]!r}) on "
                            "the same date."
                        ),
                        suggestion=(
                            "If this is intentional (split duties), no change is "
                            "needed; otherwise check for a stale assignment."
                        ),
                        data={
                            "value": f"{run_b[0]},{run_b[1]}",
                            "referenced": f"{run_a[0]},{run_a[1]}",
                        },
                    )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-E405",
    severity=Severity.ERROR,
    title="Run operates on dates its trip does not",
    description=(
        "A run event works a trip whose service is different from the run's service, "
        "and the run's service operates on dates the trip's service does not. The "
        "spec requires the run's dates to be a subset of the trip's dates."
    ),
    spec_section=f"{SPEC_URL}#service_id-crew-schedules-and-trip-schedules",
    needs_gtfs=True,
)
def run_dates_exceed_trip_dates(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    dates = context.gtfs.service_dates
    reported: set[tuple[str, str]] = set()
    for event in context.events:
        if not event.trip_id or not event.service_id:
            continue
        trip_service = context.gtfs.trip_service.get(event.trip_id)
        if not trip_service or trip_service == event.service_id:
            continue
        if event.service_id not in dates or trip_service not in dates:
            continue  # undefined services are TODS-E308's concern
        if (event.service_id, trip_service) in reported:
            continue
        extra = dates[event.service_id] - dates[trip_service]
        if extra:
            reported.add((event.service_id, trip_service))
            sample = min(extra).strftime("%Y%m%d")
            yield Finding(
                rule_id="TODS-E405",
                severity=Severity.ERROR,
                file="run_events.txt",
                row=event.row.line,
                field="service_id",
                message=(
                    f"run_events.txt row {event.row.line}: the run's service "
                    f"{event.service_id!r} operates on {len(extra)} date(s) (e.g. "
                    f"{sample}) when trip {event.trip_id!r}'s service "
                    f"{trip_service!r} does not. A run may only work a trip on dates "
                    "the trip actually operates."
                ),
                suggestion=(
                    "Adjust the run's service days in calendar_supplement.txt or "
                    "calendar_dates_supplement.txt so they are a subset of the "
                    "trip's."
                ),
                data={
                    "value": event.service_id,
                    "expected": trip_service,
                    "referenced": event.trip_id,
                },
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W406",
    severity=Severity.WARNING,
    title="Employee assignment date is outside the run's service days",
    description=(
        "An employee_run_dates.txt row assigns a run on a date when the run's "
        "service_id does not operate, according to the supplemented calendars."
    ),
    spec_section=f"{SPEC_URL}#employee_run_datestxt",
    needs_gtfs=True,
)
def assignment_outside_service(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    assignments = context.package.get("employee_run_dates.txt")
    if assignments is None:
        return
    dates = context.gtfs.service_dates
    for row in assignments.rows:
        service_id = row.values.get("service_id", "")
        day = parse_gtfs_date(row.values.get("date", ""))
        if not service_id or day is None or service_id not in dates:
            continue
        if day not in dates[service_id]:
            yield Finding(
                rule_id="TODS-W406",
                severity=Severity.WARNING,
                file="employee_run_dates.txt",
                row=row.line,
                field="date",
                message=(
                    f"employee_run_dates.txt row {row.line}: "
                    f"{row.values.get('date', '')} is not a day that service "
                    f"{service_id!r} operates, so run "
                    f"(service_id {service_id!r}, run_id "
                    f"{row.values.get('run_id', '')!r}) has nothing scheduled then."
                ),
                suggestion=(
                    "Check the date, or extend the service via the calendar supplement files."
                ),
                data={
                    "value": row.values.get("date", ""),
                    "referenced": f"calendar.service_id={service_id}",
                },
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W407",
    severity=Severity.WARNING,
    title="Vehicle assignment date is outside the service days",
    description=(
        "A vehicle_assignments.txt row names a service_id and a date when that "
        "service does not operate, according to the supplemented calendars."
    ),
    spec_section=f"{SPEC_URL}#vehicle_assignmentstxt",
    needs_gtfs=True,
)
def vehicle_assignment_outside_service(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    assignments = context.package.get("vehicle_assignments.txt")
    if assignments is None:
        return
    dates = context.gtfs.service_dates
    for row in assignments.rows:
        service_id = row.values.get("service_id", "")
        day = parse_gtfs_date(row.values.get("date", ""))
        if not service_id or day is None or service_id not in dates:
            continue
        if day not in dates[service_id]:
            yield Finding(
                rule_id="TODS-W407",
                severity=Severity.WARNING,
                file="vehicle_assignments.txt",
                row=row.line,
                field="date",
                message=(
                    f"vehicle_assignments.txt row {row.line}: "
                    f"{row.values.get('date', '')} is not a day that service "
                    f"{service_id!r} operates, so block "
                    f"{row.values.get('block_id', '')!r} does not run then."
                ),
                data={
                    "value": row.values.get("date", ""),
                    "referenced": f"calendar.service_id={service_id}",
                },
            )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W408",
    severity=Severity.WARNING,
    title="Identical employee assignment appears twice",
    description=(
        "Two rows in employee_run_dates.txt are exactly identical (same date, "
        "service, run, and employee). Multiple employees per run are fine; the same "
        "employee twice is usually an export bug."
    ),
    spec_section=f"{SPEC_URL}#employee_run_datestxt",
    interpretation=(
        "permissive: the spec's 'Primary Key: *' is read as not forbidding an exact "
        "duplicate row, so this is a warning rather than an error (spec-questions #6)."
    ),
)
def duplicate_assignment(context: ValidationContext) -> Iterator[Finding]:
    assignments = context.package.get("employee_run_dates.txt")
    if assignments is None:
        return
    seen: dict[tuple[str, str, str, str], int] = {}
    for row in assignments.rows:
        key = (
            row.values.get("date", ""),
            row.values.get("service_id", ""),
            row.values.get("run_id", ""),
            row.values.get("employee_id", ""),
        )
        if not all(key):
            continue
        if key in seen:
            yield Finding(
                rule_id="TODS-W408",
                severity=Severity.WARNING,
                file="employee_run_dates.txt",
                row=row.line,
                message=(
                    f"employee_run_dates.txt row {row.line} repeats the assignment "
                    f"on row {seen[key]} exactly (date {key[0]}, service_id "
                    f"{key[1]!r}, run_id {key[2]!r}, employee_id {key[3]!r})."
                ),
                suggestion="Remove the duplicate row.",
                data={
                    "value": ",".join(key),
                    "referenced": f"employee_run_dates.txt#L{seen[key]}",
                },
            )
        else:
            seen[key] = row.line


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-W409",
    severity=Severity.WARNING,
    title="Consecutive run events do not connect in space",
    description=(
        "Within one run, an event ends at one location but the next event in "
        "event_sequence order starts somewhere else. An operator is one person who "
        "cannot teleport, so a gap usually means a missing deadhead event or a wrong "
        "location. Events with a blank endpoint are skipped."
    ),
    spec_section=f"{SPEC_URL}#event_sequence-and-event-times",
    interpretation=(
        "the spec does not state this explicitly, but a run is a continuous tour of "
        "duty; legitimate exceptions exist (so a warning), and adjacencies with a blank "
        "location are not flagged."
    ),
)
def run_events_discontinuous(context: ValidationContext) -> Iterator[Finding]:
    for events in context.events_by_run.values():
        ordered = sorted(
            (e for e in events if e.sequence is not None), key=lambda e: e.sequence or 0
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if not previous.end_location or not current.start_location:
                continue  # an unlocated endpoint says nothing about continuity
            if previous.end_location != current.start_location:
                yield Finding(
                    rule_id="TODS-W409",
                    severity=Severity.WARNING,
                    file="run_events.txt",
                    row=current.row.line,
                    field="start_location",
                    message=(
                        f"run_events.txt row {current.row.line}: event_sequence "
                        f"{current.sequence} starts at {current.start_location!r}, but the "
                        f"previous event (sequence {previous.sequence}, row "
                        f"{previous.row.line}) ended at {previous.end_location!r} in the same "
                        "run. Consecutive events should connect; an operator cannot jump "
                        "between locations."
                    ),
                    suggestion=(
                        "Add the missing deadhead or move event between them, or correct the "
                        "location so each event begins where the last one ended."
                    ),
                    data={
                        "value": current.start_location,
                        "expected": previous.end_location,
                        "referenced": f"run_events.txt#L{previous.row.line}",
                    },
                )
