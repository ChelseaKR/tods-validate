"""The rules subcommand and the published JSON Schema for reports."""

import json
from pathlib import Path

import jsonschema
from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main
from tods_validate.rules import all_rules

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "docs" / "report.schema.json").read_text(encoding="utf-8")
)


def _report(*args: str) -> dict:
    result = CliRunner().invoke(main, ["validate", *args, "--format", "json"])
    return json.loads(result.output)


def test_clean_report_matches_schema() -> None:
    payload = _report(str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    jsonschema.validate(payload, SCHEMA)


def test_findings_report_matches_schema() -> None:
    payload = _report(str(FIXTURES / "invalid" / "TODS-E307"))
    jsonschema.validate(payload, SCHEMA)
    assert payload["summary"]["errors"] >= 1


def test_rules_json_lists_every_rule() -> None:
    result = CliRunner().invoke(main, ["rules", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert {r["id"] for r in payload} == {r.id for r in all_rules()}
    sample = payload[0]
    assert set(sample) == {
        "id",
        "severity",
        "title",
        "description",
        "specSection",
        "needsGtfs",
        "gtfsTables",
        "category",
        "defaultEnabled",
        "interpretation",
    }
    # A consumer reading a skipped:needs_gtfs_table outcome can look up which
    # companion file was missing, so the skip reason is actionable.
    by_id = {r["id"]: r for r in payload}
    assert by_id["TODS-E307"]["gtfsTables"] == [["trips.txt"]]
    assert by_id["TODS-E308"]["gtfsTables"] == [["calendar.txt", "calendar_dates.txt"]]
    assert all(bool(r["gtfsTables"]) == r["needsGtfs"] for r in payload)


def test_rules_text_lists_every_rule() -> None:
    result = CliRunner().invoke(main, ["rules"])
    assert result.exit_code == 0
    for r in all_rules():
        assert r.id in result.output
