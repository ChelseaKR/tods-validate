#!/usr/bin/env python3
"""Generate a large synthetic TODS+GTFS feed and time validation on it.

Usage:

    python scripts/benchmark.py --trips 50000

Prints rows/second so regressions in the validation path are visible. The
generated feed exercises every rule band; the point is throughput, not whether
the synthetic feed is clean.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from tods_validate.runner import run


def _write(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def build_feed(directory: Path, trips: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    blocks = max(1, trips // 10)

    _write(
        directory / "calendar.txt",
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date",
        ["daily,1,1,1,1,1,1,1,20260101,20261231"],
    )
    _write(
        directory / "stops.txt",
        "stop_id,stop_name,stop_lat,stop_lon",
        [f"s{i},Stop {i},34.0{i % 90:02d},-118.0{i % 90:02d}" for i in range(100)],
    )
    _write(
        directory / "trips.txt",
        "route_id,service_id,trip_id,block_id",
        [f"r1,daily,t{i},B{i % blocks}" for i in range(trips)],
    )

    # One run event per trip plus a deadhead, all internally consistent.
    run_rows = []
    for i in range(trips):
        start_h = 4 + (i % 18)
        run_rows.append(
            f"daily,run{i % blocks},{(i % 100) * 10 + 10},{i % blocks}-1,B{i % blocks},"
            f"Operator,Operator,t{i},s{i % 100},{start_h:02d}:00:00,2,"
            f"s{(i + 1) % 100},{start_h:02d}:50:00,2"
        )
    _write(
        directory / "run_events.txt",
        "service_id,run_id,event_sequence,piece_id,block_id,job_type,event_type,trip_id,"
        "start_location,start_time,start_mid_trip,end_location,end_time,end_mid_trip",
        run_rows,
    )
    _write(
        directory / "vehicles.txt",
        "vehicle_id",
        [f"v{i}" for i in range(blocks)],
    )
    _write(
        directory / "vehicle_assignments.txt",
        "date,service_id,block_id,vehicle_id",
        [f"20260106,daily,B{i},v{i}" for i in range(blocks)],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trips", type=int, default=20000)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        feed = Path(tmp) / "feed"
        build_feed(feed, args.trips)
        total_rows = args.trips * 2  # trips + run events dominate
        start = time.perf_counter()
        _, findings = run(feed)
        elapsed = time.perf_counter() - start

    print(f"trips:           {args.trips}")
    print(f"findings:        {len(findings)}")
    print(f"elapsed:         {elapsed:.2f}s")
    print(f"throughput:      {total_rows / elapsed:,.0f} rows/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
