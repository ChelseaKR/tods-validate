#!/usr/bin/env python3
"""Generate a seeded, clearly-labeled synthetic TODS+GTFS benchmark feed.

This produces *fake* data, structurally shaped like real transit operations
data, for performance and fuzz work (see ``scripts/benchmark.py``) and for
publishing reproducible release artifacts. It is never evidence about how
real feeds look — every package this script writes carries a loud
``SYNTHETIC.md`` label plus a ``synthetic_manifest.json`` recording the exact
seed and parameters, so any published number can be regenerated bit-for-bit.

Usage:

    python scripts/generate_feed.py --profile clean-100k --seed 1 --out dist/clean-100k.zip
    python scripts/generate_feed.py --trips 5000 --deadhead-pct 8 --seed 42 --out /tmp/feed
    python scripts/generate_feed.py --profile messy-export --seed 7 --out /tmp/messy

Profiles preset ``--trips``, ``--deadhead-pct``, and an internal error-injection
level; any of ``--trips``/``--runs``, ``--deadhead-pct``, or ``--seed`` passed
explicitly overrides the profile's value. ``--out`` may be a directory (files
written directly into it) or a path ending in ``.zip`` (a zip archive).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

TRIPS_PER_BLOCK = 4
STOPS_PER_TRIP = 3
STOP_DWELL_MINUTES = 12
TRIP_GAP_MINUTES = 10
SERVICE_DATE = "20260106"
CALENDAR_HEADER = (
    "service_id",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "start_date",
    "end_date",
)

# Preset (trips, deadhead_pct, inject_errors) tuples. `inject_errors` is the
# per-block probability [0, 1] of applying one deterministic mutation (a
# broken reference, a bad enum, a timing inversion, ...) drawn from
# `_MUTATIONS`, so "drifted" and "messy" feeds fail the same rule bands a
# real messy export would, without ever claiming to *be* one.
PROFILES: dict[str, dict[str, float]] = {
    "clean-100k": {"trips": 100_000, "deadhead_pct": 6.0, "inject_errors": 0.0},
    "drifted-gtfs": {"trips": 4_000, "deadhead_pct": 10.0, "inject_errors": 0.12},
    "messy-export": {"trips": 1_500, "deadhead_pct": 15.0, "inject_errors": 0.35},
}


def _fmt_time(total_minutes: int) -> str:
    hh, mm = divmod(total_minutes, 60)
    return f"{hh:02d}:{mm:02d}:00"


def _write(path: Path, header: tuple[str, ...] | list[str], rows: list[list[str]]) -> None:
    lines = [",".join(header)]
    lines.extend(",".join(row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass
class _Block:
    """Working state for one run/block while it is being assembled.

    Kept separate so error injection can target "this block's rows" right
    after they are built, without re-scanning the whole feed.
    """

    trips: list[list[str]]
    trips_supplement: list[list[str]]
    stop_times: list[list[str]]
    stop_times_supplement: list[list[str]]
    run_events: list[list[str]]
    employee_run_dates: list[list[str]]
    vehicles: list[list[str]]
    vehicle_assignments: list[list[str]]


# ---------------------------------------------------------------------------
# Error injection: each mutation corrupts one already-built block in place so
# the generated feed exercises the reference/semantic rule bands (TODS-x3xx,
# TODS-x4xx) instead of always validating clean. Deterministic given `rng`.
# ---------------------------------------------------------------------------


def _mutate_broken_trip_ref(block: _Block, rng: random.Random) -> None:
    candidates = [r for r in block.run_events if r[7]]  # trip_id column
    if candidates:
        rng.choice(candidates)[7] = "trip-ghost-does-not-exist"


def _mutate_broken_vehicle_ref(block: _Block, rng: random.Random) -> None:
    if block.vehicle_assignments:
        block.vehicle_assignments[0][3] = "vehicle-ghost-does-not-exist"


def _mutate_broken_block_ref(block: _Block, rng: random.Random) -> None:
    if block.vehicle_assignments:
        block.vehicle_assignments[0][2] = "BLOCK-GHOST-DOES-NOT-EXIST"


def _mutate_broken_employee_run_ref(block: _Block, rng: random.Random) -> None:
    if block.employee_run_dates:
        row = block.employee_run_dates[0]
        row[2] = f"{row[2]}-ghost"


def _mutate_unknown_service(block: _Block, rng: random.Random) -> None:
    for row in block.run_events:
        row[0] = "service-ghost-does-not-exist"


def _mutate_time_inversion(block: _Block, rng: random.Random) -> None:
    candidates = [r for r in block.run_events if r[7]]
    if candidates:
        row = rng.choice(candidates)
        row[9], row[12] = row[12], row[9]  # swap start_time/end_time


def _mutate_bad_enum(block: _Block, rng: random.Random) -> None:
    if block.run_events:
        rng.choice(block.run_events)[10] = "9"  # start_mid_trip must be '', 0, 1, or 2


def _mutate_missing_required(block: _Block, rng: random.Random) -> None:
    if block.run_events:
        rng.choice(block.run_events)[6] = ""  # event_type is required


def _mutate_trailing_whitespace(block: _Block, rng: random.Random) -> None:
    if block.employee_run_dates:
        row = block.employee_run_dates[0]
        row[3] = f"{row[3]}  "


def _mutate_duplicate_vehicle(block: _Block, rng: random.Random) -> None:
    if block.vehicles:
        block.vehicles.append(list(block.vehicles[0]))


_MUTATIONS = (
    _mutate_broken_trip_ref,
    _mutate_broken_vehicle_ref,
    _mutate_broken_block_ref,
    _mutate_broken_employee_run_ref,
    _mutate_unknown_service,
    _mutate_time_inversion,
    _mutate_bad_enum,
    _mutate_missing_required,
    _mutate_trailing_whitespace,
    _mutate_duplicate_vehicle,
)


def _build_block(
    block_index: int,
    trip_start: int,
    n_trips: int,
    stop_ids: list[str],
    rng: random.Random,
    deadhead_pct: float,
) -> _Block:
    block = _Block([], [], [], [], [], [], [], [])
    block_id = f"BLOCK-{block_index}"
    run_id = str(10000 + block_index * 10)
    vehicle_id = f"veh-{block_index}"
    route_id = "12" if block_index % 2 == 0 else "34"
    n_stops = len(stop_ids)

    block.vehicles.append(
        [vehicle_id, f"Synthetic Vehicle {block_index}", f"SYN-{block_index:06d}"]
    )
    block.vehicle_assignments.append([SERVICE_DATE, "daily", block_id, vehicle_id])
    block.employee_run_dates.append([SERVICE_DATE, "daily", run_id, f"emp-{block_index}"])

    add_deadhead = rng.random() < deadhead_pct / 100.0
    start_hour = 4 + (block_index % 18)
    cursor = start_hour * 60
    sequence = 10
    piece = 1

    def event(
        piece_id: str,
        job_type: str,
        event_type: str,
        trip_id: str,
        start_loc: str,
        start_min: int,
        end_loc: str,
        end_min: int,
        mid_trip: str = "",
    ) -> None:
        nonlocal sequence
        block.run_events.append(
            [
                "daily",
                run_id,
                str(sequence),
                piece_id,
                block_id if piece_id else "",
                job_type,
                event_type,
                trip_id,
                start_loc,
                _fmt_time(start_min),
                mid_trip,
                end_loc,
                _fmt_time(end_min),
                mid_trip,
            ]
        )
        sequence += 10

    first_stop = stop_ids[trip_start % n_stops]
    report_loc = "garage" if add_deadhead else first_stop
    event("", "Operator", "Report Time", "", report_loc, cursor - 15, report_loc, cursor - 15)
    event(
        "", "Operator", "Pre-Trip Inspection", "", report_loc, cursor - 10, report_loc, cursor - 5
    )

    if add_deadhead:
        deadhead_out = f"deadhead-{block_index}-out"
        block.trips_supplement.append(["deadheads", "daily", deadhead_out, block_id, "pull-out"])
        block.stop_times_supplement.extend(
            [
                [deadhead_out, _fmt_time(cursor - 5), _fmt_time(cursor - 5), "garage", "1"],
                [
                    deadhead_out,
                    _fmt_time(cursor - 2),
                    _fmt_time(cursor - 2),
                    "garage-waypoint",
                    "2",
                ],
                [deadhead_out, _fmt_time(cursor), _fmt_time(cursor), first_stop, "3"],
            ]
        )
        event(
            f"{run_id}-{piece}",
            "Operator",
            "Pull-Out",
            deadhead_out,
            "garage",
            cursor - 5,
            first_stop,
            cursor,
            "2",
        )

    # Every trip in a block shares one stop triple and alternates direction,
    # so consecutive events in the same run connect head-to-tail (trip j+1
    # starts where trip j ended) rather than teleporting across the feed.
    base_idx = trip_start % n_stops
    shared_stops = [stop_ids[(base_idx + k) % n_stops] for k in range(STOPS_PER_TRIP)]

    trip_ids: list[str] = []
    last_trip_end_stop = first_stop
    for j in range(n_trips):
        trip_id = f"t{trip_start + j}"
        trip_ids.append(trip_id)
        direction = j % 2
        headsign = "North" if direction == 0 else "South"
        route_stops = list(reversed(shared_stops)) if direction == 1 else list(shared_stops)
        block.trips.append([route_id, "daily", trip_id, headsign, str(direction), block_id])

        t = cursor
        for seq, stop_id in enumerate(route_stops, start=1):
            block.stop_times.append([trip_id, _fmt_time(t), _fmt_time(t), stop_id, str(seq)])
            t += STOP_DWELL_MINUTES
        trip_end = t - STOP_DWELL_MINUTES

        event(
            f"{run_id}-{piece}",
            "Operator",
            "Operator",
            trip_id,
            route_stops[0],
            cursor,
            route_stops[-1],
            trip_end,
            "2",
        )
        cursor = trip_end + TRIP_GAP_MINUTES
        last_trip_end_stop = route_stops[-1]

        if n_trips >= 4 and j == n_trips // 2 - 1:
            event(
                "", "Operator", "Break", "", route_stops[-1], cursor, route_stops[-1], cursor + 30
            )
            cursor += 30
            piece += 1

    last_stop = last_trip_end_stop
    if add_deadhead:
        deadhead_back = f"deadhead-{block_index}-back"
        block.trips_supplement.append(["deadheads", "daily", deadhead_back, block_id, "pull-back"])
        block.stop_times_supplement.extend(
            [
                [deadhead_back, _fmt_time(cursor), _fmt_time(cursor), last_stop, "1"],
                [
                    deadhead_back,
                    _fmt_time(cursor + 3),
                    _fmt_time(cursor + 3),
                    "garage-waypoint",
                    "2",
                ],
                [deadhead_back, _fmt_time(cursor + 6), _fmt_time(cursor + 6), "garage", "3"],
            ]
        )
        event(
            f"{run_id}-{piece}",
            "Operator",
            "Pull-Back",
            deadhead_back,
            last_stop,
            cursor,
            "garage",
            cursor + 6,
            "2",
        )

    return block


@dataclass
class FeedStats:
    trips: int
    blocks: int
    deadhead_blocks: int
    mutated_blocks: int
    stops: int
    seed: int
    deadhead_pct: float
    inject_errors: float
    profile: str | None


def build_feed(
    directory: Path,
    *,
    trips: int,
    deadhead_pct: float,
    seed: int,
    inject_errors: float,
    profile: str | None = None,
) -> FeedStats:
    """Write a fully-formed synthetic TODS+GTFS package into ``directory``.

    Deterministic: identical (trips, deadhead_pct, seed, inject_errors)
    always produce byte-identical output, via ``random.Random(seed)`` as the
    single source of randomness.
    """
    if trips < 1:
        raise ValueError("trips must be >= 1")
    if not 0.0 <= deadhead_pct <= 100.0:
        raise ValueError("deadhead_pct must be between 0 and 100")
    if not 0.0 <= inject_errors <= 1.0:
        raise ValueError("inject_errors must be between 0 and 1")

    directory.mkdir(parents=True, exist_ok=True)
    # random.Random(seed) here is for deterministic synthetic-data generation,
    # not a security-sensitive use of randomness (no secrets/tokens involved).
    rng = random.Random(seed)  # noqa: S311

    n_blocks = max(1, math.ceil(trips / TRIPS_PER_BLOCK))
    n_stops = max(10, min(2000, trips // 20 + 10))
    stop_ids = [f"stop-{i}" for i in range(1, n_stops + 1)]

    all_trips: list[list[str]] = []
    all_trips_supplement: list[list[str]] = []
    all_stop_times: list[list[str]] = []
    all_stop_times_supplement: list[list[str]] = []
    all_run_events: list[list[str]] = []
    all_employee_run_dates: list[list[str]] = []
    all_vehicles: list[list[str]] = []
    all_vehicle_assignments: list[list[str]] = []

    deadhead_blocks = 0
    mutated_blocks = 0
    trip_start = 0
    for block_index in range(n_blocks):
        n_trips = min(TRIPS_PER_BLOCK, trips - trip_start)
        if n_trips <= 0:
            break
        block = _build_block(block_index, trip_start, n_trips, stop_ids, rng, deadhead_pct)
        if block.trips_supplement:
            deadhead_blocks += 1

        if inject_errors > 0.0 and rng.random() < inject_errors:
            rng.choice(_MUTATIONS)(block, rng)
            mutated_blocks += 1

        all_trips.extend(block.trips)
        all_trips_supplement.extend(block.trips_supplement)
        all_stop_times.extend(block.stop_times)
        all_stop_times_supplement.extend(block.stop_times_supplement)
        all_run_events.extend(block.run_events)
        all_employee_run_dates.extend(block.employee_run_dates)
        all_vehicles.extend(block.vehicles)
        all_vehicle_assignments.extend(block.vehicle_assignments)
        trip_start += n_trips

    # A second service and a supervisor "Ride Check" run, matching the
    # shape of examples/sample-feed, so crew-specific supplement files
    # (calendar_supplement, calendar_dates_supplement) are always exercised
    # regardless of trip count. Timed relative to block 0's actual first
    # trip so it does not race the generated schedule.
    first_trip = all_trips[0][2]
    first_arrival = all_stop_times[0][1]
    first_departure = all_stop_times[0][1]
    first_hh, first_mm, _ = first_arrival.split(":")
    first_start_min = int(first_hh) * 60 + int(first_mm)
    last_route_stop = all_stop_times[STOPS_PER_TRIP - 1][3]
    last_time = all_stop_times[STOPS_PER_TRIP - 1][1]
    sign_in_start = _fmt_time(first_start_min - 10)
    sign_in_end = _fmt_time(first_start_min - 5)
    all_run_events.append(
        [
            "crew-weekday",
            "200",
            "10",
            "",
            "",
            "Supervisor",
            "Sign-In",
            "",
            all_stop_times[0][3],
            sign_in_start,
            "",
            all_stop_times[0][3],
            sign_in_end,
            "",
        ]
    )
    all_run_events.append(
        [
            "crew-weekday",
            "200",
            "20",
            "",
            "BLOCK-0",
            "Supervisor",
            "Ride Check",
            first_trip,
            all_stop_times[0][3],
            first_departure,
            "2",
            last_route_stop,
            last_time,
            "2",
        ]
    )
    all_employee_run_dates.append([SERVICE_DATE, "crew-weekday", "200", "emp-supervisor"])

    _write(
        directory / "agency.txt",
        ["agency_name", "agency_url", "agency_timezone"],
        [
            [
                "Synthetic Transit Authority",
                "https://example.invalid/synthetic",
                "America/Los_Angeles",
            ]
        ],
    )
    _write(
        directory / "stops.txt",
        ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        [
            [
                sid,
                f"Synthetic Stop {i}",
                f"{34.0 + (i % 1000) * 0.001:.6f}",
                f"-118.{(i % 1000):03d}000",
            ]
            for i, sid in enumerate(stop_ids, start=1)
        ],
    )
    _write(
        directory / "stops_supplement.txt",
        ["stop_id", "stop_name", "location_type", "TODS_location_type"],
        [
            ["garage", "Synthetic Garage", "0", "garage"],
            ["garage-waypoint", "Synthetic Garage Approach", "0", ""],
        ],
    )
    _write(
        directory / "routes.txt",
        ["route_id", "route_short_name", "route_type"],
        [["12", "12", "3"], ["34", "34", "3"]],
    )
    _write(
        directory / "routes_supplement.txt",
        ["route_id", "route_long_name", "route_type"],
        [["deadheads", "Deadheads", "3"]],
    )
    _write(
        directory / "calendar.txt",
        CALENDAR_HEADER,
        [["daily", "1", "1", "1", "1", "1", "1", "1", "20260101", "20261231"]],
    )
    _write(
        directory / "calendar_supplement.txt",
        CALENDAR_HEADER,
        [["crew-weekday", "1", "1", "1", "1", "1", "0", "0", "20260101", "20261231"]],
    )
    _write(
        directory / "calendar_dates_supplement.txt",
        ["service_id", "date", "exception_type"],
        [["crew-weekday", "20260703", "2"]],
    )
    _write(
        directory / "trips.txt",
        ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "block_id"],
        all_trips,
    )
    _write(
        directory / "trips_supplement.txt",
        ["route_id", "service_id", "trip_id", "block_id", "TODS_trip_type"],
        all_trips_supplement,
    )
    _write(
        directory / "stop_times.txt",
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        all_stop_times,
    )
    _write(
        directory / "stop_times_supplement.txt",
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        all_stop_times_supplement,
    )
    _write(
        directory / "run_events.txt",
        [
            "service_id",
            "run_id",
            "event_sequence",
            "piece_id",
            "block_id",
            "job_type",
            "event_type",
            "trip_id",
            "start_location",
            "start_time",
            "start_mid_trip",
            "end_location",
            "end_time",
            "end_mid_trip",
        ],
        all_run_events,
    )
    _write(
        directory / "employee_run_dates.txt",
        ["date", "service_id", "run_id", "employee_id"],
        all_employee_run_dates,
    )
    _write(
        directory / "vehicles.txt",
        ["vehicle_id", "vehicle_label", "license_plate"],
        all_vehicles,
    )
    _write(
        directory / "vehicle_assignments.txt",
        ["date", "service_id", "block_id", "vehicle_id"],
        all_vehicle_assignments,
    )

    return FeedStats(
        trips=trips,
        blocks=n_blocks,
        deadhead_blocks=deadhead_blocks,
        mutated_blocks=mutated_blocks,
        stops=n_stops,
        seed=seed,
        deadhead_pct=deadhead_pct,
        inject_errors=inject_errors,
        profile=profile,
    )


_SYNTHETIC_BANNER = """\
# SYNTHETIC DATA -- NOT A REAL TRANSIT FEED

