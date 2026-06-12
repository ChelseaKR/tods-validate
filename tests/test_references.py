"""Reference rules (TODS-x3xx), including resolution into the companion GTFS feed."""

import pytest

from conftest import FIXTURES, rule_ids, run_invalid_fixture
from tods_validate.findings import Finding, Severity
from tods_validate.runner import run

RULES = (
    "TODS-E301",
    "TODS-W302",
    "TODS-E303",
    "TODS-E304",
    "TODS-W305",
    "TODS-W306",
    "TODS-E307",
    "TODS-E308",
    "TODS-E309",
    "TODS-E310",
    "TODS-E311",
    "TODS-E312",
    "TODS-W313",
    "TODS-E314",
)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_fires_on_its_fixture(rule_id: str) -> None:
    findings = run_invalid_fixture(rule_id)
    assert rule_id in rule_ids(findings)


@pytest.mark.parametrize("rule_id", RULES)
def test_rule_silent_on_valid_feed(rule_id: str, valid_findings: list[Finding]) -> None:
    assert rule_id not in rule_ids(valid_findings)


def test_gtfs_rules_skipped_without_companion_feed() -> None:
    """A TODS-only package must not produce broken-GTFS-reference errors."""
    _, findings = run(FIXTURES / "invalid" / "TODS-E301")  # no GTFS files inside
    gtfs_rules = {"TODS-E307", "TODS-E308", "TODS-E309", "TODS-E310", "TODS-E311", "TODS-E312"}
    assert not (rule_ids(findings) & gtfs_rules)


def test_run_reference_message_explains_pair_matching() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E301") if f.rule_id == "TODS-E301"]
    assert len(findings) == 1
    assert "service_id" in findings[0].message
    assert "run_id" in findings[0].message


def test_missing_reference_file_is_a_warning_not_an_error() -> None:
    findings = run_invalid_fixture("TODS-W302")
    w302 = [f for f in findings if f.rule_id == "TODS-W302"]
    assert w302, "expected TODS-W302"
    assert all(f.severity is Severity.WARNING for f in w302)
    # The unresolvable run reference must not also be reported as broken.
    assert "TODS-E301" not in rule_ids(findings)


def test_block_mismatch_names_both_blocks() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E310") if f.rule_id == "TODS-E310"]
    assert len(findings) == 1
    assert "'B1'" in findings[0].message
    assert "'B2'" in findings[0].message


def test_delete_and_readd_cites_both_rows() -> None:
    findings = [f for f in run_invalid_fixture("TODS-E304") if f.rule_id == "TODS-E304"]
    assert len(findings) == 1
    assert "row 2" in findings[0].message
    assert "row 3" in findings[0].message
