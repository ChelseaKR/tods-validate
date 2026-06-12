"""Field rules (TODS-x2xx) and the GTFS time parser."""

import pytest

from conftest import rule_ids, run_invalid_fixture
from tods_validate.findings import Finding
from tods_validate.rules.fields import parse_time

RULES = (
    "TODS-E201",
    "TODS-E202",
    "TODS-E203",
    "TODS-E204",
    "TODS-E205",
    "TODS-W206",
)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_fires_on_its_fixture(rule_id: str) -> None:
    findings = run_invalid_fixture(rule_id)
    assert rule_id in rule_ids(findings)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_silent_on_valid_feed(rule_id: str, valid_findings: list[Finding]) -> None:
    assert rule_id not in rule_ids(valid_findings)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("00:00:00", 0),
        ("09:45:30", 9 * 3600 + 45 * 60 + 30),
        ("9:45:30", 9 * 3600 + 45 * 60 + 30),  # single-digit hour is allowed
        ("25:10:00", 25 * 3600 + 10 * 60),  # service past midnight keeps counting
    ],
)
def test_parse_time_accepts_gtfs_times(value: str, seconds: int) -> None:
    assert parse_time(value) == seconds


@pytest.mark.parametrize("value", ["", "9am", "09:75:00", "09:00", "09:00:0", "-1:00:00"])
def test_parse_time_rejects_bad_times(value: str) -> None:
    assert parse_time(value) is None


def test_duplicate_primary_key_reports_both_rows() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E204") if f.rule_id == "TODS-E204"]
    assert len(findings) == 1
    assert findings[0].row == 3
    assert "row 2" in findings[0].message


def test_enum_message_lists_allowed_values() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E202") if f.rule_id == "TODS-E202"]
    assert len(findings) == 1
    assert "'1'" in findings[0].message
    assert "blank" in findings[0].message


def test_conditional_service_id_explains_the_ambiguity() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E205") if f.rule_id == "TODS-E205"]
    assert len(findings) == 1
    message = findings[0].message
    assert "B1" in message
    assert "weekday" in message
    assert "weekend" in message