Every file in this package was generated by `scripts/generate_feed.py`. It
is fake data, structurally shaped like a TODS+GTFS operations export, made
for performance and fuzz testing (see `scripts/benchmark.py`) and for
publishing reproducible benchmark artifacts.

**Do not cite this as evidence about what real transit feeds look like.**
tods-validate's design constraint is that synthetic artifacts are always
loudly labeled as synthetic and never substituted for real-world review
(see `docs/ideation/03-expansions.md`, EXP-13). Real-feed conformance work
tracks separately under the roadmap's R1 item.

## Reproduce this exact package

```
python scripts/generate_feed.py \\
{args} \\
  --out YOUR-OUTPUT-PATH
```

(`--out` is omitted above because it names *this* path, not a parameter of
the generated content -- two runs with identical seed and parameters but
different `--out` values are byte-for-byte identical except for this file.)

## Parameters

| parameter        | value |
|-------------------|-------|
| profile           | {profile} |
| seed              | {seed} |
| trips             | {trips} |
| deadhead_pct      | {deadhead_pct} |
| blocks            | {blocks} |
| deadhead_blocks   | {deadhead_blocks} |
| inject_errors     | {inject_errors} |
| mutated_blocks    | {mutated_blocks} |
| stops             | {stops} |

Any published benchmark number that cites this artifact should cite the
seed and parameters above, so it can be regenerated bit-for-bit.
"""


def _write_labels(directory: Path, stats: FeedStats, cli_args: list[str]) -> None:
    reproduce_args = "  " + " \\\n  ".join(cli_args)
    (directory / "SYNTHETIC.md").write_text(
        _SYNTHETIC_BANNER.format(
            args=reproduce_args,
            profile=stats.profile or "(none)",
            seed=stats.seed,
            trips=stats.trips,
            deadhead_pct=stats.deadhead_pct,
            blocks=stats.blocks,
            deadhead_blocks=stats.deadhead_blocks,
            inject_errors=stats.inject_errors,
            mutated_blocks=stats.mutated_blocks,
            stops=stats.stops,
        ),
        encoding="utf-8",
    )
    manifest = {
        "synthetic": True,
        "generator": "scripts/generate_feed.py",
        "profile": stats.profile,
        "seed": stats.seed,
        "trips": stats.trips,
        "deadhead_pct": stats.deadhead_pct,
        "inject_errors": stats.inject_errors,
        "blocks": stats.blocks,
        "deadhead_blocks": stats.deadhead_blocks,
        "mutated_blocks": stats.mutated_blocks,
        "stops": stats.stops,
    }
    (directory / "synthetic_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# Zip entries carry the source file's mtime, so two runs of the same seed
# produced identical *contents* inside archives with different bytes. This
# module's docstring promises a package that "can be regenerated bit-for-bit",
# and a published benchmark artifact whose checksum changes every build cannot
# be checked against the number it was used to measure. Every entry is stamped
# with this instead: 1980-01-01, the earliest a zip timestamp can express.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _finalize(src: Path, out: Path) -> None:
    if out.suffix.lower() == ".zip":
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(src.iterdir()):
                info = zipfile.ZipInfo(file.name, date_time=_ZIP_EPOCH)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, file.read_bytes())
    else:
        out.mkdir(parents=True, exist_ok=True)
        for file in sorted(src.iterdir()):
            (out / file.name).write_bytes(file.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a seeded, clearly-labeled synthetic TODS+GTFS package "
            "for benchmark/fuzz release artifacts."
        )
    )
    parser.add_argument(
        "--trips",
        "--runs",
        dest="trips",
        type=int,
        default=None,
        help="number of scheduled trips (default: from --profile, else 1000)",
    )
    parser.add_argument(
        "--deadhead-pct",
        dest="deadhead_pct",
        type=float,
        default=None,
        help=(
            "percent of blocks that get a pull-out/pull-back deadhead pair "
            "(default: from --profile, else 5.0)"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="random seed; identical seed+params => identical output",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default=None,
        help="preset trips/deadhead-pct/error-injection level; explicit flags override the preset",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output directory, or a path ending in .zip to write a zip archive",
    )
    args = parser.parse_args(argv)

    preset = PROFILES.get(args.profile) if args.profile else None
    default_trips = int(preset["trips"]) if preset else 1000
    default_deadhead_pct = preset["deadhead_pct"] if preset else 5.0
    trips = args.trips if args.trips is not None else default_trips
    deadhead_pct = args.deadhead_pct if args.deadhead_pct is not None else default_deadhead_pct
    inject_errors = preset["inject_errors"] if preset else 0.0

    cli_args = [f"--trips {trips}", f"--deadhead-pct {deadhead_pct}", f"--seed {args.seed}"]
    if args.profile:
        cli_args.append(f"--profile {args.profile}")

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "feed"
        stats = build_feed(
            staging,
            trips=trips,
            deadhead_pct=deadhead_pct,
            seed=args.seed,
            inject_errors=inject_errors,
            profile=args.profile,
        )
        _write_labels(staging, stats, cli_args)
        _finalize(staging, args.out)

    print(f"wrote {args.out}")
    print(f"  profile:         {args.profile or '(none)'}")
    print(f"  seed:            {stats.seed}")
    print(f"  trips:           {stats.trips}")
    print(f"  blocks:          {stats.blocks} ({stats.deadhead_blocks} with deadheads)")
    print(f"  inject_errors:   {stats.inject_errors} ({stats.mutated_blocks} blocks mutated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
