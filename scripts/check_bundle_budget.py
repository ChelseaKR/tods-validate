#!/usr/bin/env python3
"""Fail when a shipped HTML surface grows past its committed byte budget.

The performance section of ``docs/CONFORMANCE-GAPS.md`` recorded "the shipped
HTML surfaces have no committed Lighthouse/bundle baseline" as open. This is
the bundle half.

Three things are measured, because they fail differently:

* ``web/index.html``, the playground shell. It is served over the network to
  anyone who opens the page, and it is the only one of the three where a byte
  is a byte a visitor waits for.
* The whole published ``web/`` tree, which ``pages.yml`` deploys wholesale.
  A per-page budget cannot see a rule catalog that doubles in page count.
* A generated HTML report at the FIX-15 scale of 10,000 findings. This is the
  one that can grow without anybody noticing: the per-finding cost is a
  property of the renderer, and a template change that adds 80 bytes to a row
  is invisible on a fixture and adds most of a megabyte here.

Same doctrine as ``check_perf_budget.py`` and ``check_memory_budget.py``: an
unrecorded budget is a failure, not a pass, and the failure prints the number
just measured. Unlike throughput, bytes are exact, so the budgets are absolute
ceilings with headroom rather than ratios against a noisy measurement.

Usage:

    python scripts/check_bundle_budget.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tods_validate.findings import Finding, Severity  # noqa: E402
from tods_validate.report import render_html  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUDGET = ROOT / "perf" / "bundle-baseline.json"
WEB = ROOT / "web"
REPORT_FINDINGS = 10_000


def _report_bytes(count: int) -> int:
    """Bytes of a rendered HTML report carrying ``count`` findings.

    The synthetic findings are shaped like real ones (20 rule IDs across 50
    files, all three severities, a message of realistic length) because the
    renderer groups by rule and the group count changes the total.
    """
    findings = [
        Finding(
            rule_id=f"TODS-E{300 + (index % 20)}",
            severity=Severity(index % 3),
            message=f"finding {index} with a message of realistic length describing the problem",
            file=f"file{index % 50}.txt",
            row=index,
        )
        for index in range(count)
    ]
    return len(render_html(findings, "feed/").encode("utf-8"))


def measure() -> dict[str, int]:
    pages = sorted(WEB.rglob("*.html"))
    return {
        "playgroundPageBytes": (WEB / "index.html").stat().st_size,
        "publishedSiteBytes": sum(page.stat().st_size for page in pages),
        "publishedPageCount": len(pages),
        "reportBytesAt10kFindings": _report_bytes(REPORT_FINDINGS),
    }


def load_budget() -> dict[str, Any]:
    if not BUDGET.exists():
        return {}
    loaded: dict[str, Any] = json.loads(BUDGET.read_text(encoding="utf-8"))
    return loaded


def main() -> int:
    budget = load_budget()
    measured = measure()
    limits = budget.get("limits")
    if not isinstance(limits, dict) or not limits:
        print(f"::error::{BUDGET.relative_to(ROOT)} records no limits to compare against.")
        print("Measured now:")
        print(json.dumps(measured, indent=2))
        return 1

    over = []
    for name, value in measured.items():
        limit = limits.get(name)
        if not isinstance(limit, int):
            print(f"::error::no budget recorded for {name} (measured {value:,}).")
            over.append(name)
            continue
        headroom = (limit - value) / limit * 100
        status = "over" if value > limit else f"{headroom:.0f}% headroom"
        print(f"{name:>26}: {value:>10,} / {limit:>10,}  {status}")
        if value > limit:
            over.append(name)

    if over:
        print(
            f"::error::over the committed bundle budget: {', '.join(sorted(over))}. "
            "Reduce the surface, or raise the budget deliberately and say why in "
            f"{BUDGET.relative_to(ROOT)}."
        )
        return 1
    print("within the bundle budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
