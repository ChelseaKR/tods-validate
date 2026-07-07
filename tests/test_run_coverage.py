"""The RunCoverage manifest: a report states its own scope.

A clean run should be able to say which rules actually ran and which were
skipped and why, so "no problems found" is qualified by what was checked.
"""

import json
from pathlib import Path

import jsonschema
from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS, run_invalid_fixture
from tods_validate.cli import main
from tods_validate.findings import Finding, Severity
from tods_validate.report import (
    REPORT_SCHEMA_VERSION,
    render_markdown,
    render_sarif,
    render_text,
)
from tods_validate.rules import (
    CATEGORIES,
    REGISTRY,
    STATUS_RAN,
    STATUS_SKIPPED_DISABLED,
    STATUS_SKIPPED_IGNORED,
    STATUS_SKIPPED_NEEDS_GTFS,
    all_rules,
)
from tods_validate.runner import run, run_with_coverage

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "docs" / "report.schema.json").read_text(encoding="utf-8")
)


def test_report_schema_version_bumped_for_coverage() -> None:
    assert REPORT_SCHEMA_VERSION == "1.2.0"


def test_every_registered_rule_gets_an_outcome() -> None:
    _, _, coverage = run_with_coverage(VALID_TODS, VALID_GTFS)
    assert len(coverage.outcomes) == len(REGISTRY)
    assert [o.id for o in coverage.outcomes] == [r.id for r in REGISTRY]


def test_gtfs_rules_disclosed_as_skipped_without_companion_feed(tmp_path: Path) -> None:
    # A TODS-only package (no companion GTFS anywhere) cannot resolve GTFS
    # references; the manifest must say those rules were skipped, not imply
    # they passed.
    (tmp_path / "run_events.txt").write_text(
        "service_id,run_id,event_sequence,event_type,start_location,start_time,"
        "end_location,end_time\nweekday,1,10,operator,S1,09:00:00,S1,10:00:00\n"
    )
    _, _, coverage = run_with_coverage(tmp_path)
    needs_gtfs = {r.id for r in all_rules() if r.needs_gtfs}
    skipped = {o.id for o in coverage.outcomes if o.status == STATUS_SKIPPED_NEEDS_GTFS}
    assert skipped == needs_gtfs
    assert "no companion GTFS feed" in (coverage.summary_line() or "")


def test_opt_in_rules_disclosed_until_enabled() -> None:
    _, _, coverage = run_with_coverage(VALID_TODS, VALID_GTFS)
    disabled = [o for o in coverage.outcomes if o.status == STATUS_SKIPPED_DISABLED]
    assert {o.id for o in disabled} == {r.id for r in all_rules() if not r.default_enabled}

    _, _, all_on = run_with_coverage(VALID_TODS, VALID_GTFS, enabled=frozenset(CATEGORIES))
    assert all(o.status == STATUS_RAN for o in all_on.outcomes)
    # Nothing was skipped, so there is nothing to disclose.
    assert all_on.summary_line() is None


def test_with_ignored_reclassifies_only_rules_that_ran() -> None:
    _, _, coverage = run_with_coverage(VALID_TODS, VALID_GTFS)
    ran_id = coverage.ran[0].id
    skipped_before = {o.id: o.status for o in coverage.skipped}

    disclosed = coverage.with_ignored({ran_id})
    by_id = {o.id: o for o in disclosed.outcomes}
    assert by_id[ran_id].status == STATUS_SKIPPED_IGNORED
    # Rules skipped for other reasons keep their original reason.
    for rule_id, status in skipped_before.items():
        assert by_id[rule_id].status == status
    # No ignores means the same manifest back.
    assert coverage.with_ignored(set()) is coverage


def test_to_dict_counts_are_consistent() -> None:
    _, _, coverage = run_with_coverage(VALID_TODS)
    payload = coverage.to_dict()
    assert payload["total"] == len(REGISTRY)
    assert payload["ran"] + payload["skipped"] == payload["total"]
    listed = [rule_id for ids in payload["skippedByReason"].values() for rule_id in ids]
    assert len(listed) == payload["skipped"]


def test_run_wrapper_keeps_two_tuple_contract() -> None:
    package, findings = run(VALID_TODS, VALID_GTFS)
    package2, findings2, coverage = run_with_coverage(VALID_TODS, VALID_GTFS)
    assert findings == findings2
    assert coverage.outcomes


def _report(*args: str) -> dict:
    result = CliRunner().invoke(main, ["validate", *args, "--format", "json"])
    return json.loads(result.output)


