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

from tods_validate.runner import run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "perf" / "baseline.json"
DEFAULT_TRIPS = 50000
DEFAULT_REPEAT = 3


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
        rows = trips * 2  # trips + run events dominate
        best = 0.0
        for attempt in range(1, repeat + 1):
            wall_start = time.perf_counter()
            cpu_start = time.process_time()
            run(feed)
            cpu = time.process_time() - cpu_start
            wall = time.perf_counter() - wall_start
            throughput = rows / cpu
            print(
                f"  run {attempt}/{repeat}: {cpu:.2f}s CPU ({wall:.2f}s wall), "
                f"{throughput:,.0f} rows/CPU-s"
            )
            best = max(best, throughput)
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
    measured = measure(trips, repeat)
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

    budget = float(baseline.get("maxRegressionFactor", 2.0))
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
