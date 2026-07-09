"""Workspace mode: the run-history ledger (append/load round-trip, schema
versioning, the counts-only privacy guarantee, and trend rendering)."""

from __future__ import annotations

import json
from pathlib import Path

from tods_validate.findings import Finding, Severity
from tods_validate.workspace import (
    HISTORY_SCHEMA_VERSION,
    HistoryRecord,
    append_record,
    build_record,
    load_history,
    render_trend,
)

SENSITIVE_MESSAGE = "Stop 90210 for run STOP-ID-42 is missing from the companion GTFS"


def _findings() -> list[Finding]:
    return [
        Finding(rule_id="TODS-E309", severity=Severity.ERROR, message=SENSITIVE_MESSAGE),
        Finding(rule_id="TODS-E309", severity=Severity.ERROR, message=SENSITIVE_MESSAGE + " again"),
        Finding(rule_id="TODS-W206", severity=Severity.WARNING, message="padded field"),
        Finding(rule_id="TODS-I108", severity=Severity.INFO, message="advisory note"),
    ]


def test_build_record_reuses_report_counts() -> None:
    record = build_record(_findings(), "agency-a", tool_version="9.9.9", spec_version="2.1.0")
    assert record.schema_version == HISTORY_SCHEMA_VERSION
    assert record.source == "agency-a"
    assert record.tool_version == "9.9.9"
    assert record.spec_version == "2.1.0"
    assert record.errors == 2
    assert record.warnings == 1
    assert record.infos == 1
    assert record.by_rule == {"TODS-E309": 2, "TODS-W206": 1, "TODS-I108": 1}


def test_append_and_load_round_trip(tmp_path: Path) -> None:
    history_dir = tmp_path / ".tods-history"
    record = build_record(_findings(), "agency-a", tool_version="1.0.0", spec_version="2.1.0")
    append_record(history_dir, record)

    loaded = load_history(history_dir)
    assert loaded == [record]


def test_append_creates_history_dir_if_absent(tmp_path: Path) -> None:
    history_dir = tmp_path / "nested" / ".tods-history"
    assert not history_dir.exists()
    record = build_record(_findings(), "agency-a", tool_version="1.0.0", spec_version="2.1.0")
    append_record(history_dir, record)
    assert (history_dir / "history.jsonl").is_file()


def test_append_is_append_only_one_json_object_per_line(tmp_path: Path) -> None:
    history_dir = tmp_path / ".tods-history"
    first = build_record(_findings(), "agency-a", tool_version="1.0.0", spec_version="2.1.0")
    second = build_record([], "agency-a", tool_version="1.0.0", spec_version="2.1.0")
    append_record(history_dir, first)
    append_record(history_dir, second)

    lines = (history_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line stands alone as valid JSON

    loaded = load_history(history_dir)
    assert loaded == [first, second]


def test_load_history_missing_dir_returns_empty_list(tmp_path: Path) -> None:
    assert load_history(tmp_path / "does-not-exist") == []


def test_load_history_skips_unknown_schema_version(tmp_path: Path) -> None:
    history_dir = tmp_path / ".tods-history"
    history_dir.mkdir()
    known = build_record(_findings(), "agency-a", tool_version="1.0.0", spec_version="2.1.0")
    foreign = {**known.to_dict(), "schemaVersion": "99.0.0"}
    path = history_dir / "history.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(foreign) + "\n")
        fh.write(json.dumps(known.to_dict()) + "\n")

    loaded = load_history(history_dir)
    assert loaded == [known]


def test_privacy_no_message_text_ever_written(tmp_path: Path) -> None:
    """The load-bearing privacy guarantee: only counts and rule IDs persist."""
    history_dir = tmp_path / ".tods-history"
    record = build_record(_findings(), "agency-a", tool_version="1.0.0", spec_version="2.1.0")
    append_record(history_dir, record)

    raw = (history_dir / "history.jsonl").read_text(encoding="utf-8")
    assert SENSITIVE_MESSAGE not in raw
    assert "message" not in json.loads(raw.splitlines()[0])
    assert "padded field" not in raw
    assert "advisory note" not in raw
    # Only the documented, counts-shaped keys are present.
    payload = json.loads(raw.splitlines()[0])
    assert set(payload) == {
        "schemaVersion",
        "timestamp",
        "source",
        "toolVersion",
        "specVersion",
        "errors",
        "warnings",
        "infos",
        "byRule",
    }


def test_render_trend_empty_history() -> None:
    assert render_trend([]) == "No run history yet."


def test_render_trend_groups_by_source_and_shows_regression() -> None:
    older = HistoryRecord(
        schema_version=HISTORY_SCHEMA_VERSION,
        timestamp="2026-06-01T00:00:00Z",
        source="agency-a",
        tool_version="1.0.0",
        spec_version="2.1.0",
        errors=1,
        warnings=0,
        infos=0,
        by_rule={"TODS-E309": 1},
    )
    newer = HistoryRecord(
        schema_version=HISTORY_SCHEMA_VERSION,
        timestamp="2026-07-01T00:00:00Z",
        source="agency-a",
        tool_version="1.0.0",
        spec_version="2.1.0",
        errors=3,
        warnings=0,
        infos=0,
        by_rule={"TODS-E309": 2, "TODS-W206": 1},
    )
    other_agency = HistoryRecord(
        schema_version=HISTORY_SCHEMA_VERSION,
        timestamp="2026-06-15T00:00:00Z",
        source="agency-b",
        tool_version="1.0.0",
        spec_version="2.1.0",
        errors=0,
        warnings=0,
        infos=0,
        by_rule={},
    )

    table = render_trend([newer, older, other_agency])

    assert "## agency-a" in table
    assert "## agency-b" in table
    # agency-a section lists the older run before the newer one.
    a_idx = table.index("## agency-a")
    b_idx = table.index("## agency-b")
    older_idx = table.index("2026-06-01T00:00:00Z")
    newer_idx = table.index("2026-07-01T00:00:00Z")
    assert a_idx < older_idx < newer_idx < b_idx
    # The regression (errors 1 -> 3, TODS-E309 and TODS-W206 got worse) shows.
    assert "+2" in table
    assert "TODS-E309" in table.split("## agency-a")[1].split("## agency-b")[0]
    assert "TODS-W206" in table.split("## agency-a")[1].split("## agency-b")[0]
    # No sparkline characters; text-first.
    for spark_char in "▁▂▃▄▅▆▇█":
        assert spark_char not in table
