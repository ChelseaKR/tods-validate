"""The merge subcommand and merge_feeds: producing TODS-Supplemented GTFS."""

import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from conftest import VALID_GTFS, VALID_TODS
from tods_validate.cli import main
from tods_validate.loader import PackageNotFoundError
from tods_validate.merge import merge_feeds


def test_merge_valid_feed_to_directory(tmp_path: Path) -> None:
    out = tmp_path / "merged"
    result = merge_feeds(VALID_TODS, VALID_GTFS, out)

    stops = (out / "stops.txt").read_text(encoding="utf-8")
    assert "garage" in stops  # added by stops_supplement.txt
    assert "stop-1" in stops  # original rows preserved
    trips = (out / "trips.txt").read_text(encoding="utf-8")
    assert "deadhead-1" in trips
    calendar = (out / "calendar.txt").read_text(encoding="utf-8")
    assert "crew-weekday" in calendar

    # GTFS files without a supplement are copied through byte-for-byte.
    assert (out / "agency.txt").read_bytes() == (VALID_GTFS / "agency.txt").read_bytes()
    # TODS files are not part of the merged GTFS feed.
    assert not (out / "run_events.txt").exists()
    assert not (out / "stops_supplement.txt").exists()
    assert "stops.txt" in result.written
    assert result.stats["stops.txt"].added == 2


def test_merge_to_zip(tmp_path: Path) -> None:
    out = tmp_path / "merged.zip"
    merge_feeds(VALID_TODS, VALID_GTFS, out)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert {"agency.txt", "stops.txt", "trips.txt", "calendar.txt"} <= names
    assert not any(n.endswith("_supplement.txt") for n in names)


def test_merge_matches_spec_example(tmp_path: Path) -> None:
    """Reproduces the spec's 'Supplement Files > Example' end to end."""
    feed = tmp_path / "feed"
    feed.mkdir()
    (feed / "stops.txt").write_text(
        "stop_id,stop_name,stop_desc,stop_url\n"
        "1,One,Unmodified in TODS,example.com/1\n"
        "2,Two,Deleted in TODS,example.com/2\n"
        "3,Three,Will be modified in TODS,example.com/3\n",
        encoding="utf-8",
    )
    (feed / "stops_supplement.txt").write_text(
        "stop_id,stop_name,stop_desc,TODS_delete\n"
        "2,,,1\n"
        "3,,Has been modified by TODS,\n"
        "4,Four,New in TODS,\n",
        encoding="utf-8",
    )
    out = tmp_path / "merged"
    result = merge_feeds(feed, None, out)

    merged = (out / "stops.txt").read_text(encoding="utf-8").splitlines()
    assert merged[0] == "stop_id,stop_name,stop_desc,stop_url"
    assert merged[1] == "1,One,Unmodified in TODS,example.com/1"
    assert merged[2] == "3,Three,Has been modified by TODS,example.com/3"
    assert merged[3] == "4,Four,New in TODS,"
    assert len(merged) == 4
    stats = result.stats["stops.txt"]
    assert (stats.updated, stats.added, stats.deleted) == (1, 1, 1)


def test_merge_supplement_only_creates_the_base_file(tmp_path: Path) -> None:
    feed = tmp_path / "feed"
    feed.mkdir()
    (feed / "calendar_supplement.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "crew,1,0,0,0,0,0,0,20260101,20261231\n",
        encoding="utf-8",
    )
    out = tmp_path / "merged"
    merge_feeds(feed, None, out)
    assert "crew" in (out / "calendar.txt").read_text(encoding="utf-8")


def test_merge_nothing_to_do_raises(tmp_path: Path) -> None:
    empty = tmp_path / "feed"
    empty.mkdir()
    with pytest.raises(PackageNotFoundError, match="nothing to merge"):
        merge_feeds(empty, None, tmp_path / "out")


def test_cli_merge_reports_stats(tmp_path: Path) -> None:
    out = tmp_path / "merged.zip"
    result = CliRunner().invoke(
        main,
        ["merge", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert "stops.txt: 2 added" in result.output
    assert "Wrote" in result.output
    assert out.exists()


def test_cli_bare_path_still_validates() -> None:
    """Backward compatibility: tods-validate PATH routes to validate."""
    result = CliRunner().invoke(main, [str(VALID_TODS), "--gtfs", str(VALID_GTFS)])
    assert result.exit_code == 0, result.output
    assert "No problems found." in result.output


def test_cli_explicit_validate_subcommand() -> None:
    result = CliRunner().invoke(main, ["validate", str(VALID_TODS)])
    assert result.exit_code == 0, result.output
