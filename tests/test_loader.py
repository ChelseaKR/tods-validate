"""Loader behavior: directories, zips, encodings, malformed CSV."""

import re
import zipfile
from pathlib import Path

import pytest

from conftest import VALID_TODS
from tods_validate import loader
from tods_validate.loader import (
    BLOCKING_PROBLEM_CODES,
    DEGRADING_PROBLEM_CODES,
    PROBLEM_CODES,
    PackageNotFoundError,
    load_package,
)

LOADER_SOURCE = Path(loader.__file__).read_text(encoding="utf-8")


def test_loads_directory() -> None:
    package = load_package(VALID_TODS)
    assert "run_events.txt" in package.files
    feed = package.files["run_events.txt"]
    assert feed.headers[0] == "service_id"
    assert feed.rows[0].line == 2  # header is line 1


def test_duplicate_header_keeps_first_occurrence(tmp_path: Path) -> None:
    # TODS-E105 states the duplicate column is ignored; confirm the first
    # occurrence's value is the one kept, not a later duplicate silently winning.
    (tmp_path / "run_events.txt").write_text("service_id,run_id,service_id\nfirst,10,second\n")
    package = load_package(tmp_path)
    feed = package.files["run_events.txt"]
    assert any(p.code == "duplicate_header" for p in feed.problems)
    assert feed.rows[0].values["service_id"] == "first"


def test_loads_zip(tmp_path: Path) -> None:
    archive = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for f in VALID_TODS.iterdir():
            zf.write(f, arcname=f.name)
    package = load_package(archive)
    assert set(package.files) == {f.name for f in VALID_TODS.iterdir()}


def test_zip_with_nested_directory_is_surfaced_not_guessed(tmp_path: Path) -> None:
    archive = tmp_path / "feed.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nested/run_events.txt", "service_id\n")
    package = load_package(archive)
    assert package.files == {}
    assert package.unparsed == ["nested/run_events.txt"]


def test_bom_is_stripped(tmp_path: Path) -> None:
    (tmp_path / "vehicles.txt").write_bytes(b"\xef\xbb\xbfvehicle_id\nbus-1\n")
    package = load_package(tmp_path)
    assert package.files["vehicles.txt"].headers == ("vehicle_id",)


def test_non_utf8_is_a_load_problem_not_a_crash(tmp_path: Path) -> None:
    (tmp_path / "vehicles.txt").write_bytes(b"vehicle_id\n\xff\xfe\n")
    package = load_package(tmp_path)
    problems = package.files["vehicles.txt"].problems
    assert [p.code for p in problems] == ["encoding"]
    assert "UTF-8" in problems[0].message


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "vehicles.txt").write_text("vehicle_id\n\nbus-1\n\n", encoding="utf-8")
    package = load_package(tmp_path)
    feed = package.files["vehicles.txt"]
    assert len(feed.rows) == 1
    assert feed.rows[0].line == 3  # original line number is preserved


def test_short_row_values_default_to_empty(tmp_path: Path) -> None:
    (tmp_path / "vehicles.txt").write_text("vehicle_id,vehicle_label\nbus-1\n", encoding="utf-8")
    package = load_package(tmp_path)
    feed = package.files["vehicles.txt"]
    assert feed.rows[0].values == {"vehicle_id": "bus-1", "vehicle_label": ""}
    assert [p.code for p in feed.problems] == ["ragged"]


def test_missing_path_raises() -> None:
    with pytest.raises(PackageNotFoundError):
        load_package("does-not-exist")


def test_regular_file_that_is_not_a_zip_raises(tmp_path: Path) -> None:
    plain = tmp_path / "feed.txt"
    plain.write_text("not a package", encoding="utf-8")
    with pytest.raises(PackageNotFoundError):
        load_package(plain)


def test_every_problem_code_the_parser_emits_is_classified() -> None:
    # BLOCKING_PROBLEM_CODES and DEGRADING_PROBLEM_CODES together decide
    # whether a file is trustworthy enough to resolve another file's
    # references against. A code that belongs to neither would be read as
    # harmless by default, which is the fail-open this split exists to close.
    emitted = set(re.findall(r'code="([a-z_]+)"', LOADER_SOURCE))
    assert emitted, "expected to find problem codes in the loader source"
    assert emitted == PROBLEM_CODES
    assert not (BLOCKING_PROBLEM_CODES & DEGRADING_PROBLEM_CODES)


def test_fully_read_is_stricter_than_readable(tmp_path: Path) -> None:
    # A ragged row leaves the file readable: it has a header and rows. It does
    # not leave it fully read, because the row's values could not be placed.
    (tmp_path / "trips.txt").write_text("route_id,service_id,trip_id\nR1,weekday\n")
    feed = load_package(tmp_path).files["trips.txt"]
    assert feed.readable
    assert not feed.fully_read
    assert [p.code for p in feed.problems] == ["ragged"]


def test_a_clean_file_is_both_readable_and_fully_read(tmp_path: Path) -> None:
    # Positive control for the two tests above: without this, a bug that made
    # fully_read always False would still turn them green.
    (tmp_path / "trips.txt").write_text("route_id,service_id,trip_id\nR1,weekday,T1\n")
    feed = load_package(tmp_path).files["trips.txt"]
    assert feed.readable
    assert feed.fully_read
    assert feed.problems == []


def test_repeated_cell_values_share_one_string(tmp_path: Path) -> None:
    # The per-file value pool (FIX-04): equal cells in the same file are the
    # same object, so a column like service_id costs one string rather than one
    # per row. Identity is the only way to observe this, since every version of
    # the code produces equal values.
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_type\nweekday,1,operator\nweekday,2,operator\nweekday,3,operator\n"
    )
    rows = load_package(tmp_path).files["run_events.txt"].rows
    assert [r.values["service_id"] for r in rows] == ["weekday"] * 3
    assert len({id(r.values["service_id"]) for r in rows}) == 1
    assert len({id(r.values["event_type"]) for r in rows}) == 1
    # Distinct values stay distinct objects; pooling shares, it does not merge.
    assert len({id(r.values["run_id"]) for r in rows}) == 3


def test_the_value_pool_does_not_leak_across_files(tmp_path: Path) -> None:
    # Positive control, and the reason this is a per-file dict rather than
    # sys.intern: interned strings live until the interpreter exits, which in
    # the long-running LSP server would make every feed a user opens permanent.
    (tmp_path / "run_events.txt").write_text("service_id,run_id\nweekday,1\n")
    (tmp_path / "vehicles.txt").write_text("vehicle_id,vehicle_label\nweekday,1\n")
    package = load_package(tmp_path)
    first = package.files["run_events.txt"].rows[0].values["service_id"]
    second = package.files["vehicles.txt"].rows[0].values["vehicle_id"]
    assert first == second == "weekday"
    assert first is not second
