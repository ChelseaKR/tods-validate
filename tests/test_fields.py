"""Field rules (TODS-x2xx) and the GTFS time parser."""

from pathlib import Path

import pytest

from conftest import rule_ids, run_invalid_fixture
from tods_validate.findings import Finding
from tods_validate.rules.fields import parse_time
from tods_validate.runner import run

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
        ("100:00:00", 100 * 3600),  # hours have no upper bound in the spec
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


def test_duplicate_primary_key_detects_blank_optional_key(tmp_path: Path) -> None:
    # vehicle_assignments' primary key is (date, block_id, service_id) with
    # service_id optional; two rows colliding on (date, block_id) with a blank
    # service_id are a genuine duplicate and must be flagged. Regression: the
    # blank optional component previously suppressed the whole check.
    (tmp_path / "vehicle_assignments.txt").write_text(
        "date,block_id,service_id,vehicle_id\n20240101,BLOCK-A,,V1\n20240101,BLOCK-A,,V2\n"
    )
    (tmp_path / "vehicles.txt").write_text("vehicle_id\nV1\nV2\n")
    _, findings = run(tmp_path)
    e204 = [f for f in findings if f.rule_id == "TODS-E204"]
    assert len(e204) == 1
    assert e204[0].row == 3


def test_impossible_calendar_date_is_flagged(tmp_path: Path) -> None:
    # "20260231" has eight digits, so it passes the YYYYMMDD shape, but February
    # has no 31st. TODS-E203 must still reject it, which only holds if the check
    # validates the calendar date and not merely the digit pattern.
    (tmp_path / "employee_run_dates.txt").write_text(
        "date,service_id,run_id,employee_id\n20260231,daily,1,emp-1\n"
    )
    _, findings = run(tmp_path)
    e203 = [f for f in findings if f.rule_id == "TODS-E203"]
    assert len(e203) == 1
    assert e203[0].field == "date"
    assert "20260231" in e203[0].message


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
