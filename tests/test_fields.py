"""Field rules (TODS-x2xx) and the GTFS time parser."""

from pathlib import Path

import pytest

from conftest import rule_ids, run_invalid_fixture
from tods_validate.findings import Finding
from tods_validate.rules.fields import parse_time
from tods_validate.runner import run
from tods_validate.schema import GTFS_FIELDS, GTFS_REQUIRED_FIELDS

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


@pytest.mark.parametrize(
    "value",
    [
        "",
        "9am",
        "09:75:00",
        "09:00",
        "09:00:0",
        "-1:00:00",
        "１２:34:56",
        "12:３４:56",
        "12:34:５６",
    ],
)
def test_parse_time_rejects_bad_times(value: str) -> None:
    assert parse_time(value) is None


def test_parse_time_rejects_absurdly_long_hour_without_crashing() -> None:
    assert parse_time(f"{'9' * 100_000}:00:00") is None


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


def test_employee_assignment_duplicate_is_primary_key_error() -> None:
    findings = run_invalid_fixture("TODS-W408")
    e204 = [f for f in findings if f.rule_id == "TODS-E204"]
    assert len(e204) == 1
    assert e204[0].row == 3
    assert "employee_id='emp-1'" in e204[0].message
    assert e204[0].suggestion == "Remove the duplicate assignment row."


def _write_routes_pair(tmp_path: Path, supplement_row: str) -> tuple[Path, Path]:
    tods = tmp_path / "tods"
    gtfs = tmp_path / "gtfs"
    tods.mkdir()
    gtfs.mkdir()
    (tods / "routes_supplement.txt").write_text(
        f"route_id,route_long_name,route_type,TODS_delete\n{supplement_row}\n",
        encoding="utf-8",
    )
    (gtfs / "routes.txt").write_text(
        "route_id,route_short_name,route_type\nexisting,10,3\n",
        encoding="utf-8",
    )
    return tods, gtfs


def test_added_supplement_row_requires_gtfs_required_fields(tmp_path: Path) -> None:
    tods, gtfs = _write_routes_pair(tmp_path, "new-route,New Route,,")
    _, findings = run(tods, gtfs)
    e201 = [f for f in findings if f.rule_id == "TODS-E201"]
    assert [(f.row, f.field) for f in e201] == [(2, "route_type")]
    assert "added routes.txt row" in e201[0].message


@pytest.mark.parametrize(
    "supplement_row",
    [
        "existing,Updated Name,,",
        "existing,,,1",
    ],
)
def test_update_or_delete_does_not_require_added_row_fields(
    tmp_path: Path, supplement_row: str
) -> None:
    tods, gtfs = _write_routes_pair(tmp_path, supplement_row)
    _, findings = run(tods, gtfs)
    assert not [f for f in findings if f.rule_id == "TODS-E201"]


def test_added_row_check_stays_permissive_without_companion_gtfs(tmp_path: Path) -> None:
    (tmp_path / "routes_supplement.txt").write_text(
        "route_id,route_long_name\nnew-route,New Route\n",
        encoding="utf-8",
    )
    _, findings = run(tmp_path)
    assert not [f for f in findings if f.rule_id == "TODS-E201"]


def test_gtfs_required_field_inventory_matches_current_reference() -> None:
    assert GTFS_REQUIRED_FIELDS == {
        "trips.txt": ("route_id", "service_id", "trip_id"),
        "stops.txt": ("stop_id",),
        "stop_times.txt": ("trip_id", "stop_sequence"),
        "routes.txt": ("route_id", "route_type"),
        "calendar.txt": (
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ),
        "calendar_dates.txt": ("service_id", "date", "exception_type"),
    }


def test_current_optional_gtfs_fields_are_allowed_in_supplements() -> None:
    assert {"safe_duration_factor", "safe_duration_offset"} <= set(GTFS_FIELDS["trips.txt"])
    assert "stop_access" in GTFS_FIELDS["stops.txt"]
    assert "cemv_support" in GTFS_FIELDS["routes.txt"]


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


def test_out_of_range_latitude_is_flagged_and_valid_longitude_is_not(tmp_path: Path) -> None:
    # ops_locations.txt is a v1.0.0 table; ops_location_lat/lon are the spec
    # Latitude/Longitude types. A latitude of 200 is out of the -90..90 range and
    # must trip TODS-E203, while the valid longitude beside it must stay silent.
    (tmp_path / "ops_locations.txt").write_text(
        "ops_location_id,ops_location_code,ops_location_name,ops_location_desc,"
        "ops_location_lat,ops_location_lon\n"
        "GARAGE,G1,Main Garage,,200.0,-121.7405\n"
    )
    _, findings = run(tmp_path, spec_version="1.0.0")
    e203 = [f for f in findings if f.rule_id == "TODS-E203"]
    assert [f.field for f in e203] == ["ops_location_lat"]
    assert "200.0" in e203[0].message


def test_negative_non_negative_float_is_flagged(tmp_path: Path) -> None:
    # shape_dist_traveled on deadhead_times.txt is a Non-negative float; a negative
    # distance must trip TODS-E203, and a non-numeric one likewise.
    (tmp_path / "deadhead_times.txt").write_text(
        "deadhead_id,arrival_time,departure_time,ops_location_id,stop_id,"
        "location_sequence,shape_dist_traveled\n"
        "DH1,07:30:00,07:45:00,GARAGE,,1,-5.0\n"
        "DH2,07:30:00,07:45:00,GARAGE,,2,abc\n"
    )
    _, findings = run(tmp_path, spec_version="1.0.0")
    e203 = [f for f in findings if f.rule_id == "TODS-E203" and f.field == "shape_dist_traveled"]
    assert {f.row for f in e203} == {2, 3}


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
