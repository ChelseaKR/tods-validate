"""Semantic package diff (#188): what changed in the operational data.

Two claims are under test. The comparison is keyed on the spec's primary keys,
so reordering a file is not a difference and a shifted time is one change with
its old and new values. And a comparison that could not be completed never
reports itself as a clean one: an unreadable file is named rather than reported
as every row deleted, a duplicate primary key is named rather than merged, and
both exit 2 rather than 0.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from tods_validate.cli import main
from tods_validate.loader import load_package
from tods_validate.pickdiff import (
    analyze_pickdiff,
    anonymize_pickdiff,
    pickdiff_to_dict,
    render_pickdiff_markdown,
    render_pickdiff_text,
)

_EVENTS_HEADER = (
    "service_id,run_id,event_sequence,piece_id,block_id,job_type,event_type,"
    "trip_id,start_location,start_time,start_mid_trip,end_location,end_time,end_mid_trip"
)
_EVENT_10 = "weekday,1,10,1-1,BLOCK-A,Operator,Operator,101,stop-1,10:00:00,2,stop-2,10:50:00,2"
_EVENT_20 = "weekday,1,20,1-1,BLOCK-A,Operator,Operator,102,stop-2,11:00:00,2,stop-1,11:50:00,2"
_EVENT_30 = "weekday,2,10,2-1,BLOCK-B,Operator,Operator,103,stop-1,12:00:00,2,stop-2,12:50:00,2"

_ERD_HEADER = "date,service_id,run_id,employee_id"
_ERD_ROW = "20260106,weekday,1,emp-100"


def _package(root: Path, name: str, events: list[str], employees: list[str] | None = None) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "run_events.txt").write_text(
        "\n".join([_EVENTS_HEADER, *events]) + "\n", encoding="utf-8"
    )
    if employees is not None:
        (path / "employee_run_dates.txt").write_text(
            "\n".join([_ERD_HEADER, *employees]) + "\n", encoding="utf-8"
        )
    return path


def _diff(old: Path, new: Path):
    return analyze_pickdiff(load_package(str(old)), load_package(str(new)))


def _events_diff(report):
    return next(f for f in report.files if f.file == "run_events.txt")


# --- the issue's own acceptance criteria -------------------------------------


def test_a_package_against_a_copy_reports_no_differences(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10, _EVENT_20])
    report = _diff(old, new)
    assert not report.has_changes
    assert report.incomplete == ()
    assert "No differences." in render_pickdiff_text(report)


def test_one_shifted_end_time_is_one_change_with_old_and_new_and_its_run(
    tmp_path: Path,
) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10.replace("10:50:00", "11:20:00"), _EVENT_20])
    events = _events_diff(_diff(old, new))
    assert (len(events.added), len(events.removed), len(events.changed)) == (0, 0, 1)
    change = events.changed[0]
    assert change.key == ("weekday", "1", "10")
    assert change.changes == (("end_time", "10:50:00", "11:20:00"),)
    rollup = _diff(old, new).run_rollup
    assert [(r.service_id, r.run_id, r.changed) for r in rollup] == [("weekday", "1", 1)]


def test_reordered_rows_produce_no_differences(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20, _EVENT_30])
    new = _package(tmp_path, "new", [_EVENT_30, _EVENT_20, _EVENT_10])
    assert not _diff(old, new).has_changes


def test_a_duplicate_primary_key_is_reported_not_silently_merged(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10, _EVENT_20, _EVENT_20])
    report = _diff(old, new)
    events = _events_diff(report)
    assert events.duplicate_keys == (("NEW", ("weekday", "1", "20")),)
    # Reported *and* refused: the later row was matched against nothing, so
    # "no differences" is not a claim this run is entitled to make.
    assert events.file in [f.file for f in report.incomplete]
    text = render_pickdiff_text(report)
    assert "more than one row with primary key" in text
    assert "which is not the same claim as no differences" in text


def test_an_unreadable_new_is_refused_not_reported_as_everything_removed(
    tmp_path: Path,
) -> None:
    """The failure this bucket exists for.

    An unreadable file has zero rows. A comparison that trusted the row count
    would announce every run in the pick as removed, which is a data loss
    report manufactured out of a read error.
    """
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20, _EVENT_30])
    new = _package(tmp_path, "new", [_EVENT_10])
    (new / "run_events.txt").write_bytes(b"\xff\xfe\x00not utf-8")
    report = _diff(old, new)
    events = _events_diff(report)
    assert events.not_compared_kind == "unreadable"
    assert (events.added, events.removed, events.changed) == ((), (), ())
    assert report.runs_removed == ()
    assert report.runs_added == ()
    assert "NOT COMPARED" in render_pickdiff_text(report)
    assert "not removed" in events.not_compared


def test_an_unreadable_file_leaves_the_minutes_unmeasured_rather_than_zero(
    tmp_path: Path,
) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10])
    (new / "run_events.txt").write_bytes(b"\xff\xfe\x00not utf-8")
    report = _diff(old, new)
    assert report.minutes.partial is True
    assert "not measured" in render_pickdiff_text(report)
    # A consumer reading the JSON must be able to tell "0 minutes changed" from
    # "nobody counted", so the flag travels with the numbers.
    assert pickdiff_to_dict(report)["minutes"]["partial"] is True


# --- runs, rollup, minutes ---------------------------------------------------


def test_a_new_run_is_reported_as_added_and_an_absent_one_as_removed(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10, _EVENT_20, _EVENT_30])
    report = _diff(old, new)
    assert report.runs_added == (("weekday", "2"),)
    assert report.runs_removed == ()
    assert _diff(new, old).runs_removed == (("weekday", "2"),)


def test_revenue_minutes_move_with_a_lengthened_trip_event(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10])
    new = _package(tmp_path, "new", [_EVENT_10.replace("10:50:00", "11:20:00")])
    minutes = _diff(old, new).minutes
    assert (minutes.old_revenue, minutes.new_revenue, minutes.revenue_delta) == (50, 80, 30)
    assert minutes.nonrevenue_delta == 0
    assert minutes.partial is False


def test_a_non_revenue_event_moves_the_other_total(tmp_path: Path) -> None:
    deadhead = _EVENT_10.replace(",101,", ",,")
    old = _package(tmp_path, "old", [deadhead])
    new = _package(tmp_path, "new", [deadhead.replace("10:50:00", "11:20:00")])
    minutes = _diff(old, new).minutes
    assert minutes.revenue_delta == 0
    assert (minutes.old_nonrevenue, minutes.new_nonrevenue) == (50, 80)


# --- what the comparison will not pretend to do ------------------------------


def test_a_file_with_no_primary_key_is_named_not_compared_by_row_position(
    tmp_path: Path,
) -> None:
    """v1.0.0 declares no primary key for run_events.txt.

    Falling back to row position would report a single inserted row as every
    later row changing, which is a diff of the file's shape, not its content.
    """
    old = tmp_path / "v1old"
    new = tmp_path / "v1new"
    for path in (old, new):
        path.mkdir()
        (path / "runs_pieces.txt").write_text(
            "run_id,piece_id,start_type,start_trip_id,end_type,end_trip_id\n1,p1,1,101,1,102\n",
            encoding="utf-8",
        )
        (path / "deadheads.txt").write_text(
            "deadhead_id,service_id,block_id\nd1,weekday,BLOCK-A\n", encoding="utf-8"
        )
    report = analyze_pickdiff(load_package(str(old)), load_package(str(new)), spec_version="1.0.0")
    unkeyed = [f for f in report.files if f.not_compared_kind == "unkeyed"]
    assert "deadheads.txt" in [f.file for f in unkeyed]
    # runs_pieces.txt states "must be unique" in the spec, so it does have one.
    pieces = next(f for f in report.files if f.file == "runs_pieces.txt")
    assert pieces.not_compared is None
    assert "No differences in the" in render_pickdiff_text(report)


def test_a_column_that_only_new_declares_is_a_change_not_an_invisible_one(
    tmp_path: Path,
) -> None:
    old = _package(tmp_path, "old", [_EVENT_10])
    new = tmp_path / "new"
    new.mkdir()
    (new / "run_events.txt").write_text(
        f"{_EVENTS_HEADER},TODS_extra\n{_EVENT_10},yes\n", encoding="utf-8"
    )
    events = _events_diff(_diff(old, new))
    assert events.changed[0].changes == (("TODS_extra", "", "yes"),)


# --- anonymize ---------------------------------------------------------------


def test_anonymize_pseudonymizes_the_employee_id_consistently_on_both_sides(
    tmp_path: Path,
) -> None:
    old = _package(tmp_path, "old", [_EVENT_10], employees=[_ERD_ROW])
    new = _package(
        tmp_path,
        "new",
        [_EVENT_10],
        employees=[_ERD_ROW.replace("weekday,1,", "weekday,2,")],
    )
    report = anonymize_pickdiff(_diff(old, new), salt="fixed-for-this-test")
    erd = next(f for f in report.files if f.file == "employee_run_dates.txt")
    added = erd.added[0].key[-1]
    removed = erd.removed[0].key[-1]
    assert added.startswith("emp_")
    # The same employee moved between runs, so both sides must pseudonymize to
    # the same token or the report stops being readable as a move.
    assert added == removed
    assert "emp-100" not in render_pickdiff_text(report)


def test_anonymize_leaves_schedule_identifiers_alone(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10], employees=[_ERD_ROW])
    new = _package(
        tmp_path, "new", [_EVENT_10.replace("10:50:00", "11:20:00")], employees=[_ERD_ROW]
    )
    report = anonymize_pickdiff(_diff(old, new), salt="fixed-for-this-test")
    text = render_pickdiff_text(report)
    assert "weekday" in text
    assert "end_time" in text


def test_two_anonymize_runs_without_a_salt_do_not_share_a_mapping(tmp_path: Path) -> None:
    """The default is irreversible, which means not comparable across runs."""
    old = _package(tmp_path, "old", [_EVENT_10], employees=[_ERD_ROW])
    new = _package(tmp_path, "new", [_EVENT_10], employees=[])
    first = anonymize_pickdiff(_diff(old, new))
    second = anonymize_pickdiff(_diff(old, new))
    erd_first = next(f for f in first.files if f.file == "employee_run_dates.txt")
    erd_second = next(f for f in second.files if f.file == "employee_run_dates.txt")
    assert erd_first.removed[0].key != erd_second.removed[0].key


# --- renderers and the CLI ---------------------------------------------------


def test_json_and_markdown_carry_the_same_findings_as_text(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10.replace("10:50:00", "11:20:00"), _EVENT_30])
    report = _diff(old, new)
    payload = pickdiff_to_dict(report)
    assert payload["has_changes"] is True
    assert payload["runs_added"] == [["weekday", "2"]]
    assert payload["runs_removed"] == []
    events = next(f for f in payload["files"] if f["file"] == "run_events.txt")
    assert events["changed"][0]["changes"] == [
        {"field": "end_time", "old": "10:50:00", "new": "11:20:00"}
    ]
    markdown = render_pickdiff_markdown(report)
    assert "`end_time`: `10:50:00` -> `11:20:00`" in markdown
    assert "11:20:00" in render_pickdiff_text(report)


def test_cli_exit_codes(tmp_path: Path) -> None:
    runner = CliRunner()
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    same = _package(tmp_path, "same", [_EVENT_10, _EVENT_20])
    changed = _package(tmp_path, "changed", [_EVENT_10.replace("10:50:00", "11:20:00")])

    assert runner.invoke(main, ["pickdiff", str(old), str(same)]).exit_code == 0
    assert runner.invoke(main, ["pickdiff", str(old), str(changed)]).exit_code == 1

    broken = _package(tmp_path, "broken", [_EVENT_10])
    (broken / "run_events.txt").write_bytes(b"\xff\xfe\x00not utf-8")
    unreadable = runner.invoke(main, ["pickdiff", str(old), str(broken)])
    assert unreadable.exit_code == 2, unreadable.output
    assert "NOT COMPARED" in unreadable.output

    missing = runner.invoke(main, ["pickdiff", str(old), str(tmp_path / "nowhere")])
    assert missing.exit_code == 2


def test_cli_json_output_parses(tmp_path: Path) -> None:
    runner = CliRunner()
    old = _package(tmp_path, "old", [_EVENT_10])
    new = _package(tmp_path, "new", [_EVENT_10])
    result = runner.invoke(main, ["pickdiff", str(old), str(new), "--format", "json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["has_changes"] is False


def test_cli_rejects_an_unsupported_spec_version(tmp_path: Path) -> None:
    runner = CliRunner()
    old = _package(tmp_path, "old", [_EVENT_10])
    result = runner.invoke(main, ["pickdiff", str(old), str(old), "--spec-version", "9.9.9"])
    assert result.exit_code == 2


def test_markdown_states_an_incomplete_comparison_as_prominently_as_the_text_does(
    tmp_path: Path,
) -> None:
    """The renderers must not disagree about whether a run is trustworthy.

    A reader who is handed the Markdown and not the terminal output has to see
    the same refusal; a caveat that survives only in one format is a caveat
    that gets cropped off.
    """
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10, _EVENT_20, _EVENT_20])
    (new / "employee_run_dates.txt").write_bytes(b"\xff\xfe\x00not utf-8")
    markdown = render_pickdiff_markdown(_diff(old, new))
    assert "**employee_run_dates.txt was not compared.**" in markdown
    assert "duplicate primary key" in markdown
    assert "not the same claim as no differences" in markdown


def test_markdown_renders_runs_the_rollup_and_the_row_table(tmp_path: Path) -> None:
    old = _package(tmp_path, "old", [_EVENT_10, _EVENT_20])
    new = _package(tmp_path, "new", [_EVENT_10.replace("10:50:00", "11:20:00"), _EVENT_30])
    markdown = render_pickdiff_markdown(_diff(old, new))
    assert "## Runs" in markdown
    assert "- added: `weekday` / `2`" in markdown
    assert "## Rows" in markdown
    assert "| `run_events.txt` |" in markdown
    assert "## Events changed per run" in markdown
    assert "## Totals" in markdown


def test_markdown_says_not_measured_when_the_minutes_were_not_measured(
    tmp_path: Path,
) -> None:
    old = _package(tmp_path, "old", [_EVENT_10])
    new = _package(tmp_path, "new", [_EVENT_10])
    (new / "run_events.txt").write_bytes(b"\xff\xfe\x00not utf-8")
    assert "not measured" in render_pickdiff_markdown(_diff(old, new))