def test_json_report_carries_coverage_and_matches_schema() -> None:
    payload = _report(str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    jsonschema.validate(payload, SCHEMA)
    coverage = payload["coverage"]
    assert coverage["total"] == len(REGISTRY)
    assert {r["status"] for r in coverage["rules"]} <= {
        "ran",
        "skipped:needs_gtfs",
        "skipped:disabled",
        "skipped:ignored",
    }


def test_ignored_rules_are_disclosed_in_the_report() -> None:
    fixture = str(FIXTURES / "invalid" / "TODS-E307")
    payload = _report(fixture, "--ignore", "TODS-E307")
    jsonschema.validate(payload, SCHEMA)
    assert all(f["rule_id"] != "TODS-E307" for f in payload["findings"])
    assert "TODS-E307" in payload["coverage"]["skippedByReason"]["skipped:ignored"]


def test_text_report_disclosure_lines() -> None:
    _, findings, coverage = run_with_coverage(VALID_TODS)
    clean = render_text(findings, "feed/", coverage=coverage)
    assert "No problems found." in clean
    assert "Checks skipped:" in clean

    nasty = [Finding(rule_id="TODS-E307", severity=Severity.ERROR, message="m")]
    dirty = render_text(nasty, "feed/", coverage=coverage)
    assert "Checks skipped:" in dirty


def test_markdown_stamp_footer_states_coverage() -> None:
    _, findings, coverage = run_with_coverage(VALID_TODS, VALID_GTFS)
    text = render_markdown(findings, "feed/", stamp=True, coverage=coverage)
    assert "Rule-set coverage:" in text
    unstamped = render_markdown(findings, "feed/", coverage=coverage)
    assert "Rule-set coverage:" not in unstamped


def test_sarif_records_coverage_and_enriched_descriptors() -> None:
    findings = [
        Finding(
            rule_id="TODS-E307",
            severity=Severity.ERROR,
            file="run_events.txt",
            row=2,
            message="m",
            data={"value": "T9", "referenced": "trips.trip_id"},
        )
    ]
    _, _, coverage = run_with_coverage(VALID_TODS)
    sarif = json.loads(render_sarif(findings, "feed/", coverage=coverage))
    sarif_run = sarif["runs"][0]

    descriptor = sarif_run["tool"]["driver"]["rules"][0]
    registered = next(r for r in all_rules() if r.id == "TODS-E307")
    assert descriptor["shortDescription"]["text"] == registered.title
    assert descriptor["fullDescription"]["text"] == registered.description
    assert descriptor["helpUri"] == registered.spec_section

    result = sarif_run["results"][0]
    assert result["properties"]["value"] == "T9"
    assert result["properties"]["referenced"] == "trips.trip_id"

    invocation = sarif_run["invocations"][0]
    assert invocation["executionSuccessful"] is True
    assert invocation["properties"]["coverage"]["total"] == len(REGISTRY)


def test_sarif_unknown_rule_falls_back_to_bare_descriptor() -> None:
    findings = [Finding(rule_id="TODS-E999", severity=Severity.ERROR, message="m")]
    sarif = json.loads(render_sarif(findings, "feed/"))
    descriptor = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    assert descriptor["id"] == "TODS-E999"
    assert "helpUri" not in descriptor


def test_reference_findings_carry_structured_data() -> None:
    findings = run_invalid_fixture("TODS-E307")
    e307 = next(f for f in findings if f.rule_id == "TODS-E307")
    assert e307.data is not None
    assert e307.data["referenced"] == "trips.trip_id"
    assert e307.data["value"]


def test_vehicle_assignment_block_refs_disclosed_without_trips(tmp_path: Path) -> None:
    # vehicle_assignments resolves block_id into trips.txt. When the companion
    # feed has no trips.txt, that check silently no-ops, so W302 must disclose
    # the gap instead of letting the run read as fully checked.
    (tmp_path / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\n"
    )
    (tmp_path / "stops.txt").write_text("stop_id\nS1\n")
    (tmp_path / "vehicles.txt").write_text("vehicle_id\nV1\n")
    (tmp_path / "vehicle_assignments.txt").write_text(
        "date,service_id,block_id,vehicle_id\n20260601,weekday,B1,V1\n"
    )
    _, findings = run(tmp_path)
    w302 = [
        f
        for f in findings
        if f.rule_id == "TODS-W302"
        and f.file == "vehicle_assignments.txt"
        and "trips.txt" in f.message
    ]
    assert w302, "expected W302 disclosing that block_id references were unchecked"
    # calendar.txt is present, so the service_id side must not warn.
    assert not any(
        f.rule_id == "TODS-W302" and f.file == "vehicle_assignments.txt" and "calendar" in f.message
        for f in findings
    )
