"""EXP-02: GTFS-drift analysis (tods_validate.drift)."""

from pathlib import Path

from tods_validate.drift import (
    analyze_drift,
    drift_to_dict,
    render_drift_markdown,
    render_drift_text,
)
from tods_validate.loader import load_package


def _write(dir_path: Path, name: str, content: str) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / name).write_text(content, encoding="utf-8")


def _make_tods(dir_path: Path) -> None:
    _write(
        dir_path,
        "run_events.txt",
        "service_id,run_id,event_sequence,piece_id,block_id,job_type,event_type,"
        "trip_id,start_location,start_time,start_mid_trip,end_location,end_time,end_mid_trip\n"
        "weekday,1,10,1-1,BLOCK-A,Operator,Operator,101,stop-1,10:00:00,2,stop-2,10:50:00,2\n"
        "weekday,1,20,1-1,BLOCK-A,Operator,Operator,102,stop-2,11:00:00,2,stop-1,11:50:00,2\n",
    )


def _make_gtfs(
    dir_path: Path,
    *,
    trip_102_id: str = "102",
    block_102: str = "BLOCK-A",
    stop_2_id: str = "stop-2",
) -> None:
    _write(
        dir_path,
        "trips.txt",
        "route_id,service_id,trip_id,block_id\n"
        f"R1,weekday,101,BLOCK-A\n"
        f"R1,weekday,{trip_102_id},{block_102}\n",
    )
    _write(
        dir_path,
        "stops.txt",
        "stop_id,stop_name\nstop-1,First\n" + f"{stop_2_id},Second\n",
    )
    _write(
        dir_path,
        "stop_times.txt",
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "101,10:00:00,10:00:00,stop-1,1\n"
        "101,10:50:00,10:50:00,stop-2,2\n"
        f"{trip_102_id},11:00:00,11:00:00,{stop_2_id},1\n"
        f"{trip_102_id},11:50:00,11:50:00,stop-1,2\n",
    )


def test_no_breaks_when_gtfs_is_unchanged(tmp_path: Path) -> None:
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _make_gtfs(old_dir)
    _make_gtfs(new_dir)
    _make_tods(tods_dir)

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert not report.has_breaks
    assert report.broken_trip_ids == ()
    assert report.broken_stop_ids == ()
    assert report.changed_blocks == ()
    assert "No referenced" in render_drift_text(report)
    assert "No referenced" in render_drift_markdown(report)


def test_renamed_trip_id_is_reported_with_unique_candidate(tmp_path: Path) -> None:
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _make_gtfs(old_dir)
    _make_gtfs(new_dir, trip_102_id="102A")  # renamed, single close match
    _make_tods(tods_dir)

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert report.has_breaks
    assert len(report.broken_trip_ids) == 1
    broken = report.broken_trip_ids[0]
    assert broken.value == "102"
    assert broken.candidates == ("102A",)
    assert "run_events.txt:3" in broken.used_by


def test_renamed_stop_id_is_reported(tmp_path: Path) -> None:
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _make_gtfs(old_dir)
    _make_gtfs(new_dir, stop_2_id="stop-02")
    _make_tods(tods_dir)

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert len(report.broken_stop_ids) == 1
    broken = report.broken_stop_ids[0]
    assert broken.value == "stop-2"
    assert broken.candidates == ("stop-02",)
    # Referenced as both an end_location (row 2) and a start_location (row 3).
    assert len(broken.used_by) == 2


def test_block_change_is_reported_for_a_trip_present_in_both(tmp_path: Path) -> None:
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _make_gtfs(old_dir)
    _make_gtfs(new_dir, block_102="BLOCK-B")
    _make_tods(tods_dir)

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert len(report.changed_blocks) == 1
    change = report.changed_blocks[0]
    assert change.trip_id == "102"
    assert change.old_block == "BLOCK-A"
    assert change.new_block == "BLOCK-B"


