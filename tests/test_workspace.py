"""Workspace mode: the run-history ledger (append/load round-trip, schema
versioning, the counts-only privacy guarantee, and trend rendering)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from conftest import VALID_TODS
from tods_validate.cli import main
from tods_validate.findings import Finding, Severity
from tods_validate.runner import run_with_coverage
from tods_validate.workspace import (
    HISTORY_SCHEMA_VERSION,
    CoverageRecord,
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


# ---------------------------------------------------------------------------
# Coverage in the ledger (#186)
#
# A rule that did not run contributes nothing to `byRule`, which is
# indistinguishable from a rule that ran and found nothing. Without coverage
# in the record, a check being switched off read as a fix: errors 1 -> 0,
# "Δ errors -1", no new/worse rules, in a run where the rule that found the
# error never executed and the bad trip_id was still bad.
# ---------------------------------------------------------------------------


def _coverage(ran: tuple[str, ...], skipped: dict[str, tuple[str, ...]]) -> CoverageRecord:
    return CoverageRecord(ran=ran, skipped_by_reason=skipped)


def _record(
    timestamp: str,
    *,
    errors: int,
    by_rule: dict[str, int],
    coverage: CoverageRecord | None,
    source: str = "agency-a",
) -> HistoryRecord:
    return HistoryRecord(
        schema_version=HISTORY_SCHEMA_VERSION,
        timestamp=timestamp,
        source=source,
        tool_version="1.0.0",
        spec_version="2.1.0",
        errors=errors,
        warnings=0,
        infos=0,
        by_rule=by_rule,
        coverage=coverage,
    )


def test_build_record_carries_the_runs_coverage(tmp_path: Path) -> None:
    _, findings, coverage = run_with_coverage(VALID_TODS)
    record = build_record(
        findings, "agency-a", tool_version="1.0.0", spec_version="2.1.0", coverage=coverage
    )
    assert record.coverage is not None
    assert record.coverage.total == len(coverage.outcomes)
    assert len(record.coverage.ran) == len(coverage.ran)
    # The GTFS reference rules could not run on a TODS-only package, and the
    # record says so by name rather than by silence.
    assert "TODS-E307" in record.coverage.skipped
    assert not record.coverage.ran_rule("TODS-E307")

    append_record(tmp_path, record)
    assert load_history(tmp_path) == [record]


def test_batch_history_record_matches_the_row_it_was_written_beside(tmp_path: Path) -> None:
    # cli.batch holds the coverage that produced the row's checksNotRun and
    # used to write the ledger record from counts alone in the same loop
    # iteration.
    history = tmp_path / ".tods-history"
    result = CliRunner().invoke(
        main, ["batch", "--format", "json", str(VALID_TODS), "--history", str(history)]
    )
    assert result.exit_code == 0, result.output
    feed = json.loads(result.output)["feeds"][0]

    (record,) = load_history(history)
    assert record.coverage is not None
    assert record.coverage.total == feed["coverage"]["total"]
    assert len(record.coverage.ran) == feed["coverage"]["ran"]
    assert len(record.coverage.skipped) == feed["checksNotRun"]


def test_trend_does_not_report_a_rule_that_stopped_running_as_an_improvement() -> None:
    # #186's repro: TODS-E307 finds an error, then the companion GTFS feed is
    # removed and the same command runs again. Nothing was fixed.
    before = _record(
        "2026-06-01T00:00:00Z",
        errors=1,
        by_rule={"TODS-E307": 1},
        coverage=_coverage(ran=("TODS-E101", "TODS-E307"), skipped={}),
    )
    after = _record(
        "2026-06-02T00:00:00Z",
        errors=0,
        by_rule={},
        coverage=_coverage(ran=("TODS-E101",), skipped={"skipped:needs_gtfs": ("TODS-E307",)}),
    )

    table = render_trend([before, after])
    row = next(line for line in table.splitlines() if "2026-06-02" in line)
    assert "-1" not in row  # the improvement it cannot support
    assert "?" in row
    assert "TODS-E307" in row  # named, not merely withheld
    assert "2/2" in table  # each run states its own scope
    assert "1/2" in table


def test_trend_still_reports_a_real_fix_as_an_improvement() -> None:
    # The negative case matters as much: when the rule did run and found
    # nothing, -1 is exactly right and must not be hidden behind "?".
    before = _record(
        "2026-06-01T00:00:00Z",
        errors=1,
        by_rule={"TODS-E307": 1},
        coverage=_coverage(ran=("TODS-E101", "TODS-E307"), skipped={}),
    )
    after = _record(
        "2026-06-02T00:00:00Z",
        errors=0,
        by_rule={},
        coverage=_coverage(ran=("TODS-E101", "TODS-E307"), skipped={}),
    )

    row = next(line for line in render_trend([before, after]).splitlines() if "2026-06-02" in line)
    assert "-1" in row
    assert "?" not in row


def test_trend_reports_a_rise_even_when_the_scope_shrank() -> None:
    # More errors is more errors, whatever happened to coverage; suppressing a
    # regression would be the same defect pointed the other way.
    before = _record(
        "2026-06-01T00:00:00Z",
        errors=1,
        by_rule={"TODS-E307": 1},
        coverage=_coverage(ran=("TODS-E101", "TODS-E307"), skipped={}),
    )
    after = _record(
        "2026-06-02T00:00:00Z",
        errors=3,
        by_rule={"TODS-E101": 3},
        coverage=_coverage(ran=("TODS-E101",), skipped={"skipped:needs_gtfs": ("TODS-E307",)}),
    )

    row = next(line for line in render_trend([before, after]).splitlines() if "2026-06-02" in line)
    assert "+2" in row
    assert "TODS-E307" in row


def test_trend_renders_a_record_without_coverage_as_unknown_not_as_an_improvement() -> None:
    # A ledger written before the coverage field simply does not record what
    # ran. That is not the same fact as "everything ran".
    before = _record("2026-06-01T00:00:00Z", errors=2, by_rule={"TODS-E307": 2}, coverage=None)
    after = _record("2026-06-02T00:00:00Z", errors=0, by_rule={}, coverage=None)

    table = render_trend([before, after])
    row = next(line for line in table.splitlines() if "2026-06-02" in line)
    assert "-2" not in row
    assert "?" in row
    assert "recorded no coverage" in row


def test_load_history_reads_a_record_written_before_the_coverage_field(tmp_path: Path) -> None:
    # The additive-schema promise, which the old exact-equality version check
    # did not actually keep: bumping the minor version would have silently
    # dropped every existing record.
    history_dir = tmp_path / ".tods-history"
    history_dir.mkdir()
    legacy = {
        "schemaVersion": "1.0.0",
        "timestamp": "2026-06-01T00:00:00Z",
        "source": "agency-a",
        "toolVersion": "0.5.0",
        "specVersion": "2.1.0",
        "errors": 2,
        "warnings": 0,
        "infos": 0,
        "byRule": {"TODS-E307": 2},
    }
    (history_dir / "history.jsonl").write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    (record,) = load_history(history_dir)
    assert record.schema_version == "1.0.0"
    assert record.errors == 2
    assert record.coverage is None


def test_privacy_coverage_stores_rule_ids_only(tmp_path: Path) -> None:
    """Coverage is rule IDs, which the record is already permitted to store."""
    _, findings, coverage = run_with_coverage(VALID_TODS)
    record = build_record(
        findings, "agency-a", tool_version="1.0.0", spec_version="2.1.0", coverage=coverage
    )
    append_record(tmp_path, record)
    raw = (tmp_path / "history.jsonl").read_text(encoding="utf-8")
    assert "message" not in json.loads(raw)
    payload = json.loads(raw)
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
        "coverage",
    }
    assert set(payload["coverage"]) == {"ran", "skippedByReason"}
    ids = list(payload["coverage"]["ran"]) + [
        rid for group in payload["coverage"]["skippedByReason"].values() for rid in group
    ]
    assert ids
    assert all(rid.startswith("TODS-") for rid in ids)
