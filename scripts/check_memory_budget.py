#!/usr/bin/env python3
"""Fail when peak memory per input byte regresses past the committed budget.

The companion to ``scripts/check_perf_budget.py``, measuring the other axis.
``docs/ideation/02-large-scale-fixes.md`` FIX-04 argued that the loader's own
safety limits (``MAX_FILE_BYTES`` 512 MiB, ``MAX_TOTAL_BYTES`` 2 GiB) advertise
a scale the current row representation cannot reasonably hold, and estimated
the cost at "roughly an order of magnitude over the raw bytes". Nothing
measured it, so the estimate stayed an estimate and the limits stayed a claim.

Measured, it is worse than the estimate: about 36x the input bytes for a full
``run()``. That number is now recorded in ``perf/baseline.json``, quoted in
``SECURITY.md`` next to the limits it contradicts, and gated here so it cannot
drift further without somebody deciding it should.

Two things this deliberately does, both copied from the throughput gate for
the same reasons:

* It never passes when it could not compare. An unrecorded baseline is a
  failure, and the failure prints the number just measured, so recording one
  is reading a line rather than running something else.
* It measures ``tracemalloc`` peak, not resident set size. RSS depends on the
  allocator, the platform, and what else the process did; traced peak counts
  the bytes this code asked Python for. That makes the number comparable
  across machines, which RSS is not: measured within 2% across CPython 3.12
  and 3.13, so unlike the throughput baseline this one is not tied to a
  machine class. It is tied to an interpreter version, which the baseline
  records.

Usage:

    python scripts/check_memory_budget.py
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import tracemalloc
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import build_feed  # noqa: E402

from tods_validate.runner import run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "perf" / "baseline.json"
DEFAULT_TRIPS = 10000


def measure(trips: int) -> tuple[float, int, int]:
    """Peak traced bytes per input byte for validating a ``trips``-trip feed.

    Returns the ratio, the peak, and the input size, because a ratio alone
    cannot be sanity-checked by a reader of the CI log.
    """
    with tempfile.TemporaryDirectory() as tmp:
        feed = Path(tmp) / "feed"
        build_feed(feed, trips)
        input_bytes = sum(f.stat().st_size for f in feed.iterdir() if f.is_file())
        tracemalloc.start()
        try:
            run(feed)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return peak / input_bytes, peak, input_bytes


def load_baseline() -> dict[str, Any]:
    if not BASELINE.exists():
        return {}
    loaded: dict[str, Any] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trips", type=int, default=None)
    args = parser.parse_args()

    baseline = load_baseline()
    trips = args.trips or int(baseline.get("memoryTrips", DEFAULT_TRIPS))

    print(f"measuring peak traced memory over a {trips}-trip feed")
    ratio, peak, input_bytes = measure(trips)
    print(f"\nmeasured: {ratio:.2f}x ({peak:,} bytes peak over {input_bytes:,} input bytes)")

    expected = baseline.get("peakBytesPerInputByte")
    if not isinstance(expected, int | float):
        print(
            f"::error::{BASELINE.relative_to(ROOT)} has no measured "
            "peakBytesPerInputByte, so there is nothing to compare against."
        )
        print(
            f'Record it by setting "peakBytesPerInputByte": {ratio:.2f} from a run '
            "on a supported interpreter, with the date and interpreter version in "
            "the same document."
        )
        return 1

    budget = float(baseline.get("maxMemoryRegressionFactor", 1.15))
    growth = ratio / float(expected)
    print(
        f"baseline: {float(expected):.2f}x "
        f"({baseline.get('memoryMeasuredAt')}, {baseline.get('memoryMeasuredOn')})"
    )
    print(f"growth:   {growth:.2f}x the committed ratio (budget: {budget:.2f}x)")

    if growth > budget:
        print(
            f"::error::Peak memory per input byte grew {growth:.2f}x against the "
            f"committed baseline, past the {budget:.2f}x budget. See FIX-04 in "
            "docs/ideation/02-large-scale-fixes.md before raising the baseline."
        )
        return 1
    print("within the memory budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
