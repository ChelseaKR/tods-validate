"""Content-anchored baseline fingerprints (FIX-07).

Row numbers shift constantly as feeds are regenerated; identity built on row
number (or a message that embeds the row number) makes every finding look
"new" and every baseline entry look "fixed" after a single inserted row. These
tests pin the fingerprint's stability contract: it depends on rule, file,
field, and structured ``data`` -- never on row or message text.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tods_validate.baseline import (
    diff_findings,
    load_baseline_identities,
    new_findings,
)
from tods_validate.findings import Finding, Severity


def _finding(
    row: int, value: str, *, field: str = "trip_id", message: str | None = None
) -> Finding:
    return Finding(
        rule_id="TODS-E307",
        severity=Severity.ERROR,
        file="run_events.txt",
        row=row,
        field=field,
        message=message or f"run_events.txt row {row}: unknown trip_id {value!r}.",
        data={"value": value, "referenced": "trips.txt"},
    )


def test_fingerprint_excludes_row_and_message() -> None:
    a = _finding(4, "trip-1")
    b = _finding(5, "trip-1", message="a totally different message")
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_changes_with_data_value() -> None:
    a = _finding(4, "trip-1")
    b = _finding(4, "trip-2")
    assert a.fingerprint() != b.fingerprint()


def test_fingerprint_changes_with_rule_file_or_field() -> None:
    base = _finding(4, "trip-1")
    other_field = _finding(4, "trip-1", field="route_id")
    assert base.fingerprint() != other_field.fingerprint()

    other_rule = Finding(
        rule_id="TODS-E308",
        severity=Severity.ERROR,
        file=base.file,
        row=base.row,
        field=base.field,
        message=base.message,
        data=dict(base.data or {}),
    )
    assert base.fingerprint() != other_rule.fingerprint()


def test_fingerprint_is_deterministic() -> None:
    a = _finding(4, "trip-1")
    b = _finding(4, "trip-1")
    assert a.fingerprint() == b.fingerprint()
    # Stable across repeated calls too, not just across equal instances.
    assert a.fingerprint() == a.fingerprint()


def test_fingerprint_stored_in_to_dict() -> None:
    f = _finding(4, "trip-1")
    d = f.to_dict()
    assert d["fingerprint"] == f.fingerprint()
    assert d["data"] == {"value": "trip-1", "referenced": "trips.txt"}


def test_inserted_row_does_not_churn_baseline(tmp_path: Path) -> None:
    """The motivating scenario: one row inserted at the top of the file."""
    old = [_finding(4, "trip-1"), _finding(10, "trip-2"), _finding(20, "trip-3")]
    baseline_path = tmp_path / "base.json"
    baseline_path.write_text(
        json.dumps({"findings": [f.to_dict() for f in old]}),
        encoding="utf-8",
    )
    baseline = load_baseline_identities(baseline_path)

    # Every finding shifts down by one row, as if a row were inserted above
    # them all; content is unchanged.
    new = [_finding(5, "trip-1"), _finding(11, "trip-2"), _finding(21, "trip-3")]
    assert new_findings(new, baseline) == []


def test_baseline_report_requires_findings_array(tmp_path: Path) -> None:
    baseline_path = tmp_path / "malformed.json"
    baseline_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="'findings' array"):
        load_baseline_identities(baseline_path)


def test_legacy_baseline_without_data_still_matches() -> None:
    """Reports predating structured ``data``/``fingerprint`` still suppress."""
    f = _finding(4, "trip-1")
    legacy_dict = {
        "rule_id": f.rule_id,
        "location": f.pointer(),
        "message": f.message,
        # No "data" and no "fingerprint" key: pre-FIX-05 report shape.
    }
    baseline = {
        (
            str(legacy_dict["rule_id"]),
            str(legacy_dict["location"]),
            str(legacy_dict["message"]),
        )
    }
    assert new_findings([f], baseline) == []


def test_diff_findings_moved_category_for_shifted_rows() -> None:
    old = [_finding(4, "trip-1"), _finding(10, "trip-2")]
    new = [_finding(5, "trip-1"), _finding(10, "trip-2")]
    result = diff_findings(old, new)
    assert [f.row for f in result.moved] == [5]
    assert [f.row for f in result.persisting] == [10]
    assert result.introduced == []
    assert result.fixed == []


def test_diff_findings_true_fix_and_introduction() -> None:
    old = [_finding(4, "trip-1"), _finding(10, "trip-2")]
    new = [_finding(4, "trip-1"), _finding(30, "trip-3")]
    result = diff_findings(old, new)
    assert [f.data["value"] for f in result.introduced] == ["trip-3"]  # type: ignore[index]
    assert [f.data["value"] for f in result.fixed] == ["trip-2"]  # type: ignore[index]
    assert [f.data["value"] for f in result.persisting] == ["trip-1"]  # type: ignore[index]
    assert result.moved == []


def test_excellent_looks_like_500_findings_shift_by_one_row() -> None:
    """The roadmap's bar: 500 findings, every row +1, zero introduced/fixed."""
    old = [_finding(row=i * 3 + 4, value=f"trip-{i}") for i in range(500)]
    new = [_finding(row=i * 3 + 5, value=f"trip-{i}") for i in range(500)]

    result = diff_findings(old, new)
    assert result.introduced == []
    assert result.fixed == []
    assert len(result.moved) == 500
    assert result.persisting == []


def test_findings_without_data_do_not_crash_fingerprinting() -> None:
    """Rules that have not been migrated to emit ``data`` (data=None) still
    fingerprint deterministically -- degraded uniqueness, not a crash."""
    f = Finding(
        rule_id="TODS-E201",
        severity=Severity.ERROR,
        file="run_events.txt",
        row=4,
        field="trip_id",
        message="run_events.txt row 4: 'trip_id' is required but empty.",
    )
    assert isinstance(f.fingerprint(), str)
    assert len(f.fingerprint()) == 64  # sha256 hex digest length
