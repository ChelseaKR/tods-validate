"""Semantic rules (TODS-x4xx)."""

from pathlib import Path

import pytest

from conftest import rule_ids, run_invalid_fixture
from tods_validate.findings import Finding
from tods_validate.runner import run

_RUN_EVENTS_HEADER = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time\n"
)

RULES = (
    "TODS-E401",
    "TODS-E402",
    "TODS-W403",
    "TODS-W404",
    "TODS-E405",
    "TODS-W406",
    "TODS-W407",
    "TODS-W408",
    "TODS-W409",
)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_fires_on_its_fixture(rule_id: str) -> None:
    findings = run_invalid_fixture(rule_id)
    assert rule_id in rule_ids(findings)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_silent_on_valid_feed(rule_id: str, valid_findings: list[Finding]) -> None:
    assert rule_id not in rule_ids(valid_findings)


def test_overnight_suggestion_on_negative_duration() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E401") if f.rule_id == "TODS-E401"]
    assert len(findings) == 1
    assert findings[0].suggestion is not None
    assert "25:10:00" in findings[0].suggestion


def test_overlap_message_names_both_trips() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E402") if f.rule_id == "TODS-E402"]
    assert len(findings) == 1
    assert "'t1'" in findings[0].message
    assert "'t2'" in findings[0].message


def test_run_dates_exceeding_trip_dates_reports_once_per_service_pair() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E405") if f.rule_id == "TODS-E405"]
    assert len(findings) == 1
    assert "20260101" in findings[0].message  # an example offending date


def test_double_booking_is_not_reported_for_distinct_employees() -> None:
    # The valid feed has two different employees on overlapping runs.
    findings = [f for f in run_invalid_fixture("TODS-W404") if f.rule_id == "TODS-W404"]
    assert len(findings) == 1
    assert "emp-1" in findings[0].message


def test_run_continuity_names_both_locations() -> None:
    findings = [f for f in run_invalid_fixture("TODS-W409") if f.rule_id == "TODS-W409"]
    assert len(findings) == 1
    msg = findings[0].message
    assert "'stopA'" in msg  # where the previous event ended
    assert "'stopB'" in msg  # where this event starts instead


def test_run_continuity_passes_when_events_connect(tmp_path: Path) -> None:
    (tmp_path / "run_events.txt").write_text(
        _RUN_EVENTS_HEADER
        + "daily,1,1,Pullout,garage,08:00:00,stopA,08:30:00\n"
        + "daily,1,2,Operate,stopA,08:30:00,garage,09:30:00\n"  # starts where #1 ended
    )
    _, findings = run(tmp_path)
    assert not any(f.rule_id == "TODS-W409" for f in findings)


def test_run_continuity_skips_blank_endpoints(tmp_path: Path) -> None:
    # A break event with no location should not be read as a teleport.
    (tmp_path / "run_events.txt").write_text(
        _RUN_EVENTS_HEADER
        + "daily,1,1,Operate,garage,08:00:00,stopA,08:30:00\n"
        + "daily,1,2,Break,,08:30:00,,09:00:00\n"
        + "daily,1,3,Operate,stopB,09:00:00,garage,10:00:00\n"
    )
    _, findings = run(tmp_path)
    assert not any(f.rule_id == "TODS-W409" for f in findings)


def test_run_continuity_does_not_cross_runs(tmp_path: Path) -> None:
    # Two different runs; the gap between them is not a discontinuity.
    (tmp_path / "run_events.txt").write_text(
        _RUN_EVENTS_HEADER
        + "daily,1,1,Operate,garage,08:00:00,stopA,09:00:00\n"
        + "daily,2,1,Operate,stopZ,08:00:00,garage,09:00:00\n"
    )
    _, findings = run(tmp_path)
    assert not any(f.rule_id == "TODS-W409" for f in findings)
