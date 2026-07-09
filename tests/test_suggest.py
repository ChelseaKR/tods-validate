"""Concrete fix suggestions: the advisory layer over the safe ``fix`` transforms.

Each suggestion must be one the validator itself would accept, reachable from the
bad value by zero-padding or dropping date separators alone, so applying it clears
the finding without changing what the value means. These tests pin that contract.
"""

from pathlib import Path

from click.testing import CliRunner

from tods_validate.api import suggest_fixes
from tods_validate.cli import main
from tods_validate.fix import fix_package
from tods_validate.runner import run
from tods_validate.suggest import (
    AUTO,
    REVIEW,
    Suggestion,
    render_suggestions,
    suggest_for_findings,
)

_RUN_EVENTS_HEADER = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time\n"
)


def _feed(tmp_path: Path, name: str, body: str) -> Path:
    src = tmp_path / "feed"
    src.mkdir(parents=True, exist_ok=True)
    (src / name).write_text(body)
    return src


def _vehicle_feed(tmp_path: Path, vehicle_ids: str, assigned_vehicle_id: str) -> Path:
    src = tmp_path / "feed"
    src.mkdir(parents=True, exist_ok=True)
    (src / "vehicles.txt").write_text("vehicle_id\n" + vehicle_ids)
    (src / "vehicle_assignments.txt").write_text(
        f"date,service_id,block_id,vehicle_id\n20260106,weekday,B1,{assigned_vehicle_id}\n"
    )
    return src


def _suggestions(path: Path) -> list[Suggestion]:
    package, findings = run(path)
    return suggest_for_findings(findings, package)


def test_trim_is_an_auto_suggestion(tmp_path: Path) -> None:
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000 ,10,sign-in,garage,08:45:00,garage,08:50:00\n",
    )
    suggestions = _suggestions(src)
    trims = [s for s in suggestions if s.rule_id == "TODS-W206"]
    assert len(trims) == 1
    assert trims[0].kind == AUTO
    assert trims[0].current == "10000 "
    assert trims[0].proposed == "10000"


def test_bad_time_is_a_review_suggestion(tmp_path: Path) -> None:
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000,10,sign-in,garage,08:45:00,garage,9:45\n",
    )
    fixes = [s for s in _suggestions(src) if s.rule_id == "TODS-E203"]
    assert len(fixes) == 1
    assert fixes[0].kind == REVIEW
    assert fixes[0].field == "end_time"
    assert fixes[0].current == "9:45"
    assert fixes[0].proposed == "09:45:00"


def test_applying_the_time_suggestion_clears_the_error(tmp_path: Path) -> None:
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000,10,sign-in,garage,08:45:00,garage,9:45\n",
    )
    fix = next(s for s in _suggestions(src) if s.rule_id == "TODS-E203")
    assert fix.proposed is not None
    fixed_body = _RUN_EVENTS_HEADER + (
        f"weekday,10000,10,sign-in,garage,08:45:00,garage,{fix.proposed}\n"
    )
    out = _feed(tmp_path / "after", "run_events.txt", fixed_body)
    _, findings = run(out)
    assert not any(f.rule_id == "TODS-E203" for f in findings)


def test_out_of_range_time_gets_no_suggestion(tmp_path: Path) -> None:
    # 9:75 has no valid HH:MM:SS reachable by padding, so the validator must not
    # invent one; the finding stands on its own message.
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000,10,sign-in,garage,08:45:00,garage,9:75\n",
    )
    assert [s for s in _suggestions(src) if s.rule_id == "TODS-E203"] == []


_ERD_HEADER = "date,service_id,run_id,employee_id\n"


def test_iso_date_is_a_review_suggestion(tmp_path: Path) -> None:
    src = _feed(tmp_path, "employee_run_dates.txt", _ERD_HEADER + "2026-03-15,weekday,10000,E1\n")
    fixes = [s for s in _suggestions(src) if s.rule_id == "TODS-E203"]
    assert len(fixes) == 1
    assert fixes[0].kind == REVIEW
    assert fixes[0].current == "2026-03-15"
    assert fixes[0].proposed == "20260315"


def test_us_ordered_date_gets_no_suggestion(tmp_path: Path) -> None:
    # 03/15/2026 cleans to 03152026, which is not a real YYYYMMDD date, so no
    # suggestion is offered rather than a silently reordered one.
    src = _feed(tmp_path, "employee_run_dates.txt", _ERD_HEADER + "03/15/2026,weekday,10000,E1\n")
    assert [s for s in _suggestions(src) if s.rule_id == "TODS-E203"] == []


def test_duplicate_employee_row_is_an_auto_delete_suggestion(tmp_path: Path) -> None:
    row = "20260315,weekday,10000,E1\n"
    src = _feed(tmp_path, "employee_run_dates.txt", _ERD_HEADER + row + row)
    dups = [s for s in _suggestions(src) if s.rule_id == "TODS-W408"]
    assert len(dups) == 1
    assert dups[0].kind == AUTO
    assert dups[0].proposed is None  # a structural fix, not a value change
    # The auto suggestions line up with what `fix` would actually do.
    assert fix_package(src).total_duplicates_dropped == 1


def test_broken_vehicle_id_typo_is_a_review_suggestion(tmp_path: Path) -> None:
    # "bus-2" is a single substitution away from the one defined vehicle, "bus-9".
    src = _vehicle_feed(tmp_path, "bus-9\n", "bus-2")
    fixes = [s for s in _suggestions(src) if s.rule_id == "TODS-E303"]
    assert len(fixes) == 1
    assert fixes[0].kind == REVIEW
    assert fixes[0].field == "vehicle_id"
    assert fixes[0].current == "bus-2"
    assert fixes[0].proposed == "bus-9"
    assert "one character off" in fixes[0].description


