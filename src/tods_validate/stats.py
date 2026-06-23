"""Descriptive statistics for a TODS feed.

Validation answers "is this feed correct?"; this answers "what is in it?" —
counts a researcher or analyst wants before diving in. These are facts, not a
quality score: a feed with fewer runs is not "worse". The optional coverage
figures, when a companion GTFS feed is available, show how much of the GTFS is
described operationally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .gtfs_companion import build_companion, parse_gtfs_date
from .loader import load_package
from .rules.fields import parse_time


@dataclass
class FeedStats:
    source: str
    run_events: int = 0
    runs: int = 0
    employees: int = 0
    employee_assignments: int = 0
    vehicles: int = 0
    vehicle_assignments: int = 0
    distinct_blocks: int = 0
    trip_events: int = 0
    deadhead_events: int = 0
    revenue_minutes: int = 0
    nonrevenue_minutes: int = 0
    # Populated only when a companion GTFS feed is available.
    gtfs_trips: int | None = None
    trips_with_run_event: int | None = None
    trip_coverage_pct: float | None = None
    gtfs_blocks: int | None = None
    blocks_with_vehicle: int | None = None
    # Operational profile: which files shipped, and the span of dated assignments.
    files_present: tuple[str, ...] = ()
    service_date_range: tuple[str, str] | None = None


def _event_minutes(start: str, end: str) -> int:
    s, e = parse_time(start), parse_time(end)
    if s is None or e is None or e < s:
        return 0
    return (e - s) // 60


def collect_stats(
    path: str | Path, gtfs_path: str | Path | None = None, encoding: str | None = None
) -> FeedStats:
    package = load_package(path, encoding=encoding)
    stats = FeedStats(source=package.source)

    run_events = package.get("run_events.txt")
    runs: set[tuple[str, str]] = set()
    covered_trips: set[str] = set()
    event_blocks: set[str] = set()
    if run_events is not None:
        stats.run_events = len(run_events.rows)
        for row in run_events.rows:
            runs.add((row.values.get("service_id", ""), row.values.get("run_id", "")))
            trip_id = row.values.get("trip_id", "")
            minutes = _event_minutes(
                row.values.get("start_time", ""), row.values.get("end_time", "")
            )
            if trip_id:
                stats.trip_events += 1
                stats.revenue_minutes += minutes
                covered_trips.add(trip_id)
            else:
                stats.deadhead_events += 1
                stats.nonrevenue_minutes += minutes
            block = row.values.get("block_id", "")
            if block:
                event_blocks.add(block)
    runs.discard(("", ""))
    stats.runs = len({r for r in runs if all(r)})

    erd = package.get("employee_run_dates.txt")
    if erd is not None:
        stats.employee_assignments = len(erd.rows)
        stats.employees = len({r.values.get("employee_id", "") for r in erd.rows} - {""})

    vehicles = package.get("vehicles.txt")
    if vehicles is not None:
        stats.vehicles = len(vehicles.rows)

    va = package.get("vehicle_assignments.txt")
    assigned_blocks: set[str] = set()
    if va is not None:
        stats.vehicle_assignments = len(va.rows)
        assigned_blocks = {r.values.get("block_id", "") for r in va.rows} - {""}

    stats.distinct_blocks = len(event_blocks | assigned_blocks)

    companion = None
    from .schema import GTFS_FILENAMES

    if gtfs_path is not None:
        gtfs_pkg = load_package(gtfs_path, encoding=encoding)
        companion = build_companion(gtfs_pkg, package, str(gtfs_path))
    elif any(name in GTFS_FILENAMES for name in package.files):
        companion = build_companion(package, package, package.source)

    if companion is not None:
        all_trips = set(companion.trip_service)
        stats.gtfs_trips = len(all_trips)
        stats.trips_with_run_event = len(covered_trips & all_trips)
        if all_trips:
            stats.trip_coverage_pct = round(100 * stats.trips_with_run_event / len(all_trips), 1)
        all_blocks = set(companion.block_ids)
        stats.gtfs_blocks = len(all_blocks)
        stats.blocks_with_vehicle = len(assigned_blocks & all_blocks)

    stats.files_present = tuple(sorted(package.files))
    dated: list[str] = []
    for fname in ("vehicle_assignments.txt", "employee_run_dates.txt"):
        feed = package.get(fname)
        if feed is not None and "date" in feed.headers:
            dated.extend(
                value
                for value in (row.values.get("date", "") for row in feed.rows)
                if parse_gtfs_date(value) is not None
            )
    if dated:
        stats.service_date_range = (min(dated), max(dated))

    return stats


def stats_to_dict(stats: FeedStats) -> dict[str, object]:
    return asdict(stats)


def _stat_rows(stats: FeedStats) -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    if stats.service_date_range is not None:
        start, end = stats.service_date_range
        rows.append(("Date range", f"{start} to {end}"))
    if stats.files_present:
        rows.append(
            ("Files present", f"{len(stats.files_present)}: {', '.join(stats.files_present)}")
        )
    rows.extend(
        [
            ("Run events", stats.run_events),
            ("Distinct runs", stats.runs),
            ("Trip (revenue) events", stats.trip_events),
            ("Deadhead/other events", stats.deadhead_events),
            ("Revenue minutes", stats.revenue_minutes),
            ("Non-revenue minutes", stats.nonrevenue_minutes),
            ("Employees", stats.employees),
            ("Employee assignments", stats.employee_assignments),
            ("Vehicles", stats.vehicles),
            ("Vehicle assignments", stats.vehicle_assignments),
            ("Distinct blocks", stats.distinct_blocks),
        ]
    )
    if stats.gtfs_trips is not None:
        rows.extend(
            [
                ("GTFS trips", stats.gtfs_trips),
                ("Trips with a run event", stats.trips_with_run_event),
                ("Trip coverage", f"{stats.trip_coverage_pct}%"),
                ("GTFS blocks", stats.gtfs_blocks),
                ("Blocks with a vehicle", stats.blocks_with_vehicle),
            ]
        )
    return rows


def render_stats_text(stats: FeedStats) -> str:
    lines = [f"tods-validate stats: {stats.source}", ""]
    rows = _stat_rows(stats)
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        lines.append(f"  {label.ljust(width)}  {value}")
    return "\n".join(lines)


def render_stats_markdown(stats: FeedStats) -> str:
    """A feed profile suitable for pasting into an issue or working-group thread."""
    lines = [f"# TODS feed profile: {stats.source}", "", "| Metric | Value |", "| --- | --- |"]
    lines.extend(f"| {label} | {value} |" for label, value in _stat_rows(stats))
    return "\n".join(lines)
