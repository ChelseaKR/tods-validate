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


def test_trip_reference_without_companion_trips_warns_w302(tmp_path: Path) -> None:
    # run_events references a trip_id, but the companion GTFS has no trips.txt
    # (and nothing supplements one in). Those references cannot be resolved, so
    # W302 must say so. The warning hinges on noticing that run_events actually
    # uses trip_ids; drop that observation and the gap would pass silently.
    (tmp_path / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time\nweekday,1,10,operator,T1,S1,09:00:00,S1,10:00:00\n"
    )
    _, findings = run(tmp_path)
    w302 = [f for f in findings if f.rule_id == "TODS-W302" and "trips.txt" in f.message]
    assert w302, "expected a W302 warning that the companion GTFS lacks trips.txt"
    # A missing companion file is a warning, never a hard reference error.
    assert "TODS-E307" not in rule_ids(findings)


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


def test_run_event_time_mismatch_w316() -> None:
    findings = [f for f in run_invalid_fixture("TODS-W316") if f.rule_id == "TODS-W316"]
    assert len(findings) == 1  # only start_time mismatches; end_time matches the schedule
    msg = findings[0].message
    assert findings[0].field == "start_time"
    assert "'08:30:00'" in msg  # the run event's wrong start_time
    assert "'09:00:00'" in msg  # the trip's scheduled departure
    assert "T1" in msg


def test_time_check_skips_mid_trip_events(tmp_path: Path) -> None:
    # The start_time disagrees with the schedule, but the event is flagged mid-trip.
    (tmp_path / "trips.txt").write_text("trip_id,route_id,service_id\nT1,R1,weekday\n")
    (tmp_path / "stop_times.txt").write_text(
        "trip_id,stop_sequence,stop_id,arrival_time,departure_time\n"
        "T1,1,S1,09:00:00,09:00:00\nT1,2,S2,10:00:00,10:00:00\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\nS2\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time,start_mid_trip\n"
        "weekday,1,10,operator,T1,S1,08:30:00,S2,10:00:00,1\n"
    )
    _, findings = run(tmp_path)
    assert not any(f.rule_id == "TODS-W316" for f in findings)


def test_unreadable_vehicles_file_does_not_invent_e303(tmp_path: Path) -> None:
    # #125: an undecodable vehicles.txt used to count as present-but-empty,
    # so every real vehicle_id in vehicle_assignments.txt read as undefined.
    (tmp_path / "vehicles.txt").write_bytes(b"\xff\xfe\x00\x01garbage-not-utf8")
    (tmp_path / "vehicle_assignments.txt").write_text(
        "block_id,vehicle_id,service_id\nB1,bus-1,weekday\n"
    )
    _, findings = run(tmp_path)
    assert "TODS-E303" not in rule_ids(findings)
    assert "TODS-E103" in rule_ids(findings)  # the file itself is reported unreadable
    w302 = [f for f in findings if f.rule_id == "TODS-W302"]
    assert w302, "expected TODS-W302 to disclose that vehicles.txt could not be read"
    assert "vehicles.txt could not be read" in w302[0].message
    assert "TODS-E103" in w302[0].message


def test_unreadable_run_events_file_does_not_invent_e301(tmp_path: Path) -> None:
    # Same shape as above, on employee_run_dates.txt -> run_events.txt.
    (tmp_path / "run_events.txt").write_bytes(b"\xff\xfe\x00\x01garbage-not-utf8")
    (tmp_path / "employee_run_dates.txt").write_text(
        "employee_id,service_id,run_id,date\nE1,weekday,1,20260105\n"
    )
    _, findings = run(tmp_path)
    assert "TODS-E301" not in rule_ids(findings)
    assert "TODS-E103" in rule_ids(findings)
    w302 = [f for f in findings if f.rule_id == "TODS-W302"]
    assert w302, "expected TODS-W302 to disclose that run_events.txt could not be read"
    assert "run_events.txt could not be read" in w302[0].message


def test_unreadable_companion_trips_does_not_invent_e307(tmp_path: Path) -> None:
    # #125's headline repro: an undecodable companion trips.txt used to count
    # as present, so run_events.txt's trip_id references resolved against an
    # empty table and every one read as a dangling TODS-E307.
    (tmp_path / "trips.txt").write_bytes(b"\xff\xfe\x00\x01garbage-not-utf8")
    (tmp_path / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time\nweekday,1,10,operator,T1,S1,09:00:00,S1,10:00:00\n"
    )
    _, findings = run(tmp_path)
    assert "TODS-E307" not in rule_ids(findings)
    w302 = [f for f in findings if f.rule_id == "TODS-W302" and "trips.txt" in f.message]
    assert w302, "expected TODS-W302 to disclose that the companion trips.txt could not be read"
    assert "could not be read" in w302[0].message
    assert "has no trips.txt" not in w302[0].message  # distinct from the missing-file wording


def test_time_check_treats_2400_as_midnight(tmp_path: Path) -> None:
    # The event ends at 24:00:00 and the trip arrives at 24:00:00: equal, no W316.
    (tmp_path / "trips.txt").write_text("trip_id,route_id,service_id\nT1,R1,weekday\n")
    (tmp_path / "stop_times.txt").write_text(
        "trip_id,stop_sequence,stop_id,arrival_time,departure_time\n"
        "T1,1,S1,23:00:00,23:00:00\nT1,2,S2,24:00:00,24:00:00\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\nS2\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time\n"
        "weekday,1,10,operator,T1,S1,23:00:00,S2,24:00:00\n"
    )
    _, findings = run(tmp_path)
    assert not any(f.rule_id == "TODS-W316" for f in findings)


def test_ragged_companion_trips_does_not_invent_e307(tmp_path: Path) -> None:
    # The companion-GTFS half of #125's defect class. trips.txt parses, so it
    # counted as present; the ragged row dropped trip T1's trip_id; and the
    # run event that names T1 was reported as TODS-E307 -- an ERROR against
    # the producer's TODS file for a defect in their GTFS file, with a message
    # asserting T1 "does not exist in the companion GTFS trips.txt" when it
    # does. Nothing anywhere reported the ragged row itself.
    (tmp_path / "trips.txt").write_text(
        "route_id,service_id,trip_id,block_id\nR1,weekday,T1,B1\nR1,weekday\n"
    )
    (tmp_path / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time\nweekday,1,10,operator,T1,S1,09:00:00,S1,10:00:00\n"
    )
    _, findings = run(tmp_path)
    assert "TODS-E307" not in rule_ids(findings)
    w302 = [f for f in findings if f.rule_id == "TODS-W302" and "trips.txt" in f.message]
    assert w302, "expected TODS-W302 to disclose that the companion trips.txt was not read in full"
    assert "could not be read in full" in w302[0].message
    # Distinct from both of the other two wordings, so a reader can tell which
    # of the three remedies applies.
    assert "has no trips.txt" not in w302[0].message
    assert "trips.txt could not be read (" not in w302[0].message


def test_a_complete_companion_trips_still_reports_a_real_e307(tmp_path: Path) -> None:
    # Positive control for the test above: same feed, same run event, but a
    # trips.txt that reads in full and genuinely does not contain T1. TODS-E307
    # must still fire, or the test above could be green because E307 stopped
    # working rather than because it stopped being invented.
    (tmp_path / "trips.txt").write_text("route_id,service_id,trip_id,block_id\nR1,weekday,T2,B1\n")
    (tmp_path / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\n")
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
        "end_location,end_time\nweekday,1,10,operator,T1,S1,09:00:00,S1,10:00:00\n"
    )
    _, findings = run(tmp_path)
    assert "TODS-E307" in rule_ids(findings)