def test_ambiguous_rename_proposes_no_candidate(tmp_path: Path) -> None:
    """Two equally-plausible new IDs is ambiguity, not a rename -- say nothing."""
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _write(old_dir, "trips.txt", "route_id,service_id,trip_id,block_id\nR1,weekday,102,BLOCK-A\n")
    _write(
        new_dir,
        "trips.txt",
        "route_id,service_id,trip_id,block_id\nR1,weekday,102A,BLOCK-A\nR1,weekday,102B,BLOCK-A\n",
    )
    for d in (old_dir, new_dir):
        _write(d, "stops.txt", "stop_id,stop_name\nstop-1,First\n")
        _write(d, "stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
    _make_tods(tods_dir)

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert len(report.broken_trip_ids) == 1
    assert report.broken_trip_ids[0].candidates == ()


def test_render_markdown_and_dict_shapes(tmp_path: Path) -> None:
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _make_gtfs(old_dir)
    _make_gtfs(new_dir, trip_102_id="102A")
    _make_tods(tods_dir)

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    md = render_drift_markdown(report)
    assert "Broken `trip_id` references" in md
    assert "`102`" in md
    assert "`102A`" in md

    payload = drift_to_dict(report)
    assert payload["brokenTripIds"][0]["value"] == "102"
    assert payload["brokenTripIds"][0]["candidates"] == ["102A"]
    assert payload["oldSource"] == str(old_dir)


def test_no_run_events_file_means_no_references_at_all(tmp_path: Path) -> None:
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _make_gtfs(old_dir)
    _make_gtfs(new_dir, trip_102_id="102A")  # would otherwise be a break
    tods_dir.mkdir()  # no run_events.txt at all

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert not report.has_breaks


def test_render_text_and_markdown_cover_all_break_kinds_and_many_uses(tmp_path: Path) -> None:
    """One scenario with a trip break, a stop break, and a block change, plus a
    reference used more than 3 times, to exercise the "+N more" summarizing
    and every section of both renderers."""
    old_dir, new_dir, tods_dir = tmp_path / "old", tmp_path / "new", tmp_path / "tods"
    _write(
        old_dir,
        "trips.txt",
        "route_id,service_id,trip_id,block_id\n"
        "R1,weekday,101,BLOCK-A\n"
        "R1,weekday,102,BLOCK-A\n"
        "R1,weekday,103,BLOCK-A\n",
    )
    _write(
        new_dir,
        "trips.txt",
        "route_id,service_id,trip_id,block_id\n"
        "R1,weekday,101,BLOCK-A\n"
        "R1,weekday,103,BLOCK-B\n",  # 102 renamed away (dropped -> no candidate), 103 rebocked
    )
    for d in (old_dir, new_dir):
        _write(d, "stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n")
    _write(old_dir, "stops.txt", "stop_id,stop_name\nstop-1,First\nstop-9,Ninth\n")
    _write(new_dir, "stops.txt", "stop_id,stop_name\nstop-1,First\n")  # stop-9 dropped
    _write(
        tods_dir,
        "run_events.txt",
        "service_id,run_id,event_sequence,piece_id,block_id,job_type,event_type,"
        "trip_id,start_location,start_time,start_mid_trip,end_location,end_time,end_mid_trip\n"
        "weekday,1,10,,,Operator,Report Time,,stop-9,09:30:00,,stop-9,09:30:00,\n"
        "weekday,1,20,,,Operator,Break,,stop-9,09:35:00,,stop-9,09:45:00,\n"
        "weekday,1,30,1-1,BLOCK-A,Operator,Operator,102,stop-1,10:00:00,2,stop-9,10:50:00,2\n"
        "weekday,1,40,1-1,BLOCK-A,Operator,Operator,103,stop-1,11:00:00,2,stop-1,11:50:00,2\n",
    )

    report = analyze_drift(load_package(old_dir), load_package(new_dir), load_package(tods_dir))

    assert len(report.broken_trip_ids) == 1
    assert report.broken_trip_ids[0].candidates == ()  # dropped, not renamed: no false guess
    assert len(report.broken_stop_ids) == 1
    # stop-9 appears as start_location twice, end_location three times.
    assert len(report.broken_stop_ids[0].used_by) == 5
    assert len(report.changed_blocks) == 1

    text = render_drift_text(report)
    assert "+2 more" in text  # 5 uses of stop-9, only first 3 summarized
    assert "broken trip_id references: 1" in text
    assert "trips whose block_id changed: 1" in text

    md = render_drift_markdown(report)
    assert "Broken `trip_id` references" in md
    assert "Broken `stop_id` references" in md
    assert "Trips whose `block_id` changed" in md
    assert "`103`" in md
    assert "BLOCK-A" in md
    assert "BLOCK-B" in md
