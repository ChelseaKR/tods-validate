"""The delivery collector never fabricates a zero (QM-11).

`docs/standards/QUALITY-AND-METRICS-STANDARD.md` states it plainly: "the
collector never fabricates a zero". A change fail rate of 0% is excellent; a
change fail rate that is 0% because nothing was counted is a lie that looks
excellent, and the two render identically in a ledger. These pin the
difference, and they matter more than the arithmetic: the arithmetic is
checkable by reading it, the absent-versus-zero distinction is not.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "delivery_metrics.py"
SNAPSHOT = ROOT / "docs" / "DORA-2026-Q3.json"
REVIEW = ROOT / "docs" / "DORA-2026-Q3.md"


def _collector() -> ModuleType:
    spec = importlib.util.spec_from_file_location("delivery_metrics", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_an_unmeasurable_metric_is_null_with_a_reason_not_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With gh unavailable and no git history readable, every metric must come
    # back absent. Not one of them may come back 0.
    collector = _collector()
    monkeypatch.setattr(collector, "_gh", lambda *a: None)
    monkeypatch.setattr(collector, "_git", lambda *a: [])
    metrics = collector.collect()
    assert metrics, "the collector produced no metrics at all"
    for name, metric in metrics.items():
        assert metric.get("value") is None, f"{name} produced a value with no data behind it"
        assert metric.get("reason"), f"{name} is absent without saying why"


def test_a_single_release_is_not_a_frequency(monkeypatch: pytest.MonkeyPatch) -> None:
    # One release cannot yield an interval. Reporting one would be arithmetic
    # on a sample of zero gaps.
    collector = _collector()
    monkeypatch.setattr(
        collector,
        "_gh",
        lambda *a: (
            [{"tagName": "v1", "publishedAt": "2026-01-01T00:00:00+00:00"}]
            if a[0] == "release"
            else []
        ),
    )
    monkeypatch.setattr(collector, "_git", lambda *a: [])
    frequency = collector.collect()["deploymentFrequencyDays"]
    assert frequency["value"] is None
    assert "at least two" in frequency["reason"]


def test_real_data_does_produce_values(monkeypatch: pytest.MonkeyPatch) -> None:
    # Positive control. A collector that returned None for everything would
    # satisfy both tests above and measure nothing.
    collector = _collector()
    releases = [
        {"tagName": "v1", "publishedAt": "2026-01-01T00:00:00+00:00"},
        {"tagName": "v2", "publishedAt": "2026-01-11T00:00:00+00:00"},
    ]
    prs = [
        {
            "number": 1,
            "createdAt": "2026-01-01T00:00:00+00:00",
            "mergedAt": "2026-01-01T02:00:00+00:00",
            "reviews": [],
        },
        {
            "number": 2,
            "createdAt": "2026-01-02T00:00:00+00:00",
            "mergedAt": "2026-01-02T04:00:00+00:00",
            "reviews": [{"state": "APPROVED"}],
        },
    ]
    monkeypatch.setattr(collector, "_gh", lambda *a: releases if a[0] == "release" else prs)
    monkeypatch.setattr(collector, "_git", lambda *a: ["sha"] * 10)
    metrics = collector.collect()
    assert metrics["deploymentFrequencyDays"]["value"] == 10.0
    assert metrics["changeLeadTimeHours"]["p50"] == 3.0
    assert metrics["unreviewedMergeRate"]["value"] == 0.5


def test_the_committed_snapshot_and_review_agree_on_the_headline_numbers() -> None:
    # A review document and its snapshot that disagree are worse than either
    # alone, because each reads as authoritative.
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    review = REVIEW.read_text(encoding="utf-8")
    metrics = snapshot["metrics"]
    assert f"1 per {metrics['deploymentFrequencyDays']['value']} days" in review
    assert f"p50 {metrics['changeLeadTimeHours']['p50']}h" in review
    unreviewed = metrics["unreviewedMergeRate"]
    assert f"{unreviewed['unreviewed']} of {unreviewed['sample']}" in review


def test_the_review_records_a_dated_graduation_for_every_baseline_row() -> None:
    # "A BASELINE row without a graduation date is a conformance failure, same
    # as an aspirational row." Count the BASELINE rows, count the dates.
    review = REVIEW.read_text(encoding="utf-8")
    baseline_rows = [line for line in review.splitlines() if "BASELINE" in line and "|" in line]
    assert baseline_rows, "the review records no BASELINE rows at all"
    for row in baseline_rows:
        assert "graduation decision **" in row, f"BASELINE row with no graduation date: {row}"


def test_the_review_ends_with_actions() -> None:
    # "Every quarterly review must produce at least one action or an explicit
    # 'no action, because...'". A checkpoint-only review is the named
    # anti-pattern.
    review = REVIEW.read_text(encoding="utf-8")
    assert "## Actions" in review
    actions = review.split("## Actions", 1)[1]
    assert any(line.strip().startswith(("1.", "2.")) for line in actions.splitlines())
