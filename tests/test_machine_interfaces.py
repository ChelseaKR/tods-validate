"""The rules subcommand and the published JSON Schema for reports."""

import json
import re
from pathlib import Path

import jsonschema
import pytest
from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main
from tods_validate.rules import CATEGORIES, OPERATIONAL_NAMESPACE, all_rules

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


# The two schema tests above were, until this block, the only places a real
# report met this schema, and both ran with every opt-in category off. That is
# where new report content arrives first. OPS-W001 brought a rule ID outside
# the TODS- namespace and a per-rule `measurement` block into the JSON report;
# the schema refused both, and neither test could see it, because neither run
# enabled the rule that emits them. Every fixture now reports with every opt-in
# category on, so what an opt-in rule adds is held to the schema from the
# commit that adds it. The categories are read from the registry, not listed,
# so a category added later is enabled here without anyone remembering to.
_EVERY_OPT_IN = tuple(
    token for category in CATEGORIES if category != "core" for token in ("--enable", category)
)
_INVALID_FIXTURES = sorted(p for p in (FIXTURES / "invalid").iterdir() if p.is_dir())
_RULE_ID_PATTERN = re.compile(
    SCHEMA["properties"]["findings"]["items"]["properties"]["rule_id"]["pattern"]
)


@pytest.mark.parametrize("fixture", _INVALID_FIXTURES, ids=lambda p: p.name)
def test_every_fixture_report_matches_schema_with_every_category_enabled(fixture: Path) -> None:
    jsonschema.validate(_report(str(fixture), *_EVERY_OPT_IN), SCHEMA)


def test_every_fixture_is_examined() -> None:
    # The floor under the parametrized test: a fixture directory that moved, or
    # a glob that stopped matching, would otherwise parametrize over nothing and
    # pass. One fixture per registered rule is test_registry.py's invariant.
    assert len(_INVALID_FIXTURES) == len(tuple(all_rules()))


def test_clean_report_with_every_category_enabled_matches_schema() -> None:
    payload = _report(str(VALID_TODS), "--gtfs", str(VALID_GTFS), *_EVERY_OPT_IN)
    jsonschema.validate(payload, SCHEMA)
    # Without this the test passes just as well over a run in which no rule
    # reported a measurement, and the schema's description of one would be
    # examined by nothing.
    measured = [rule for rule in payload["coverage"]["rules"] if "measurement" in rule]
    assert measured, "no rule reported a measurement; the measurement block went unexamined"


def test_a_report_carrying_an_operational_finding_matches_schema() -> None:
    payload = _report(str(FIXTURES / "invalid" / "OPS-W001"), *_EVERY_OPT_IN)
    assert any(f["rule_id"].startswith(OPERATIONAL_NAMESPACE) for f in payload["findings"])
    jsonschema.validate(payload, SCHEMA)


def test_schema_rule_id_pattern_admits_every_registered_rule() -> None:
    refused = sorted(r.id for r in all_rules() if not _RULE_ID_PATTERN.search(r.id))
    assert not refused, f"docs/report.schema.json refuses registered rule ID(s): {refused}"


def test_schema_rule_id_pattern_still_refuses_what_is_not_a_rule_id() -> None:
    # The other side: a pattern widened to `.*` would satisfy the test above.
    for not_an_id in ("FOO-E001", "tods-e101", "TODS-X101", "OPS-W01", "TODS-E1010", ""):
        assert not _RULE_ID_PATTERN.search(not_an_id), not_an_id


def test_schema_refuses_an_unmeasurable_count_without_its_reason() -> None:
    # The schema states Measurement's own invariant: a non-zero unmeasurable
    # count carries its reason, because an undisclosed gap reads as a clean
    # result. Start from a real report whose measurement is valid, so the one
    # edit below is the only thing the schema can refuse.
    payload = _report(str(VALID_TODS), "--gtfs", str(VALID_GTFS), *_EVERY_OPT_IN)
    (measured,) = (r for r in payload["coverage"]["rules"] if "measurement" in r)
    assert measured["measurement"]["unmeasurable"] > 0
    jsonschema.validate(payload, SCHEMA)
    measured["measurement"]["reason"] = None
    with pytest.raises(jsonschema.ValidationError, match="reason|None"):
        jsonschema.validate(payload, SCHEMA)
