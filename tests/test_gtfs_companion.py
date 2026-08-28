"""Supplement merge semantics and calendar date math.

The merge test reproduces the worked example from the spec's
"Supplement Files > Example" section verbatim.
"""

from datetime import date
from pathlib import Path

from tods_validate.gtfs_companion import build_companion, merge_supplement, parse_gtfs_date
from tods_validate.loader import load_package


def _write(tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / name).write_text(content, encoding="utf-8")


def test_merge_matches_spec_example(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "stops.txt",
        "stop_id,stop_name,stop_desc,stop_url\n"
        "1,One,Unmodified in TODS,example.com/1\n"
        "2,Two,Deleted in TODS,example.com/2\n"
        "3,Three,Will be modified in TODS,example.com/3\n",
    )
    _write(
        tmp_path,
        "stops_supplement.txt",
        "stop_id,stop_name,stop_desc,TODS_delete\n"
        "2,,,1\n"
        "3,,Has been modified by TODS,\n"
        "4,Four,New in TODS,\n",
    )
    package = load_package(tmp_path)
    effective = merge_supplement(
        package.get("stops.txt"), package.get("stops_supplement.txt"), ("stop_id",)
    )
    assert set(effective) == {("1",), ("3",), ("4",)}
    # Update: only non-empty values overwrite; stop_name "Three" is kept.
    assert effective[("3",)]["stop_name"] == "Three"
    assert effective[("3",)]["stop_desc"] == "Has been modified by TODS"
    assert effective[("3",)]["stop_url"] == "example.com/3"
    # Added row comes through wholesale (minus TODS_delete).
    assert effective[("4",)]["stop_name"] == "Four"
    assert "TODS_delete" not in effective[("4",)]


def test_calendar_dates_apply_exceptions(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "calendar.txt",
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "weekday,1,1,1,1,1,0,0,20260105,20260111\n",  # Mon Jan 5 - Sun Jan 11 2026
    )
    _write(
        tmp_path,
        "calendar_dates.txt",
        "service_id,date,exception_type\nweekday,20260107,2\nweekday,20260110,1\n",
    )
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    days = companion.service_dates["weekday"]
    assert date(2026, 1, 5) in days
    assert date(2026, 1, 7) not in days  # removed by exception_type 2
    assert date(2026, 1, 10) in days  # Saturday added by exception_type 1
    assert date(2026, 1, 11) not in days  # Sunday not in weekday pattern


def test_supplement_only_service_exists_without_base_calendar(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "calendar_supplement.txt",
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "crew,1,0,0,0,0,0,0,20260105,20260111\n",
    )
    package = load_package(tmp_path)
    companion = build_companion(None, package, source="test")
    assert "crew" in companion.service_ids
    assert companion.service_dates["crew"] == frozenset({date(2026, 1, 5)})


def test_base_keys_track_pre_supplement_rows(tmp_path: Path) -> None:
    _write(tmp_path, "stops.txt", "stop_id\ns1\n")
    _write(tmp_path, "stops_supplement.txt", "stop_id\ns2\n")
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert companion.base_keys["stops.txt"] == {("s1",)}
    assert companion.stop_ids == {"s1", "s2"}


def test_unreadable_base_file_is_treated_as_absent(tmp_path: Path) -> None:
    # An undecodable trips.txt must not count as present: every reference
    # into it would otherwise resolve against an empty table and read as
    # dangling instead of correctly unresolvable (#125).
    (tmp_path / "trips.txt").write_bytes(b"\xff\xfe\x00\x01garbage-not-utf8")
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert "trips.txt" not in companion.present
    assert companion.trip_service == {}
    assert companion.trip_block == {}
    assert "trips.txt" in companion.unreadable
    assert "trips.txt" in companion.unreadable["trips.txt"]  # names itself, like TODS-E103


def test_header_only_base_file_is_still_present(tmp_path: Path) -> None:
    # Contrast with the unreadable case above: a file that parses fine but
    # happens to have zero data rows is a legitimately empty table, not an
    # unreadable one, and must still count as present.
    _write(tmp_path, "trips.txt", "route_id,service_id,trip_id,block_id\n")
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert "trips.txt" in companion.present
    assert companion.unreadable == {}


def test_ragged_base_file_is_treated_as_absent(tmp_path: Path) -> None:
    # A trips.txt with a ragged row parses, so it used to count as present and
    # the reader silently held whatever the short row happened to yield. The
    # dropped trip_id is reported nowhere -- TODS-E104 scans the TODS package,
    # never the companion feed -- so every reference to it read as dangling.
    _write(
        tmp_path,
        "trips.txt",
        "route_id,service_id,trip_id,block_id\nR1,weekday,T1,B1\nR1,weekday\n",
    )
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert "trips.txt" not in companion.present
    assert companion.trip_service == {}
    assert companion.unreadable == {}  # it parsed; this is the other failure
    assert "trips.txt" in companion.degraded
    assert "row 3" in companion.degraded["trips.txt"]  # names where to look


def test_duplicate_column_base_file_is_treated_as_absent(tmp_path: Path) -> None:
    # The other degrading code: a column declared twice means the second
    # column's values were dropped, so the reader's ID set is short in a way
    # nothing on the TODS side reports.
    _write(tmp_path, "stops.txt", "stop_id,stop_name,stop_id\nS1,One,S2\n")
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert "stops.txt" not in companion.present
    assert companion.stop_ids == set()
    assert "stops.txt" in companion.degraded
    assert "stop_id" in companion.degraded["stops.txt"]


def test_degraded_reason_counts_the_problems_it_did_not_quote(tmp_path: Path) -> None:
    # One quoted message plus a count, so the report does not imply that
    # fixing the first ragged row is the whole job.
    _write(
        tmp_path,
        "trips.txt",
        "route_id,service_id,trip_id,block_id\nR1,weekday\nR1,weekday\nR1,weekday\n",
    )
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert "And 2 further problem(s) in the same file." in companion.degraded["trips.txt"]


def test_a_clean_base_file_is_present_and_not_degraded(tmp_path: Path) -> None:
    # Positive control for the three tests above. A change that emptied
    # `present` unconditionally would satisfy them and fail this one.
    _write(tmp_path, "trips.txt", "route_id,service_id,trip_id,block_id\nR1,weekday,T1,B1\n")
    package = load_package(tmp_path)
    companion = build_companion(package, package, source="test")
    assert "trips.txt" in companion.present
    assert companion.trip_service == {"T1": "weekday"}
    assert companion.degraded == {}
    assert companion.unreadable == {}


def test_parse_gtfs_date() -> None:
    assert parse_gtfs_date("20260229") is None  # 2026 is not a leap year
    assert parse_gtfs_date("2026-01-05") is None
    assert parse_gtfs_date("") is None
    assert parse_gtfs_date("20260105") == date(2026, 1, 5)
