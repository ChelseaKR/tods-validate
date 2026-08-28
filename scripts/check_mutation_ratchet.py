#!/usr/bin/env python3
"""Fail when the mutation kill rate drops below the committed floor (CQ-47).

`.github/workflows/mutation.yml` has run mutmut weekly for months under
`continue-on-error: true`, with every step ending in `|| true`. It produced a
number, printed it into a job summary, and could not fail: a kill rate that
halved would have looked exactly like one that did not move. That is advisory
in the sense of "nobody is told", which is not what advisory is supposed to
mean.

This keeps the run advisory in the sense that matters (it never blocks a pull
request; it is weekly, and mutation runs take about fifteen minutes) while
making one thing non-negotiable: the rate may not fall below the floor
committed in `perf/mutation-baseline.json`. Ratchet, do not jump, per
`docs/CONFORMANCE-GAPS.md`'s CQ-47 entry. Raising the floor is a decision
recorded in that file; drifting below it is the regression this exists to
catch.

Reads the JSON `mutmut export-cicd-stats` writes, so it does not re-run
anything.

Usage:

    mutmut run || true
    mutmut export-cicd-stats
    python scripts/check_mutation_ratchet.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "perf" / "mutation-baseline.json"
STATS = ROOT / "mutants" / "mutmut-cicd-stats.json"


def kill_rate(stats: dict[str, Any]) -> float:
    """killed / (killed + survived).

    `no_tests` is deliberately outside the denominator: a mutant no test
    touches is a statement about coverage, which has its own gate at 90%, and
    folding it in here would let a coverage change move a number meant to
    track how much the assertions actually pin down.
    """
    killed = int(stats["killed"])
    survived = int(stats["survived"])
    decided = killed + survived
    if decided == 0:
        raise SystemExit("mutation stats record no killed or survived mutants; nothing to rate")
    return killed / decided


def main() -> int:
    if not STATS.exists():
        print(f"::error::{STATS.relative_to(ROOT)} does not exist, so no rate can be read.")
        print("Run `mutmut run` then `mutmut export-cicd-stats` first.")
        return 1
    if not BASELINE.exists():
        print(f"::error::{BASELINE.relative_to(ROOT)} does not exist; there is no floor.")
        return 1

    stats = json.loads(STATS.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    floor = baseline.get("killRateFloor")
    if not isinstance(floor, int | float):
        print(f"::error::{BASELINE.relative_to(ROOT)} records no killRateFloor.")
        return 1

    rate = kill_rate(stats)
    target = baseline.get("target")
    print(
        f"mutation kill rate: {rate:.1%} "
        f"({stats['killed']} killed, {stats['survived']} survived, "
        f"{stats.get('no_tests', 0)} with no covering test, {stats.get('total', 0)} generated)"
    )
    print(f"floor: {float(floor):.1%}" + (f", target: {float(target):.1%}" if target else ""))

    if rate < float(floor):
        print(
            f"::error::mutation kill rate {rate:.1%} is below the committed floor "
            f"{float(floor):.1%}. Something stopped pinning down behaviour it used "
            "to pin down; see docs/mutation-testing.md."
        )
        return 1
    print("at or above the committed floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
