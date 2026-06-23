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

from .loader import FeedFile, Package
from .schema import GTFS_PRIMARY_KEYS

_WEEKDAY_FIELDS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_gtfs_date(value: str) -> date | None:
    """Parse a GTFS YYYYMMDD date, returning None if malformed."""
    if len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def merge_supplement(
    base: FeedFile | None,
    supplement: FeedFile | None,
    primary_key: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, str]]:
    """Compute effective rows keyed by primary key.

    Rows whose primary-key fields are blank or missing are skipped here; the
    field rules report those problems on the supplement file itself.
    """
    effective: dict[tuple[str, ...], dict[str, str]] = {}
    if base is not None:
        for row in base.rows:
            key = tuple(row.values.get(f, "") for f in primary_key)
            if any(v == "" for v in key):
                continue
            effective[key] = dict(row.values)
    if supplement is not None:
        for row in supplement.rows:
            key = tuple(row.values.get(f, "") for f in primary_key)
            if any(v == "" for v in key):
                continue
            if row.values.get("TODS_delete", "") == "1":
                effective.pop(key, None)
                continue
            if key in effective:
                target = effective[key]
                for name, value in row.values.items():
                    if name == "TODS_delete" or value == "":
                        continue
                    target[name] = value
            else:
                effective[key] = {k: v for k, v in row.values.items() if k != "TODS_delete"}
    return effective


@dataclass
class CompanionGTFS:
    """The supplemented GTFS slices that TODS references resolve against."""

    source: str
    # Which GTFS base files were actually present (affects what can be checked).
    present: set[str] = field(default_factory=set)
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


def build_companion(gtfs: Package | None, tods: Package, source: str) -> CompanionGTFS:
    """Build the supplemented GTFS view.

    ``gtfs`` is the package holding the GTFS base files (may be the same
    package as ``tods`` when the feed ships both together); supplements always
    come from the TODS package.
    """
    companion = CompanionGTFS(source=source)

    def effective(base_name: str) -> dict[tuple[str, ...], dict[str, str]]:
        base = gtfs.get(base_name) if gtfs is not None else None
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
    stops_by_trip: dict[str, list[tuple[int, str]]] = {}
    for (trip_id, sequence), st_row in stop_times.items():
        try:
            order = int(sequence)
        except ValueError:
            continue
        stops_by_trip.setdefault(trip_id, []).append((order, st_row.get("stop_id", "")))
    for trip_id, ordered in stops_by_trip.items():
        ordered.sort()
        companion.trip_first_stop[trip_id] = ordered[0][1]
        companion.trip_last_stop[trip_id] = ordered[-1][1]

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
