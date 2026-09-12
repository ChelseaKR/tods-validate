"""Local policy rules (LOCAL-P0xx): an agency's own operational limits.

A labour agreement says how long a run may be, how short a break may be, and how
many days in a row one person may be scheduled. The TODS specification cannot
say any of that, and an agency's scheduling tool usually knows it and drops it
at export. This module evaluates those limits against a package, from a
declarative ``[policy]`` table in ``tods-validate.toml``: thresholds and a break
vocabulary, with no code and no expression language (ADR 0004 holds here too).

Why these are not registry rules
--------------------------------
Everything registered in ``rules/`` exists on every run. It has a fixture in the
conformance corpus, a row in every coverage manifest, and a page in the
published rule catalog. A local rule must have none of those unless an agency
asked for it. With no ``[policy]`` table there is no local band at all, and a
report is byte-identical to one from a build without this module. That
guarantee is why this lives outside the registry, and why nothing here calls
``rules.rule``.

Why ``LOCAL-`` and not ``OPS-``
-------------------------------
ADR 0008 expected these to reuse ``OPS-``. ADR 0009 records why they cannot. An
``OPS-`` rule is registered and ships with a project default and a corpus
fixture, and these may do neither. The letter after an ``OPS-`` prefix is the
rule's severity, and here the agency sets the severity, so an ID that encoded
it would be wrong for any agency that chose differently. And an ``OPS-``
finding is this project's judgement while a ``LOCAL-`` finding is the agency's
own: a reader of a report should be able to tell whose rule fired.

What the checks refuse to do
----------------------------
A limit checked against a partial read is a pass nobody earned. A run whose
events cannot all be timed, a break whose end cannot be read, an employee with
an unreadable date, and every unit in a file that was not read in full are
counted as unmeasurable with a reason, and never as having passed. The
coverage manifest states every configured rule's denominator, including zero.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from .findings import Finding, Severity
from .gtfs_companion import CompanionGTFS, parse_gtfs_date
from .loader import FeedFile

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for annotations only
    from .rules import Measurement, Rule, RuleOutcome, ValidationContext
    from .run_events import _Event

LOCAL_NAMESPACE = "LOCAL-"
LOCAL_CATEGORY = "local-policy"
DECISION_RECORD = (
    "https://github.com/ChelseaKR/tods-validate/blob/main/docs/adr/0009-local-policy-rules.md"
)
BREAK_TYPES_KEY = "break-event-types"
DEFAULT_SEVERITY = Severity.WARNING

# Said at the end of every LOCAL- finding in these words, so no report format,
# annotation or excerpt can show one without saying whose rule it is.
AGENCY_POLICY_NOTE = "This is agency policy, not the TODS specification."

# The kinds of value a [policy] key takes.
KIND_MINUTES = "minutes"
KIND_DAYS = "days"
KIND_FLAG = "flag"


@dataclass(frozen=True)
class LocalRule:
    """One local policy rule: what it is called, what it reads, what it measures."""

    id: str
    # The [policy] key that turns this rule on and sets its limit.
    key: str
    kind: str
    title: str
    description: str
    # Exactly what is measured, in one sentence. Shown by `explain` and quoted
    # in the rule's findings, because a limit is only checkable if the
    # quantity it limits is defined.
    measures: str
    # What one unit of the coverage-manifest measurement is.
    unit: str
    # Rules that need the companion GTFS feed (for operating days) are skipped,
    # and disclosed as skipped, when none is available.
    needs_gtfs: bool = False


LOCAL_RULES: tuple[LocalRule, ...] = (
    LocalRule(
        id="LOCAL-P001",
        key="max-run-minutes",
        kind=KIND_MINUTES,
        title="A run's worked time is longer than the agency allows",
        description=(
            "The time a run spends on events other than breaks is longer than the limit "
            "set in the agency's [policy] table. The TODS specification says nothing about "
            "how long a run may be; this checks the agency's own rule."
        ),
        measures=(
            "worked time: the time covered by the run's events, leaving out events whose "
            "event_type is listed in break-event-types, with overlapping events counted once"
        ),
        unit="run",
    ),
    LocalRule(
        id="LOCAL-P002",
        key="max-piece-minutes",
        kind=KIND_MINUTES,
        title="A piece of work is longer than the agency allows",
        description=(
            "A piece of a run, the events that share one piece_id, lasts longer than the "
            "limit set in the agency's [policy] table. A run whose events carry no piece_id "
            "cannot be divided into pieces and is reported as unmeasurable."
        ),
        measures=(
            "piece length: from the earliest start_time to the latest end_time among the "
            "events that share one piece_id within a run; an event with no piece_id belongs "
            "to no piece"
        ),
        unit="run",
    ),
    LocalRule(
        id="LOCAL-P003",
        key="min-break-minutes",
        kind=KIND_MINUTES,
        title="A break is shorter than the agency allows",
        description=(
            "An event the agency's policy names as a break is shorter than the minimum set "
            "in its [policy] table. A run with no break at all is not a finding here; "
            "TODS-I601 is the advisory for a long run without one."
        ),
        measures=(
            "break length: end_time minus start_time of each event whose event_type is "
            "listed in break-event-types, matched exactly after trimming spaces"
        ),
        unit="break event",
    ),
    LocalRule(
        id="LOCAL-P004",
        key="max-spread-minutes",
        kind=KIND_MINUTES,
        title="A run's spread is longer than the agency allows",
        description=(
            "The time from a run's first event to its last, breaks included, is longer than "
            "the limit set in the agency's [policy] table."
        ),
        measures=(
            "spread: from the earliest start_time to the latest end_time among all of the "
            "run's events, breaks included"
        ),
        unit="run",
    ),
    LocalRule(
        id="LOCAL-P005",
        key="max-consecutive-days-per-employee",
        kind=KIND_DAYS,
        title="An employee is scheduled on more consecutive days than the agency allows",
        description=(
            "employee_run_dates.txt assigns one employee on more consecutive calendar days "
            "than the limit set in the agency's [policy] table."
        ),
        measures=(
            "consecutive days: calendar dates in employee_run_dates.txt on which one "
            "employee_id holds at least one assignment, with no date between them missing"
        ),
        unit="employee",
    ),
    LocalRule(
        id="LOCAL-P006",
        key="require-vehicle-assignment-for-revenue-events",
        kind=KIND_FLAG,
        title="A revenue event has no vehicle assigned on a day it operates",
        description=(
            "The agency's [policy] table requires every revenue event to have a vehicle, and "
            "on at least one day the event's trip operates, vehicle_assignments.txt assigns "
            "no vehicle to its block. Needs the companion GTFS trips and calendars to know "
            "which days those are."
        ),
        measures=(
            "a revenue event is a run event that carries a trip_id, the rule `stats` and "
            "`pickdiff` use; its block is its own block_id or else its trip's block_id in "
            "the companion trips.txt; it operates on the days its trip's service operates in "
            "the supplemented calendars, and each of those days needs a vehicle_assignments.txt "
            "row for that block, under the trip's service_id or a blank one"
        ),
        unit="revenue event",
        needs_gtfs=True,
    ),
)

LOCAL_RULES_BY_ID: dict[str, LocalRule] = {r.id: r for r in LOCAL_RULES}
LOCAL_RULES_BY_KEY: dict[str, LocalRule] = {r.key: r for r in LOCAL_RULES}


@dataclass(frozen=True)
class PolicyLimit:
    """One configured local rule: its limit and the severity the agency gave it."""

    rule: LocalRule
    # Minutes or days; 1 for a flag that is switched on.
    value: int
    severity: Severity = DEFAULT_SEVERITY

    @property
    def setting(self) -> str:
        """The setting as it reads in the [policy] table, e.g. ``max-spread-minutes = 660``."""
        value = "true" if self.rule.kind == KIND_FLAG else str(self.value)
        return f"{self.rule.key} = {value}"


@dataclass(frozen=True)
class LocalPolicy:
    """The parsed ``[policy]`` table, built by ``config.py``.

    ``break_event_types`` is None when the table does not declare a break
    vocabulary, which is different from declaring an empty one: an empty list
    is the agency saying none of its event types is a break.
    """

    limits: tuple[PolicyLimit, ...]
    break_event_types: frozenset[str] | None = None
    # Flags this table set to false. Kept so that a file which `extends` a
    # house policy can switch off a flag the house policy switched on.
    switched_off: frozenset[str] = frozenset()

    def limit(self, rule_id: str) -> PolicyLimit | None:
        return next((limit for limit in self.limits if limit.rule.id == rule_id), None)


def as_rule(local: LocalRule, severity: Severity = DEFAULT_SEVERITY) -> Rule:
    """``local`` as a registry-shaped :class:`~tods_validate.rules.Rule`, for rendering.

    ``explain`` and ``rules`` describe a rule through the same renderers
    whatever its namespace, so a local rule is handed to them in the registry's
    shape. It is never added to the registry and never run through
    ``rules.validate``; its check refuses to run so that a mistake which does
    either fails loudly.
    """
    from .rules import GTFS_CALENDARS, Rule

    def _not_a_registry_check(_context: object) -> object:
        raise RuntimeError(
            f"{local.id} is evaluated by tods_validate.local_policy.evaluate, "
            "not by the rule registry"
        )

    return Rule(
        id=local.id,
        severity=severity,
        title=local.title,
        description=local.description,
        spec_section=DECISION_RECORD,
        check=_not_a_registry_check,  # type: ignore[arg-type]
        needs_gtfs=local.needs_gtfs,
        gtfs_tables=(GTFS_CALENDARS,) if local.needs_gtfs else (),
        category=LOCAL_CATEGORY,
        default_enabled=False,
        interpretation=f"Configured by [policy] {local.key}. Measures {local.measures}.",
    )


# --- measuring helpers --------------------------------------------------------


def _read_gap(feed: FeedFile) -> str | None:
    """Why nothing in ``feed`` can be measured from, or None when it was read in full.

    A file that could not be parsed has no rows, and one that parsed with lost
    values has rows that are not the file. Either way a limit checked against
    it would be checked against something other than the export, so every unit
    that depends on it is unmeasurable (ADR 0007 makes the same argument for the
    companion GTFS feed).
    """
    if not feed.readable:
        return f"{feed.name} could not be read"
    if not feed.fully_read:
        return f"{feed.name} was not read in full, so no row in it is known to be complete"
    return None


def _untimed(events: Iterable[_Event]) -> str | None:
    """Why these events cannot be timed, or None when every one of them can."""
    timed = _timed(events := list(events))
    if len(timed) != len(events):
        return "an event in the run has no readable start_time or end_time"
    if any(end < start for start, end, _ in timed):
        return "an event in the run ends before it starts (see TODS-E401)"
    return None


def _timed(events: Iterable[_Event]) -> list[tuple[int, int, _Event]]:
    """``(start, end, event)`` for each event whose start_time and end_time both parse."""
    return [(e.start, e.end, e) for e in events if e.start is not None and e.end is not None]


def _hm(seconds: int) -> str:
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _run_label(run: tuple[str, str]) -> str:
    return f"(service_id {run[0]!r}, run_id {run[1]!r})"


def _event_type(event: _Event) -> str:
    return event.row.values.get("event_type", "").strip()


class _Tally:
    """Measured and unmeasurable counts for one rule, with the reasons for the second."""

    def __init__(self, unit: str) -> None:
        self.unit = unit
        self.measured = 0
        self.unmeasurable = 0
        self.reasons: dict[str, None] = {}
        # Why there was nothing to measure at all, when that is the case.
        self.absent: str | None = None

    def miss(self, reason: str, count: int = 1) -> None:
        self.unmeasurable += count
        if count:
            self.reasons.setdefault(reason, None)

    def measurement(self) -> Measurement:
        from .rules import Measurement

        reason = "; ".join(self.reasons) if self.reasons else self.absent
        return Measurement(
            measured=self.measured,
            unmeasurable=self.unmeasurable,
            unit=self.unit,
            reason=reason,
        )


def _finding(
    limit: PolicyLimit,
    *,
    file: str,
    row: int,
    field: str,
    message: str,
    value: str,
    expected: str,
) -> Finding:
    return Finding(
        rule_id=limit.rule.id,
        severity=limit.severity,
        file=file,
        row=row,
        field=field,
        message=f"{message} {AGENCY_POLICY_NOTE}",
        # Suggestion-free by design: a policy finding is a scheduling decision
        # to revisit, and nothing here knows what the right schedule is.
        suggestion=None,
        data={"value": value, "expected": expected, "policy": limit.setting},
    )


def _runs(context: ValidationContext, tally: _Tally) -> dict[tuple[str, str], list[_Event]] | None:
    """The runs a run-level rule measures, or None when none can be measured.

    Records the reason on ``tally`` in the None case: an absent file leaves
    nothing to count, and a file that was not read in full makes every run it
    does show unmeasurable.
    """
    feed = context.package.get("run_events.txt")
    if feed is None:
        tally.absent = "the package has no run_events.txt"
        return None
    gap = _read_gap(feed)
    if gap is not None:
        tally.absent = gap
        tally.miss(gap, len(context.events_by_run))
        return None
    return context.events_by_run


# --- the six checks -----------------------------------------------------------

_CheckResult = tuple[list[Finding], "Measurement"]


def _worked_time(work: list[tuple[int, int, _Event]], ceiling: int) -> tuple[int, _Event | None]:
    """Seconds covered by ``work`` (sorted by start), overlaps counted once.

    Also returns the event during which the running total first passes
    ``ceiling``: that is the row a scheduler has to change, and it is where the
    finding points. Two events that overlap -- a defect TODS-E402 reports -- do
    not make a run look longer than the time it occupies.
    """
    worked = 0
    covered_until: int | None = None
    crossing: _Event | None = None
    for start, end, event in work:
        begin = start if covered_until is None else max(start, covered_until)
        if end > begin:
            worked += end - begin
        covered_until = end if covered_until is None else max(covered_until, end)
        if crossing is None and worked > ceiling:
            crossing = event
    return worked, crossing


def _max_run(context: ValidationContext, limit: PolicyLimit, policy: LocalPolicy) -> _CheckResult:
    tally = _Tally(limit.rule.unit)
    findings: list[Finding] = []
    breaks = policy.break_event_types or frozenset()
    ceiling = limit.value * 60
    listing = ", ".join(repr(b) for b in sorted(breaks)) or "none are declared"
    for run, events in (_runs(context, tally) or {}).items():
        why = _untimed(events)
        if why is not None:
            tally.miss(why)
            continue
        tally.measured += 1
        work = sorted(
            (t for t in _timed(events) if _event_type(t[2]) not in breaks),
            key=lambda t: (t[0], t[1], t[2].row.line),
        )
        worked, crossing = _worked_time(work, ceiling)
        if crossing is None:
            continue
        findings.append(
            _finding(
                limit,
                file="run_events.txt",
                row=crossing.row.line,
                field="end_time",
                message=(
                    f"run_events.txt row {crossing.row.line}: run {_run_label(run)} works "
                    f"{_hm(worked)} across its events other than breaks, and passes the "
                    f"limit during this one. The agency's policy sets {limit.setting} "
                    f"({_hm(ceiling)}). Worked time leaves out events whose event_type is "
                    f"in break-event-types ({listing}) and counts overlapping events once."
                ),
                value=str(worked // 60),
                expected=f"<= {limit.value}",
            )
        )
    return findings, tally.measurement()


def _max_piece(
    context: ValidationContext, limit: PolicyLimit, _policy: LocalPolicy
) -> _CheckResult:
    tally = _Tally(limit.rule.unit)
    findings: list[Finding] = []
    ceiling = limit.value * 60
    for run, events in (_runs(context, tally) or {}).items():
        pieces: dict[str, list[_Event]] = {}
        for event in events:
            piece_id = event.row.values.get("piece_id", "")
            if piece_id.strip():
                pieces.setdefault(piece_id, []).append(event)
        if not pieces:
            tally.miss(
                "no event in the run carries a piece_id, so it cannot be divided into pieces"
            )
            continue
        why = _untimed(e for piece in pieces.values() for e in piece)
        if why is not None:
            tally.miss(why)
            continue
        tally.measured += 1
        for piece_id, piece in pieces.items():
            timed = _timed(piece)
            first = min(timed, key=lambda t: (t[0], t[2].row.line))
            last = max(timed, key=lambda t: (t[1], -t[2].row.line))
            length = last[1] - first[0]
            if length <= ceiling:
                continue
            findings.append(
                _finding(
                    limit,
                    file="run_events.txt",
                    row=last[2].row.line,
                    field="end_time",
                    message=(
                        f"run_events.txt row {last[2].row.line}: piece {piece_id!r} of run "
                        f"{_run_label(run)} lasts {_hm(length)}, from "
                        f"{first[2].row.values.get('start_time', '')} (row "
                        f"{first[2].row.line}) to {last[2].row.values.get('end_time', '')}. "
                        f"The agency's policy sets {limit.setting} ({_hm(ceiling)}), measured "
                        "over the events that share this piece_id."
                    ),
                    value=str(length // 60),
                    expected=f"<= {limit.value}",
                )
            )
    return findings, tally.measurement()


def _min_break(context: ValidationContext, limit: PolicyLimit, policy: LocalPolicy) -> _CheckResult:
    tally = _Tally(limit.rule.unit)
    findings: list[Finding] = []
    feed = context.package.get("run_events.txt")
    breaks = policy.break_event_types or frozenset()
    floor = limit.value * 60
    if feed is None:
        tally.absent = "the package has no run_events.txt"
        return findings, tally.measurement()
    candidates = [e for e in context.events if _event_type(e) in breaks]
    gap = _read_gap(feed)
    if gap is not None:
        tally.absent = gap
        tally.miss(gap, len(candidates))
        return findings, tally.measurement()
    if not candidates:
        tally.absent = "no event in run_events.txt has an event_type listed in break-event-types"
    for event in candidates:
        if event.start is None or event.end is None:
            tally.miss("a break has no readable start_time or end_time")
            continue
        if event.end < event.start:
            tally.miss("a break ends before it starts (see TODS-E401)")
            continue
        tally.measured += 1
        length = event.end - event.start
        if length >= floor:
            continue
        findings.append(
            _finding(
                limit,
                file="run_events.txt",
                row=event.row.line,
                field="end_time",
                message=(
                    f"run_events.txt row {event.row.line}: this break (event_type "
                    f"{_event_type(event)!r}) in run {_run_label(event.run)} lasts "
                    f"{length // 60} minute(s), {event.row.values.get('start_time', '')} to "
                    f"{event.row.values.get('end_time', '')}. The agency's policy sets "
                    f"{limit.setting}."
                ),
                value=str(length // 60),
                expected=f">= {limit.value}",
            )
        )
    return findings, tally.measurement()


def _max_spread(
    context: ValidationContext, limit: PolicyLimit, _policy: LocalPolicy
) -> _CheckResult:
    tally = _Tally(limit.rule.unit)
    findings: list[Finding] = []
    ceiling = limit.value * 60
    for run, events in (_runs(context, tally) or {}).items():
        why = _untimed(events)
        if why is not None:
            tally.miss(why)
            continue
        tally.measured += 1
        timed = _timed(events)
        first = min(timed, key=lambda t: (t[0], t[2].row.line))
        last = max(timed, key=lambda t: (t[1], -t[2].row.line))
        spread = last[1] - first[0]
        if spread <= ceiling:
            continue
        findings.append(
            _finding(
                limit,
                file="run_events.txt",
                row=last[2].row.line,
                field="end_time",
                message=(
                    f"run_events.txt row {last[2].row.line}: run {_run_label(run)} spreads "
                    f"{_hm(spread)}, from {first[2].row.values.get('start_time', '')} "
                    f"(row {first[2].row.line}) to {last[2].row.values.get('end_time', '')} "
                    f"(row {last[2].row.line}). The agency's policy sets {limit.setting} "
                    f"({_hm(ceiling)}), measured from the earliest start_time to the latest "
                    "end_time in the run."
                ),
                value=str(spread // 60),
                expected=f"<= {limit.value}",
            )
        )
    return findings, tally.measurement()


def _dates_by_employee(feed: FeedFile) -> dict[str, dict[date | None, int]]:
    """employee_id -> date -> the first row assigning that employee that day.

    A None key records that one of the employee's dates could not be read, which
    makes every streak of theirs unknowable: the unreadable date could join two
    short runs of days into a long one.
    """
    by_employee: dict[str, dict[date | None, int]] = {}
    for row in feed.rows:
        employee = row.values.get("employee_id", "")
        if employee.strip():
            day = parse_gtfs_date(row.values.get("date", ""))
            by_employee.setdefault(employee, {}).setdefault(day, row.line)
    return by_employee


def _streaks(days: list[date]) -> list[list[date]]:
    """Runs of consecutive calendar days in sorted, distinct ``days``."""
    streaks: list[list[date]] = []
    for day in days:
        if streaks and (day - streaks[-1][-1]).days == 1:
            streaks[-1].append(day)
        else:
            streaks.append([day])
    return streaks


def _max_consecutive_days(
    context: ValidationContext, limit: PolicyLimit, _policy: LocalPolicy
) -> _CheckResult:
    tally = _Tally(limit.rule.unit)
    findings: list[Finding] = []
    feed = context.package.get("employee_run_dates.txt")
    if feed is None:
        tally.absent = "the package has no employee_run_dates.txt"
        return findings, tally.measurement()
    by_employee = _dates_by_employee(feed)
    gap = _read_gap(feed)
    if gap is not None:
        tally.absent = gap
        tally.miss(gap, len(by_employee))
        return findings, tally.measurement()
    for employee, rows_by_day in by_employee.items():
        if None in rows_by_day:
            tally.miss("a date assigned to the employee in employee_run_dates.txt is unreadable")
            continue
        tally.measured += 1
        for streak in _streaks(sorted(d for d in rows_by_day if d is not None)):
            if len(streak) <= limit.value:
                continue
            crossing = streak[limit.value]
            row = rows_by_day[crossing]
            findings.append(
                _finding(
                    limit,
                    file="employee_run_dates.txt",
                    row=row,
                    field="date",
                    message=(
                        f"employee_run_dates.txt row {row}: employee {employee!r} is assigned "
                        f"on {len(streak)} consecutive days, {streak[0]:%Y-%m-%d} to "
                        f"{streak[-1]:%Y-%m-%d}, and this row's date, {crossing:%Y-%m-%d}, is "
                        f"day {limit.value + 1}. The agency's policy sets {limit.setting}."
                    ),
                    value=str(len(streak)),
                    expected=f"<= {limit.value}",
                )
            )
    return findings, tally.measurement()


def _assigned_days(
    feed: FeedFile | None,
) -> tuple[dict[str, set[tuple[date, str]]], set[str]]:
    """block_id -> (date, service_id) pairs that have a vehicle, and blocks with an unreadable date.

    A block with an assignment row whose date cannot be read is not known to
    lack a vehicle on any given day, so its events are unmeasurable rather than
    reported: the unreadable row may be the assignment the check is looking for.
    """
    assigned: dict[str, set[tuple[date, str]]] = {}
    unreadable: set[str] = set()
    for row in feed.rows if feed is not None else []:
        block = row.values.get("block_id", "")
        day = parse_gtfs_date(row.values.get("date", ""))
        if day is None:
            unreadable.add(block)
            continue
        assigned.setdefault(block, set()).add((day, row.values.get("service_id", "")))
    return assigned, unreadable


def _revenue_target(
    event: _Event, gtfs: CompanionGTFS, unreadable_blocks: set[str]
) -> tuple[str, str, frozenset[date]] | str:
    """``(block_id, service_id, operating days)`` for a revenue event, or why it has none.

    The service is the trip's, from the companion trips.txt, not the run's: a
    vehicle is assigned to a block under the service its trips run on, and a
    supervisor's run under one service can ride a trip under another.
    """
    service = gtfs.trip_service.get(event.trip_id)
    if service is None:
        return (
            "the event's trip is not in the companion trips.txt, so its operating days are unknown"
        )
    block = event.row.values.get("block_id", "") or gtfs.trip_block.get(event.trip_id, "")
    if not block:
        return "the event names no block_id and its trip has no block_id in the companion trips.txt"
    if block in unreadable_blocks:
        return "a vehicle_assignments.txt row for the event's block has an unreadable date"
    days = gtfs.service_dates.get(service)
    if days is None:
        return "the supplemented calendars give no operating days for the trip's service_id"
    return block, service, days


def _revenue_assignment(
    context: ValidationContext, limit: PolicyLimit, _policy: LocalPolicy
) -> _CheckResult:
    tally = _Tally(limit.rule.unit)
    findings: list[Finding] = []
    gtfs = context.gtfs
    if gtfs is None:  # pragma: no cover - _status() skips this rule without a companion
        raise RuntimeError("LOCAL-P006 reached without a companion GTFS feed")
    runs_feed = context.package.get("run_events.txt")
    if runs_feed is None:
        tally.absent = "the package has no run_events.txt"
        return findings, tally.measurement()
    # A revenue event is one that carries a trip_id: the rule `stats` and
    # `pickdiff` use, read the same way (a non-empty value), so the three
    # cannot disagree about which events are revenue.
    revenue = [e for e in context.events if e.trip_id]
    assignments = context.package.get("vehicle_assignments.txt")
    for feed in (runs_feed, assignments):
        gap = None if feed is None else _read_gap(feed)
        if gap is not None:
            tally.absent = gap
            tally.miss(gap, len(revenue))
            return findings, tally.measurement()
    assigned, unreadable_blocks = _assigned_days(assignments)
    # (service_id, block_id) -> (first row, field, the days with no vehicle).
    gaps: dict[tuple[str, str], tuple[int, str, set[date]]] = {}
    for event in revenue:
        target = _revenue_target(event, gtfs, unreadable_blocks)
        if isinstance(target, str):
            tally.miss(target)
            continue
        block, service, days = target
        tally.measured += 1
        covered = {day for day, on in assigned.get(block, set()) if on in ("", service)}
        missing = days - covered
        if missing:
            field = "block_id" if event.row.values.get("block_id", "") else "trip_id"
            gaps.setdefault((service, block), (event.row.line, field, set()))[2].update(missing)
    no_file = " The package has no vehicle_assignments.txt." if assignments is None else ""
    for (service, block), (row, field, unassigned) in gaps.items():
        ordered = sorted(unassigned)
        sample = ", ".join(f"{d:%Y-%m-%d}" for d in ordered[:5])
        more = f", and {len(ordered) - 5} more" if len(ordered) > 5 else ""
        findings.append(
            _finding(
                limit,
                file="run_events.txt",
                row=row,
                field=field,
                message=(
                    f"run_events.txt row {row}: block {block!r} (service_id {service!r}) "
                    f"carries revenue events on {len(ordered)} day(s) its trips operate with no "
                    f"vehicle_assignments.txt row for the block: {sample}{more}.{no_file} The "
                    f"agency's policy sets {limit.setting}; a revenue event is one that carries "
                    "a trip_id, the rule `stats` and `pickdiff` use."
                ),
                value=str(len(ordered)),
                expected="0",
            )
        )
    return findings, tally.measurement()


_CHECKS: dict[str, Callable[[ValidationContext, PolicyLimit, LocalPolicy], _CheckResult]] = {
    "LOCAL-P001": _max_run,
    "LOCAL-P002": _max_piece,
    "LOCAL-P003": _min_break,
    "LOCAL-P004": _max_spread,
    "LOCAL-P005": _max_consecutive_days,
    "LOCAL-P006": _revenue_assignment,
}


def _status(local: LocalRule, context: ValidationContext) -> str:
    from .rules import (
        GTFS_CALENDARS,
        STATUS_RAN,
        STATUS_SKIPPED_NEEDS_GTFS,
        STATUS_SKIPPED_NEEDS_GTFS_TABLE,
        STATUS_SKIPPED_SPEC_VERSION,
    )
    from .schema import SPEC_VERSION

    # Every local rule reads v2.1.0's run_events.txt / employee_run_dates.txt /
    # vehicle_assignments.txt field names, as OPS-W001 does.
    if context.spec_version != SPEC_VERSION:
        return STATUS_SKIPPED_SPEC_VERSION
    if local.needs_gtfs:
        if context.gtfs is None:
            return STATUS_SKIPPED_NEEDS_GTFS
        if not set(GTFS_CALENDARS) & context.gtfs.present:
            return STATUS_SKIPPED_NEEDS_GTFS_TABLE
    return STATUS_RAN


def evaluate(
    context: ValidationContext, policy: LocalPolicy
) -> tuple[list[Finding], tuple[RuleOutcome, ...]]:
    """Evaluate every configured local rule; return findings and their outcomes.

    Outcomes come back in ``LOCAL_RULES`` order, one per configured rule and
    none for a rule the policy does not set, so the local band of the coverage
    manifest lists exactly what the agency asked for.
    """
    from .rules import STATUS_RAN, RuleOutcome

    findings: list[Finding] = []
    outcomes: list[RuleOutcome] = []
    for local in LOCAL_RULES:
        limit = policy.limit(local.id)
        if limit is None:
            continue
        status = _status(local, context)
        measurement = None
        if status == STATUS_RAN:
            found, measurement = _CHECKS[local.id](context, limit, policy)
            findings.extend(found)
        outcomes.append(
            RuleOutcome(
                id=local.id,
                severity=limit.severity,
                category=LOCAL_CATEGORY,
                status=status,
                measurement=measurement,
                policy_setting=limit.setting,
            )
        )
    return findings, tuple(outcomes)


__all__ = [
    "AGENCY_POLICY_NOTE",
    "BREAK_TYPES_KEY",
    "DECISION_RECORD",
    "LOCAL_CATEGORY",
    "LOCAL_NAMESPACE",
    "LOCAL_RULES",
    "LOCAL_RULES_BY_ID",
    "LOCAL_RULES_BY_KEY",
    "LocalPolicy",
    "LocalRule",
    "PolicyLimit",
    "as_rule",
    "evaluate",
]
