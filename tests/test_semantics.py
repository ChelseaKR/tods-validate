"""Semantic rules (TODS-x4xx)."""

import pytest

from conftest import rule_ids, run_invalid_fixture
from tods_validate.findings import Finding

RULES = (
    "TODS-E401",
    "TODS-E402",
    "TODS-W403",
    "TODS-W404",
    "TODS-E405",
    "TODS-W406",
    "TODS-W407",
    "TODS-W408",
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
