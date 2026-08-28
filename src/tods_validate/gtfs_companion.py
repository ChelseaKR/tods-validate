"""Load the companion GTFS feed and apply TODS supplement files.

TODS IDs resolve against the GTFS feed *after* supplements are applied (the
spec calls this "TODS-Supplemented GTFS"). Supplement evaluation follows the
spec's "Supplement Files > Evaluation" section:

1. PK matches and TODS_delete == "1": remove the GTFS row.
2. PK matches otherwise: non-empty supplement values overwrite GTFS values.
3. PK does not match: add the whole row.

Only the slices of GTFS that TODS references are modeled here (trips, stops,
calendars). This is not a GTFS validator; for that, use MobilityData's
gtfs-validator on the supplemented feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .loader import BLOCKING_PROBLEM_CODES, FeedFile, Package
from .schema import GTFS_PRIMARY_KEYS
from .supplement import apply_supplement

_WEEKDAY_FIELDS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_gtfs_date(value: str) -> date | None:
    """Parse a GTFS YYYYMMDD date, returning None if malformed."""
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def merge_supplement(  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    base: FeedFile | None,
    supplement: FeedFile | None,
    primary_key: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, str]]:
    """Compute effective rows keyed by primary key.

    Rows whose primary-key fields are blank or missing are skipped here; the
    field rules report those problems on the supplement file itself.

    Delegates to the shared engine in ``supplement.py`` (also used by
    ``merge._merge_file``) so the validation view and the materialized merge
    can never disagree about which keys survive and their values.
    """
    return apply_supplement(base, supplement, primary_key).rows


@dataclass
class CompanionGTFS:
    """The supplemented GTFS slices that TODS references resolve against."""

    source: str
    # Which GTFS base files were actually present (affects what can be checked).
    present: set[str] = field(default_factory=set)
    # Base files that were in the package but could not be parsed at all (see
    # loader.BLOCKING_PROBLEM_CODES), keyed to why. Treated as absent from
    # `present` -- an unreadable file parsed no rows, so treating it as
    # present would make every reference into it read as dangling instead of
    # unresolvable (#125). TODS-W302 discloses the reason from this map
    # rather than reporting the table simply missing.
    unreadable: dict[str, str] = field(default_factory=dict)
    # Base files that parsed but did not read in full (see
    # loader.DEGRADING_PROBLEM_CODES), keyed to why. Treated as absent from
    # `present` for the same reason as `unreadable`: the reader holds an
    # incomplete set of IDs, and an ID it dropped is indistinguishable from an
    # ID the feed never had, so every reference to a dropped ID would be
    # reported as a dangling reference against the *TODS* file. Kept in its own
    # map rather than folded into `unreadable` because the two say different
    # things to a producer: an unreadable file has to be re-exported, while a
    # file that read but lost values has a named row or column to fix.
    # TODS-W302 discloses this map. See ADR 0007.
    degraded: dict[str, str] = field(default_factory=dict)
    trip_service: dict[str, str] = field(default_factory=dict)
    trip_block: dict[str, str] = field(default_factory=dict)
    stop_ids: set[str] = field(default_factory=set)
    route_ids: set[str] = field(default_factory=set)
    service_ids: set[str] = field(default_factory=set)
    block_services: dict[str, set[str]] = field(default_factory=dict)
    # First and last stop_id of each trip, from stop_times after supplements,
    # used to check run_events start/end locations against the trip endpoints.
    trip_first_stop: dict[str, str] = field(default_factory=dict)
    trip_last_stop: dict[str, str] = field(default_factory=dict)
    # The first stop's departure_time and the last stop's arrival_time, used to
    # check run_events start/end times against the trip's scheduled span. Each
    # falls back to the other time when one is blank, as GTFS permits.
    trip_first_departure: dict[str, str] = field(default_factory=dict)
    trip_last_arrival: dict[str, str] = field(default_factory=dict)
    # Operating dates per service_id, from calendar + calendar_dates after
    # supplements. Only populated for services whose calendar rows parse.
    service_dates: dict[str, frozenset[date]] = field(default_factory=dict)
    # Primary keys present in each GTFS base file *before* supplements, used
    # to check that TODS_delete rows target something that exists.
    base_keys: dict[str, set[tuple[str, ...]]] = field(default_factory=dict)

    @property
    def block_ids(self) -> set[str]:
        return set(self.block_services)


def _calendar_dates_for(
    calendar: dict[tuple[str, ...], dict[str, str]],
    calendar_dates: dict[tuple[str, ...], dict[str, str]],
) -> dict[str, frozenset[date]]:
    dates: dict[str, set[date]] = {}
    for row in calendar.values():
        service_id = row.get("service_id", "")
        start = parse_gtfs_date(row.get("start_date", ""))
        end = parse_gtfs_date(row.get("end_date", ""))
        if not service_id or start is None or end is None or end < start:
            continue
        active = {i for i, name in enumerate(_WEEKDAY_FIELDS) if row.get(name, "") == "1"}
        days = dates.setdefault(service_id, set())
        current = start
        while current <= end:
            if current.weekday() in active:
                days.add(current)
            current += timedelta(days=1)
    for row in calendar_dates.values():
        service_id = row.get("service_id", "")
        day = parse_gtfs_date(row.get("date", ""))
        if not service_id or day is None:
            continue
        exception = row.get("exception_type", "")
        if exception == "1":
            dates.setdefault(service_id, set()).add(day)
        elif exception == "2":
            dates.setdefault(service_id, set()).discard(day)
    return {k: frozenset(v) for k, v in dates.items()}


def _blocking_reason(feed: FeedFile) -> str:
    """The LoadProblem message that made ``feed`` unreadable.

    Callers only reach here when ``feed.readable`` is False, which by
    definition means one of BLOCKING_PROBLEM_CODES is present.
    """
    for problem in feed.problems:
        if problem.code in BLOCKING_PROBLEM_CODES:
            return problem.message
    raise AssertionError(f"{feed.name}: not readable but no blocking problem recorded")


def _degraded_reason(feed: FeedFile) -> str:
    """Why ``feed`` parsed but did not read in full, as one sentence.

    Callers only reach here when ``feed.readable`` is True and
    ``feed.fully_read`` is False, so at least one problem is recorded and none
    of them is blocking. The first message is quoted and the rest counted: a
    producer needs one concrete row or column to open the file at, and the
    count so the report does not imply that fixing the first one is the whole
    job.
    """
    if not feed.problems:  # pragma: no cover -- guarded by the caller
        raise AssertionError(f"{feed.name}: not fully read but no problem recorded")
    first = feed.problems[0].message
    rest = len(feed.problems) - 1
    if rest:
        return f"{first} And {rest} further problem(s) in the same file."
    return first


def _resolve_base(
    gtfs: Package | None, base_name: str, companion: CompanionGTFS
) -> FeedFile | None:
    """The base FeedFile to read for ``base_name``, or None if it cannot be trusted.

    Three cases collapse to None here, and they collapse for one reason: in
    each, the rows this reader holds for ``base_name`` are not the rows the
    file contains, so resolving a reference against them would answer a
    question the reader cannot answer.

    - Absent from the package. Already handled correctly everywhere.
    - Present but unparseable (no headers, no rows). Folded into the absent
      case with the reason recorded in ``companion.unreadable`` (#125).
    - Present and parsed, but not read in full: a ragged row or a duplicated
      column means some values were dropped. Folded in the same way, with the
      reason recorded in ``companion.degraded``.

    The third case is the one that used to fail open. A dropped ``trip_id`` is
    not reported anywhere -- TODS-E103/E104/E105 scan the TODS package, never
    the companion feed -- so the reader silently held a short list of trips,
    every rule that reads trips still recorded ``ran`` in the coverage
    manifest, and a run event naming a real trip was reported as TODS-E307,
    an ERROR against the producer's TODS file for a defect in their GTFS file.
    See ADR 0007.
    """
    base = gtfs.get(base_name) if gtfs is not None else None
    if base is None:
        return None
    if not base.readable:
        companion.unreadable[base_name] = _blocking_reason(base)
        return None
    if not base.fully_read:
        companion.degraded[base_name] = _degraded_reason(base)
        return None
    return base


def build_companion(gtfs: Package | None, tods: Package, source: str) -> CompanionGTFS:
    """Build the supplemented GTFS view.

    ``gtfs`` is the package holding the GTFS base files (may be the same
    package as ``tods`` when the feed ships both together); supplements always
    come from the TODS package.
    """
    companion = CompanionGTFS(source=source)

    def effective(base_name: str) -> dict[tuple[str, ...], dict[str, str]]:
        base = _resolve_base(gtfs, base_name, companion)
        supplement = tods.get(base_name.removesuffix(".txt") + "_supplement.txt")
        pk = GTFS_PRIMARY_KEYS[base_name]
        if base is not None:
            companion.present.add(base_name)
            keys = companion.base_keys.setdefault(base_name, set())
            for row in base.rows:
                key = tuple(row.values.get(f, "") for f in pk)
                if all(key):
                    keys.add(key)
        return merge_supplement(base, supplement, pk)

    trips = effective("trips.txt")
    for (trip_id,), row in trips.items():
        companion.trip_service[trip_id] = row.get("service_id", "")
        block_id = row.get("block_id", "")
        companion.trip_block[trip_id] = block_id
        if block_id:
            companion.block_services.setdefault(block_id, set()).add(row.get("service_id", ""))

    stop_times = effective("stop_times.txt")
    stops_by_trip: dict[str, list[tuple[int, str, str, str]]] = {}
    for (trip_id, sequence), st_row in stop_times.items():
        try:
            order = int(sequence)
        except ValueError:
            continue
        arrival = st_row.get("arrival_time", "")
        departure = st_row.get("departure_time", "")
        stops_by_trip.setdefault(trip_id, []).append(
            (order, st_row.get("stop_id", ""), arrival or departure, departure or arrival)
        )
    for trip_id, ordered in stops_by_trip.items():
        ordered.sort()
        companion.trip_first_stop[trip_id] = ordered[0][1]
        companion.trip_last_stop[trip_id] = ordered[-1][1]
        companion.trip_first_departure[trip_id] = ordered[0][3]
        companion.trip_last_arrival[trip_id] = ordered[-1][2]

    companion.stop_ids = {key[0] for key in effective("stops.txt")}
    companion.route_ids = {key[0] for key in effective("routes.txt")}

    calendar = effective("calendar.txt")
    calendar_dates = effective("calendar_dates.txt")
    companion.service_ids = {row.get("service_id", "") for row in calendar.values()} | {
        row.get("service_id", "") for row in calendar_dates.values()
    }
    companion.service_ids.discard("")
    companion.service_dates = _calendar_dates_for(calendar, calendar_dates)

    return companion
