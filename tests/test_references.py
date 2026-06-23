"""Reference rules (TODS-x3xx), including resolution into the companion GTFS feed."""

from pathlib import Path

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


def test_stop_times_for_deleted_trip_does_not_trip_e314(tmp_path: Path) -> None:
    # A trip deleted via trips_supplement leaves the supplemented feed; the spec
    # says its stop_times "would thus be ignored," so a stop_times_supplement row
    # pointing at the deleted trip must not be flagged as a missing reference.
    (tmp_path / "trips.txt").write_text("trip_id,route_id,service_id\nT1,R1,weekday\n")
    (tmp_path / "trips_supplement.txt").write_text("trip_id,TODS_delete\nT1,1\n")
    (tmp_path / "stop_times_supplement.txt").write_text(
        "trip_id,stop_sequence,arrival_time\nT1,1,10:00:00\n"
    )
    _, findings = run(tmp_path)
    e314 = [f for f in findings if f.rule_id == "TODS-E314"]
    assert e314 == [], f"deleted trip should not trip E314, got {[f.message for f in e314]}"


def test_run_event_endpoint_mismatch_w315() -> None:
    findings = [f for f in run_invalid_fixture("TODS-W315") if f.rule_id == "TODS-W315"]
    assert len(findings) == 1  # only start_location mismatches; end_location matches
    msg = findings[0].message
    assert "start_location" in msg
    assert "'S3'" in msg  # the actual (wrong) location
    assert "'S1'" in msg  # the trip's first stop
    assert "T1" in msg


def test_endpoint_check_skips_mid_trip_events(tmp_path: Path) -> None:
    # Same start_location mismatch, but flagged as a mid-trip start: no W315.
    (tmp_path / "trips.txt").write_text("trip_id,route_id,service_id\nT1,R1,weekday\n")
    (tmp_path / "stop_times.txt").write_text(
        "trip_id,stop_sequence,stop_id,arrival_time,departure_time\n"
        "T1,1,S1,09:00:00,09:00:00\nT1,2,S2,10:00:00,10:00:00\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\nS2\nS3\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time,start_mid_trip\n"
        "weekday,1,10,operator,T1,S3,09:30:00,S2,10:00:00,1\n"
    )
    _, findings = run(tmp_path)
    assert not any(f.rule_id == "TODS-W315" for f in findings)
