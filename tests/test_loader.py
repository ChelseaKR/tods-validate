"""Loader behavior: directories, zips, encodings, malformed CSV."""

import zipfile
from pathlib import Path

import pytest

from conftest import VALID_TODS
from tods_validate.loader import PackageNotFoundError, load_package


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
