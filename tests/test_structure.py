"""Structure rules (TODS-x1xx): each fires on its fixture, none on the valid feed."""

import pytest

from conftest import rule_ids, run_invalid_fixture
from tods_validate.findings import Finding, Severity

RULES = (
    "TODS-W101",
    "TODS-W109",
    "TODS-I102",
    "TODS-E103",
    "TODS-E104",
    "TODS-E105",
    "TODS-E106",
    "TODS-W107",
    "TODS-I108",
)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_fires_on_its_fixture(rule_id: str) -> None:
    findings = run_invalid_fixture(rule_id)
    assert rule_id in rule_ids(findings)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_silent_on_valid_feed(rule_id: str, valid_findings: list[Finding]) -> None:
    assert rule_id not in rule_ids(valid_findings)


def test_missing_required_column_names_the_column() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E106") if f.rule_id == "TODS-E106"]
    assert len(findings) == 1
    f = findings[0]
    assert f.file == "run_events.txt"
    assert f.field == "event_type"
    assert f.severity is Severity.ERROR
    assert "event_type" in f.message


def test_unknown_file_is_info_only() -> None:
    findings = run_invalid_fixture("TODS-I102")
    unknown = [f for f in findings if f.rule_id == "TODS-I102"]
    assert [f.file for f in unknown] == ["notes.txt"]
    assert all(f.severity is Severity.INFO for f in unknown)


def test_other_version_file_is_recognized_not_unknown() -> None:
    findings = run_invalid_fixture("TODS-W109")
    warned = [f for f in findings if f.rule_id == "TODS-W109"]
    assert [f.file for f in warned] == ["deadheads.txt"]
    assert all(f.severity is Severity.WARNING for f in warned)
    # The v1 file must no longer fall through to the unknown-file rule.
    assert "TODS-I102" not in rule_ids(findings)


def test_other_version_file_message_names_the_active_version() -> None:
    findings = run_invalid_fixture("TODS-W109")
    warned = [f for f in findings if f.rule_id == "TODS-W109"]
    assert "2.1.0" in warned[0].message
    assert warned[0].suggestion is not None


def test_empty_file_reports_unreadable_not_missing_columns() -> None:
    findings = run_invalid_fixture("TODS-E103")
    ids = rule_ids(findings)
    assert "TODS-E103" in ids
    assert "TODS-E106" not in ids  # no header to check columns against


def test_ragged_row_points_at_the_row() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E104") if f.rule_id == "TODS-E104"]
    assert len(findings) == 1
    assert findings[0].row == 2