def test_broken_vehicle_id_case_variant_is_a_review_suggestion(tmp_path: Path) -> None:
    src = _vehicle_feed(tmp_path, "BUS-9\n", "bus-9")
    fixes = [s for s in _suggestions(src) if s.rule_id == "TODS-E303"]
    assert len(fixes) == 1
    assert fixes[0].proposed == "BUS-9"
    assert "case" in fixes[0].description


def test_broken_vehicle_id_zero_padding_variant_is_a_review_suggestion(tmp_path: Path) -> None:
    src = _vehicle_feed(tmp_path, "bus-01\n", "bus-1")
    fixes = [s for s in _suggestions(src) if s.rule_id == "TODS-E303"]
    assert len(fixes) == 1
    assert fixes[0].proposed == "bus-01"
    assert "zero-padding" in fixes[0].description


def test_two_equally_close_vehicle_ids_gets_no_suggestion(tmp_path: Path) -> None:
    # Both "bus-1" and "bus-3" are a single substitution away from "bus-2":
    # picking either would be a guess, so no suggestion is made.
    src = _vehicle_feed(tmp_path, "bus-1\nbus-3\n", "bus-2")
    assert [s for s in _suggestions(src) if s.rule_id == "TODS-E303"] == []


def test_no_close_vehicle_id_gets_no_suggestion(tmp_path: Path) -> None:
    src = _vehicle_feed(tmp_path, "bus-9\n", "vehicle-completely-different")
    assert [s for s in _suggestions(src) if s.rule_id == "TODS-E303"] == []


def test_render_text_groups_and_counts() -> None:
    suggestions = [
        Suggestion("TODS-W206", AUTO, "Trim", "run_events.txt", 2, "run_id", "x ", "x"),
        Suggestion(
            "TODS-E203",
            REVIEW,
            "Write the time as HH:MM:SS",
            "run_events.txt",
            2,
            "end_time",
            "9:45",
            "09:45:00",
        ),
    ]
    text = render_suggestions(suggestions)
    assert "Suggestions (1 auto, 1 to review):" in text
    assert "[auto] run_events.txt, row 2, field 'run_id': Trim: 'x ' -> 'x'" in text
    assert "'9:45' -> '09:45:00'" in text
    assert "tods-validate fix PATH -o OUTPUT" in text


def test_render_markdown_has_a_section() -> None:
    suggestions = [
        Suggestion(
            "TODS-E203",
            REVIEW,
            "Write the date as YYYYMMDD",
            "employee_run_dates.txt",
            2,
            "date",
            "2026-03-15",
            "20260315",
        ),
    ]
    md = render_suggestions(suggestions, "markdown")
    assert md.startswith("## Fix suggestions")
    assert "**review**" in md
    assert "'2026-03-15' -> '20260315'" in md


def test_render_text_handles_no_suggestions() -> None:
    assert render_suggestions([]) == "No mechanical fix suggestions."


def test_render_markdown_handles_no_suggestions() -> None:
    assert render_suggestions([], "markdown").startswith("## Fix suggestions")
    assert "No mechanical fix suggestions." in render_suggestions([], "markdown")


def test_render_markdown_points_at_fix_for_auto() -> None:
    suggestions = [Suggestion("TODS-W206", AUTO, "Trim", "run_events.txt", 2, "run_id", "x ", "x")]
    md = render_suggestions(suggestions, "markdown")
    assert "1 auto, 0 to review." in md
    assert "tods-validate fix PATH -o OUTPUT" in md


def test_suggestion_to_dict_is_serializable() -> None:
    s = Suggestion(
        "TODS-E203",
        REVIEW,
        "Write the time as HH:MM:SS",
        "run_events.txt",
        2,
        "end_time",
        "9:45",
        "09:45:00",
    )
    assert s.to_dict() == {
        "rule_id": "TODS-E203",
        "kind": "review",
        "file": "run_events.txt",
        "row": 2,
        "field": "end_time",
        "current": "9:45",
        "proposed": "09:45:00",
        "description": "Write the time as HH:MM:SS",
    }


def test_api_suggest_fixes_round_trips(tmp_path: Path) -> None:
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000 ,10,sign-in,garage,08:45:00,garage,9:45\n",
    )
    kinds = {s.rule_id: s.kind for s in suggest_fixes(src)}
    assert kinds["TODS-W206"] == AUTO
    assert kinds["TODS-E203"] == REVIEW


def test_cli_suggest_prints_a_block(tmp_path: Path) -> None:
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000,10,sign-in,garage,08:45:00,garage,9:45\n",
    )
    result = CliRunner().invoke(main, ["validate", str(src), "--suggest"])
    assert "Suggestions (" in result.output
    assert "09:45:00" in result.output


def test_cli_suggest_is_silent_for_json(tmp_path: Path) -> None:
    # JSON output must stay machine-parseable; the suggestions block is never
    # appended to it (use the Python API for structured suggestions).
    src = _feed(
        tmp_path,
        "run_events.txt",
        _RUN_EVENTS_HEADER + "weekday,10000,10,sign-in,garage,08:45:00,garage,9:45\n",
    )
    result = CliRunner().invoke(main, ["validate", str(src), "--format", "json", "--suggest"])
    assert "Suggestions (" not in result.output
    import json

    json.loads(result.output)  # still valid JSON
