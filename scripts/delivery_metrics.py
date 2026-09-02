#!/usr/bin/env python3
"""Collect the DORA five and their quality-debt counterweights (QM-11, ADM-01..10).

`docs/standards/QUALITY-AND-METRICS-STANDARD.md` asks for "a `gh api`-based
collector [that] reads deploy, release, and publish workflow runs plus
`incident`-labelled issues, then writes a committed quarterly
`DORA-<year>-Q<n>.md` report and JSON snapshot", and states that
"library/CLI repositories report DF/LT only" and that "the collector never
fabricates a zero".

That last clause is the whole design. Every metric this cannot measure comes
back as ``None`` with a ``reason`` string beside it, never as ``0``. Zero and
"no data" are different claims, and a delivery ledger that renders them
identically is the same defect as a gate that passes when it did not run. A
change fail rate of 0% is excellent; a change fail rate that is 0% because
nothing was counted is a lie that looks excellent.

Usage:

    python scripts/delivery_metrics.py --quarter 2026-Q3
    python scripts/delivery_metrics.py --quarter 2026-Q3 --out docs/DORA-2026-Q3.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# The metrics a library/CLI repository cannot source, with the trigger that
# retires each N/A. Named here rather than left out, so the report says why a
# number is absent instead of leaving a reader to guess.
NOT_APPLICABLE = {
    "failedDeploymentRecoveryTime": (
        "no incident-labelled issue exists yet; becomes measurable from issue "
        "open and close timestamps at the first one (IR-03)"
    ),
    "deploymentReworkRate": (
        "no revert commits exist, so there is no ratio to compute; the first revert retires this"
    ),
}


def _gh(*args: str) -> Any:
    """A `gh` call returning parsed JSON, or None when gh is unavailable."""
    try:
        out = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["/usr/bin/env", "gh", *args], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return json.loads(out.stdout)


def _git(*args: str) -> list[str]:
    out = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["/usr/bin/env", "git", *args], capture_output=True, text=True, cwd=ROOT, check=False
    )
    return [line for line in out.stdout.splitlines() if line]


def _unmeasured(reason: str) -> dict[str, Any]:
    """A metric with no value. Never 0, never an empty list rendered as 0."""
    return {"value": None, "reason": reason}


def collect() -> dict[str, Any]:
    metrics: dict[str, Any] = {}

    releases = _gh("release", "list", "--limit", "100", "--json", "tagName,publishedAt")
    if releases is None:
        metrics["deploymentFrequencyDays"] = _unmeasured("gh unavailable; releases not read")
    elif len(releases) < 2:
        metrics["deploymentFrequencyDays"] = _unmeasured(
            f"only {len(releases)} published release(s); a frequency needs at least two"
        )
    else:
        dates = sorted(datetime.fromisoformat(r["publishedAt"]).astimezone(UTC) for r in releases)
        span = (dates[-1] - dates[0]).days
        metrics["deploymentFrequencyDays"] = {
            "value": round(span / (len(dates) - 1), 1),
            "releases": len(dates),
            "spanDays": span,
            "first": dates[0].date().isoformat(),
            "last": dates[-1].date().isoformat(),
        }

    prs = _gh(
        "pr",
        "list",
        "--state",
        "merged",
        "--limit",
        "300",
        "--json",
        "number,createdAt,mergedAt,reviews",
    )
    if not prs:
        metrics["changeLeadTimeHours"] = _unmeasured("gh unavailable or no merged pull requests")
        metrics["unreviewedMergeRate"] = _unmeasured("gh unavailable or no merged pull requests")
    else:
        hours = sorted(
            (
                datetime.fromisoformat(p["mergedAt"]) - datetime.fromisoformat(p["createdAt"])
            ).total_seconds()
            / 3600
            for p in prs
        )
        metrics["changeLeadTimeHours"] = {
            "p50": round(statistics.median(hours), 1),
            "p90": round(hours[int(len(hours) * 0.9)], 1),
            "sample": len(hours),
        }
        unreviewed = sum(1 for p in prs if not p.get("reviews"))
        metrics["unreviewedMergeRate"] = {
            "value": round(unreviewed / len(prs), 3),
            "unreviewed": unreviewed,
            "sample": len(prs),
        }

    reverts = _git("log", "--format=%H", "--grep", "^Revert", "-i", "origin/main")
    commits = _git("log", "--format=%H", "origin/main")
    if commits:
        metrics["revertRate"] = {
            "value": round(len(reverts) / len(commits), 4),
            "reverts": len(reverts),
            "commits": len(commits),
        }
        ai = _git("log", "--format=%H", "--grep", "Co-Authored-By: Claude", "origin/main")
        metrics["aiAuthoredShare"] = {
            "value": round(len(ai) / len(commits), 3),
            "aiAuthored": len(ai),
            "commits": len(commits),
            "note": "diagnostic only; never gates (AI-DEVELOPMENT-MEASUREMENT-STANDARD section 2)",
        }
    else:
        metrics["revertRate"] = _unmeasured("no commits read from origin/main")
        metrics["aiAuthoredShare"] = _unmeasured("no commits read from origin/main")

    for name, reason in NOT_APPLICABLE.items():
        metrics[name] = _unmeasured(reason)

    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", required=True, help="e.g. 2026-Q3")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    snapshot = {
        "quarter": args.quarter,
        "collectedAt": datetime.now(UTC).date().isoformat(),
        "repositoryShape": "library/CLI: reports deployment frequency and lead time only",
        "metrics": collect(),
    }
    out = args.out or ROOT / "docs" / f"DORA-{args.quarter}.json"
    out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    print(f"\nwrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
