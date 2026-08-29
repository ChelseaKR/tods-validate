#!/usr/bin/env python3
"""Fail when validation throughput regresses past the committed budget (QM-02).

``scripts/benchmark.py`` has always been able to measure throughput; nothing
compared the measurement to anything, so a regression was only visible to
someone who happened to run it and remember the old number. This turns it into
a gate: measure, compare against ``perf/baseline.json``, fail on a regression
worse than the budget.

Two things it deliberately does not do, because either would make a green run
mean less than it says:

* It never passes when it could not compare. A missing or unmeasured baseline
  is a failure -- and the failure prints the number that was just measured, so
  recording a baseline is reading one line rather than running something else.
* It does not average the repetitions. On a shared runner a slow repetition
  means the runner was busy, not that the code got slower, so the *best* run is
  the honest estimate of what the code can do. Noise then makes a regression
  under-reported rather than invented, and the budget absorbs the difference.

And one thing it now does that it did not. A throughput gate can only fire on
slowness, which means *doing less work makes it greener*. The timed call's
result was discarded and the row count was an assumed constant, so a validator
that had quietly stopped reading the feed would have burned almost no CPU,
reported an enormous rate, and passed more comfortably than a correct one --
the failure the gate exists to catch was unreachable from below. Every
repetition now counts the rows the loader actually parsed, refuses to report a
rate when that count falls short of what the generated feed contains, and
refuses when two repetitions disagree about it.

The rate's denominator stays the fixed ``trips * ROWS_PER_TRIP`` unit of work
rather than becoming the measured count. The two differ (the generated feed
also carries stops, vehicles and assignments), and switching would silently
raise every number by that margin, making the committed baseline look like a
speedup nobody made. The measured count is printed and checked; it is not the
divisor.

The baseline has to be recorded on the machine class the gate runs on: a number
from a laptop compared against a shared CI runner is a comparison between two
different things, which is how a perf gate ends up either permanently red or
permanently vacuous.

Usage:

    python scripts/check_perf_budget.py
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import build_feed  # noqa: E402

from tods_validate.runner import run_with_coverage  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "perf" / "baseline.json"
DEFAULT_TRIPS = 50000
DEFAULT_REPEAT = 3
# `benchmark.build_feed` writes one trips.txt row and one run_events.txt row per
# trip, so a run that parsed fewer than this did not read the feed it was given.
# The generated package also holds calendar, stops, vehicles and
# vehicle_assignments rows, so the real count is comfortably above the floor;
# the floor is the "did any work happen" question, not a row-exact assertion.
ROWS_PER_TRIP = 2
# A budget this large is not a loose budget, it is a retired one, and it would
# be retired in a data file rather than in a reviewed change to this script.
MAX_SANE_BUDGET = 10.0


class NoWorkMeasured(RuntimeError):
    """A timed repetition did not do the work the measurement assumes.

    Raised rather than returned so there is no path on which the caller can
    treat "the validator read nothing" as a very fast run.
    """


def measure(trips: int, repeat: int) -> float:
    """Best-of-``repeat`` rows of CPU-second for validating a ``trips``-trip feed.

    Throughput is computed from ``process_time`` (CPU time this process spent),
    not wall clock. Validation is single-threaded pure Python, so CPU time is
    close to a measure of the work the code does, while wall clock on a shared
    runner also measures the runner's other tenants -- and a budget that fires
    on someone else's build is a budget that gets muted. Wall clock is printed
    alongside it so a pathological difference is still visible.
    """
    with tempfile.TemporaryDirectory() as tmp:
        feed = Path(tmp) / "feed"
        build_feed(feed, trips)
        rows = trips * ROWS_PER_TRIP
        floor = trips * ROWS_PER_TRIP
        best = 0.0
        parsed_counts: set[int] = set()
        for attempt in range(1, repeat + 1):
            wall_start = time.perf_counter()
            cpu_start = time.process_time()
            package, _findings, _coverage = run_with_coverage(feed)
            cpu = time.process_time() - cpu_start
            wall = time.perf_counter() - wall_start

            parsed = sum(len(f.rows) for f in package.files.values())
            parsed_counts.add(parsed)
            if parsed < floor:
                raise NoWorkMeasured(
                    f"repetition {attempt} parsed {parsed:,} rows from a {trips:,}-trip "
                    f"feed, below the {floor:,} this generator writes. The measurement "
                    "timed a run that did not read the feed, and a rate computed from "
                    "it would report a speedup rather than the defect."
                )

            throughput = rows / cpu
            print(
                f"  run {attempt}/{repeat}: {cpu:.2f}s CPU ({wall:.2f}s wall), "
                f"{parsed:,} rows parsed, {throughput:,.0f} rows/CPU-s"
            )
            best = max(best, throughput)

        if len(parsed_counts) != 1:
            raise NoWorkMeasured(
                "repetitions of the same feed parsed different row counts "
                f"({sorted(parsed_counts)}). The runs are not comparable, so the best "
                "of them is not a measurement of anything."
            )
        return best


def load_baseline() -> dict[str, Any]:
    if not BASELINE.exists():
        return {}
    loaded: dict[str, Any] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trips", type=int, default=None)
    parser.add_argument("--repeat", type=int, default=None)
    args = parser.parse_args()

    baseline = load_baseline()
    trips = args.trips or int(baseline.get("trips", DEFAULT_TRIPS))
    repeat = args.repeat or int(baseline.get("repeat", DEFAULT_REPEAT))

    print(f"measuring {trips} trips, best of {repeat}")
    try:
        measured = measure(trips, repeat)
    except NoWorkMeasured as exc:
        print(f"::error::{exc}")
        return 1
    print(f"\nmeasured: {measured:,.0f} rows/CPU-s")

    expected = baseline.get("rowsPerCpuSecond")
    if not isinstance(expected, int | float):
        print(
            f"::error::{BASELINE.relative_to(ROOT)} has no measured rowsPerCpuSecond, so "
            "there is nothing to compare against."
        )
        print(
            f'Record it by setting "rowsPerCpuSecond": {round(measured)} from a run on '
            "the machine class this gate runs on, with the date and machine class in "
            "the same document."
        )
        return 1

    declared_budget = baseline.get("maxRegressionFactor", 2.0)
    if (
        not isinstance(declared_budget, int | float)
        or isinstance(declared_budget, bool)
        or not 1.0 <= float(declared_budget) <= MAX_SANE_BUDGET
    ):
        print(
            f"::error::{BASELINE.relative_to(ROOT)} declares maxRegressionFactor "
            f"{declared_budget!r}, which is not a number between 1.0 and "
            f"{MAX_SANE_BUDGET}. A budget outside that range does not loosen this "
            "gate, it retires it, and retiring a gate belongs in a reviewed change "
            "rather than in a data file."
        )
        return 1
    budget = float(declared_budget)
    ratio = float(expected) / measured if measured else float("inf")
    print(
        f"baseline: {float(expected):,.0f} rows/CPU-s "
        f"({baseline.get('measuredAt')}, {baseline.get('measuredOn')})"
    )
    print(f"ratio:    {ratio:.2f}x slower than baseline (budget: {budget:.2f}x)")

    if ratio > budget:
        print(
            f"::error::Validation throughput regressed {ratio:.2f}x against the "
            f"committed baseline, past the {budget:.2f}x budget."
        )
        return 1
    print("within the perf budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
