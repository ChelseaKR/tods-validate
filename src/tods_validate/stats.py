"""Descriptive statistics for a TODS feed.

Validation answers "is this feed correct?"; this answers "what is in it?" —
counts a researcher or analyst wants before diving in. These are facts, not a
quality score: a feed with fewer runs is not "worse". The optional coverage
figures, when a companion GTFS feed is available, show how much of the GTFS is
described operationally.
"""

from __future__ import annotations

import typing
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .gtfs_companion import build_companion, parse_gtfs_date
from .loader import PackageNotFoundError, load_package
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
    # Set instead of the fields above when the feed could not be loaded at all.
    # Mirrors how `batch` records a per-feed load failure without aborting the
    # whole run; every numeric field above stays at its zero/None default.
    error: str | None = None


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


# The label -> field-name mapping behind every per-feed metric row. Shared by
# the single-feed renderers below and the cross-feed comparison renderers, so
# a label only needs to be spelled once.
_ROW_SPECS: tuple[tuple[str, str], ...] = (
    ("Run events", "run_events"),
    ("Distinct runs", "runs"),
    ("Trip (revenue) events", "trip_events"),
    ("Deadhead/other events", "deadhead_events"),
    ("Revenue minutes", "revenue_minutes"),
    ("Non-revenue minutes", "nonrevenue_minutes"),
    ("Employees", "employees"),
    ("Employee assignments", "employee_assignments"),
    ("Vehicles", "vehicles"),
    ("Vehicle assignments", "vehicle_assignments"),
    ("Distinct blocks", "distinct_blocks"),
)

_GTFS_ROW_SPECS: tuple[tuple[str, str], ...] = (
    ("GTFS trips", "gtfs_trips"),
    ("Trips with a run event", "trips_with_run_event"),
    ("GTFS blocks", "gtfs_blocks"),
    ("Blocks with a vehicle", "blocks_with_vehicle"),
)


def _stat_rows(stats: FeedStats) -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    if stats.service_date_range is not None:
        start, end = stats.service_date_range
        rows.append(("Date range", f"{start} to {end}"))
    if stats.files_present:
        rows.append(
            ("Files present", f"{len(stats.files_present)}: {', '.join(stats.files_present)}")
        )
    rows.extend((label, getattr(stats, field_name)) for label, field_name in _ROW_SPECS)
    if stats.gtfs_trips is not None:
        rows.append(("GTFS trips", stats.gtfs_trips))
        rows.append(("Trips with a run event", stats.trips_with_run_event))
        rows.append(("Trip coverage", f"{stats.trip_coverage_pct}%"))
        rows.append(("GTFS blocks", stats.gtfs_blocks))
        rows.append(("Blocks with a vehicle", stats.blocks_with_vehicle))
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


# --- Cross-feed comparison -------------------------------------------------
#
# `stats` on a single feed answers "what is in it?"; comparing several feeds
# answers "how do these feeds differ?" — useful for a researcher sizing up an
# agency portfolio or an oversight body spot-checking submissions. Like
# single-feed stats, these are facts, not a score: a smaller feed is not
# "worse".


def collect_cross_stats(
    paths: typing.Sequence[str | Path],
    gtfs_path: str | Path | None = None,
    encoding: str | None = None,
) -> list[FeedStats]:
    """Run `collect_stats` per path, recording (not raising on) load failures.

    Mirrors `batch`'s error handling: one unreadable feed among several is
    reported in place, not a reason to abort the whole comparison.
    """
    results: list[FeedStats] = []
    for path in paths:
        try:
            results.append(collect_stats(path, gtfs_path, encoding))
        except PackageNotFoundError as exc:
            results.append(FeedStats(source=str(path), error=str(exc)))
    return results


def _numeric_field_names() -> list[str]:
    """FeedStats field names typed as int/float (optionally `| None`).

    Enumerated from the dataclass itself, rather than hardcoded, so a new
    numeric field on FeedStats is picked up by aggregation automatically.
    """
    hints = typing.get_type_hints(FeedStats)
    names: list[str] = []
    for f in fields(FeedStats):
        hint = hints[f.name]
        args = typing.get_args(hint) or (hint,)
        non_none = tuple(a for a in args if a is not type(None))
        if non_none and all(a in (int, float) for a in non_none):
            names.append(f.name)
    return names


def aggregate_stats(feeds: list[FeedStats]) -> dict[str, object]:
    """Totals, means, and min/max across the numeric FeedStats fields.

    Feeds that failed to load (``error`` set) are excluded from the numbers
    but counted in ``error_count``, so a bad path among several doesn't skew
    the aggregate toward zero.
    """
    ok = [f for f in feeds if f.error is None]
    metrics: dict[str, object] = {}
    for name in _numeric_field_names():
        values = [v for f in ok for v in (getattr(f, name),) if v is not None]
        if not values:
            continue
        metrics[name] = {
            "total": sum(values),
            "mean": round(sum(values) / len(values), 2),
            "min": min(values),
            "max": max(values),
        }
    return {
        "feed_count": len(ok),
        "error_count": len(feeds) - len(ok),
        "metrics": metrics,
    }


def comparison_to_dict(feeds: list[FeedStats]) -> dict[str, object]:
    return {
        "feeds": [stats_to_dict(f) for f in feeds],
        "aggregate": aggregate_stats(feeds),
    }


def _comparison_rows(feeds: list[FeedStats]) -> list[tuple[str, list[object]]]:
    rows: list[tuple[str, list[object]]] = []
    rows.append(("Status", [f"error: {f.error}" if f.error else "ok" for f in feeds]))
    if any(f.service_date_range is not None for f in feeds):
        rows.append(
            (
                "Date range",
                [
                    f"{f.service_date_range[0]} to {f.service_date_range[1]}"
                    if f.service_date_range is not None
                    else "—"
                    for f in feeds
                ],
            )
        )
    if any(f.files_present for f in feeds):
        rows.append(("Files present", [len(f.files_present) or "—" for f in feeds]))
    for label, field_name in _ROW_SPECS:
        rows.append((label, ["—" if f.error else getattr(f, field_name) for f in feeds]))
    if any(f.gtfs_trips is not None for f in feeds):
        rows.append(
            (
                "GTFS trips",
                [f.gtfs_trips if f.gtfs_trips is not None else "—" for f in feeds],
            )
        )
        rows.append(
            (
                "Trips with a run event",
                [
                    f.trips_with_run_event if f.trips_with_run_event is not None else "—"
                    for f in feeds
                ],
            )
        )
        rows.append(
            (
                "Trip coverage",
                [
                    f"{f.trip_coverage_pct}%" if f.trip_coverage_pct is not None else "—"
                    for f in feeds
                ],
            )
        )
        rows.append(
            ("GTFS blocks", [f.gtfs_blocks if f.gtfs_blocks is not None else "—" for f in feeds])
        )
        rows.append(
            (
                "Blocks with a vehicle",
                [
                    f.blocks_with_vehicle if f.blocks_with_vehicle is not None else "—"
                    for f in feeds
                ],
            )
        )
    return rows


_AggRow = tuple[str, tuple[object, object, object, object]]


def _aggregate_rows(feeds: list[FeedStats]) -> tuple[dict[str, object], list[_AggRow]]:
    aggregate = aggregate_stats(feeds)
    metrics = typing.cast("dict[str, dict[str, object]]", aggregate["metrics"])
    label_by_field = {field_name: label for label, field_name in _ROW_SPECS}
    label_by_field.update({field_name: label for label, field_name in _GTFS_ROW_SPECS})
    label_by_field["trip_coverage_pct"] = "Trip coverage %"
    rows: list[_AggRow] = [
        (label_by_field.get(name, name), (m["total"], m["mean"], m["min"], m["max"]))
        for name, m in metrics.items()
        if name in label_by_field
    ]
    return aggregate, rows


def render_comparison_text(feeds: list[FeedStats]) -> str:
    lines = [f"tods-validate stats comparison: {len(feeds)} feed(s)", ""]
    header = ["Metric"] + [f.source for f in feeds]
    rows = _comparison_rows(feeds)
    label_width = max(len(header[0]), *(len(r[0]) for r in rows))
    value_widths = [
        max(len(header[i + 1]), *(len(str(r[1][i])) for r in rows)) for i in range(len(feeds))
    ]
    col_widths = [label_width, *value_widths]
    lines.append("  " + "  ".join(h.ljust(w) for h, w in zip(header, col_widths, strict=True)))
    for label, values in rows:
        cells = [label] + [str(v) for v in values]
        lines.append("  " + "  ".join(c.ljust(w) for c, w in zip(cells, col_widths, strict=True)))

    aggregate, agg_rows = _aggregate_rows(feeds)
    lines.append("")
    lines.append(
        f"Aggregate (feeds with data: {aggregate['feed_count']}, "
        f"unreadable: {aggregate['error_count']})"
    )
    if agg_rows:
        agg_header = ["Metric", "Total", "Mean", "Min", "Max"]
        agg_widths = [
            max(len(agg_header[i]), *(len(str(r[1][i - 1])) if i else len(r[0]) for r in agg_rows))
            for i in range(len(agg_header))
        ]
        lines.append(
            "  " + "  ".join(h.ljust(w) for h, w in zip(agg_header, agg_widths, strict=True))
        )
        for label, (total, mean, lo, hi) in agg_rows:
            cells = [label, str(total), str(mean), str(lo), str(hi)]
            lines.append(
                "  " + "  ".join(c.ljust(w) for c, w in zip(cells, agg_widths, strict=True))
            )
    return "\n".join(lines)


def render_comparison_markdown(feeds: list[FeedStats]) -> str:
    """A multi-feed comparison suitable for pasting into an issue or thread."""
    lines = [f"# TODS feed comparison: {len(feeds)} feed(s)", ""]
    header = ["Metric"] + [f.source for f in feeds]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for label, values in _comparison_rows(feeds):
        lines.append("| " + " | ".join([label] + [str(v) for v in values]) + " |")

    aggregate, agg_rows = _aggregate_rows(feeds)
    lines.append("")
    lines.append(
        f"## Aggregate (feeds with data: {aggregate['feed_count']}, "
        f"unreadable: {aggregate['error_count']})"
    )
    lines.append("")
    if agg_rows:
        lines.append("| Metric | Total | Mean | Min | Max |")
        lines.append("| --- | --- | --- | --- | --- |")
        for label, (total, mean, lo, hi) in agg_rows:
            lines.append(f"| {label} | {total} | {mean} | {lo} | {hi} |")
    return "\n".join(lines)
