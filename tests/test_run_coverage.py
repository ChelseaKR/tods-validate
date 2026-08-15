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
from tods_validate.gtfs_companion import build_companion
from tods_validate.loader import load_package
from tods_validate.report import (
    REPORT_SCHEMA_VERSION,
    RULE_PAGE_BASE,
    render_markdown,
    render_sarif,
    render_text,
)
from tods_validate.rules import (
    _STATUS_REASON,
    CATEGORIES,
    REGISTRY,
    STATUS_RAN,
    STATUS_SKIPPED_DISABLED,
    STATUS_SKIPPED_IGNORED,
    STATUS_SKIPPED_NEEDS_GTFS,
    STATUS_SKIPPED_NEEDS_GTFS_TABLE,
    STATUS_SKIPPED_SPEC_VERSION,
    all_rules,
    missing_gtfs_tables,
)
from tods_validate.runner import run, run_with_coverage
from tods_validate.schema import GTFS_PRIMARY_KEYS

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "docs" / "report.schema.json").read_text(encoding="utf-8")
)
SCHEMA_STATUSES = set(
    SCHEMA["properties"]["coverage"]["properties"]["rules"]["items"]["properties"]["status"]["enum"]
)
NEEDS_GTFS = {r.id for r in all_rules() if r.needs_gtfs}


def _copy_valid_tods(destination: Path) -> Path:
    """The valid TODS package, copied so a test can add a file beside it."""
    for source in VALID_TODS.iterdir():
        (destination / source.name).write_bytes(source.read_bytes())
    return destination


def test_report_schema_version_bumped_for_coverage() -> None:
    assert REPORT_SCHEMA_VERSION == "1.3.0"


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
    assert {r["status"] for r in coverage["rules"]} <= SCHEMA_STATUSES


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
    assert descriptor["helpUri"] == f"{RULE_PAGE_BASE}{registered.id}.html"
    assert descriptor["properties"]["specSection"] == registered.spec_section

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


def test_a_stray_gtfs_file_is_not_a_companion_feed(tmp_path: Path) -> None:
    # One stray agency.txt used to promote the package to its own companion
    # feed, so all 16 GTFS reference rules ran against a "feed" with no trips,
    # stops or calendars: 28 invented errors, and a manifest claiming 39 of 42
    # rules had run. agency.txt holds nothing a TODS ID resolves against, so
    # the package is not a companion and those rules must stay skipped.
    package = _copy_valid_tods(tmp_path)
    (package / "agency.txt").write_text(
        "agency_name,agency_url,agency_timezone\nA,https://a.example,Etc/UTC\n"
    )
    _, findings, coverage = run_with_coverage(package)
    assert findings == []
    skipped = {o.id for o in coverage.outcomes if o.status == STATUS_SKIPPED_NEEDS_GTFS}
    assert skipped == NEEDS_GTFS
    # Identical to the same package without the stray file, in both directions.
    _, _, without = run_with_coverage(VALID_TODS)
    assert coverage.to_dict() == without.to_dict()


def test_package_with_no_tods_files_does_not_report_reference_checks_as_run() -> None:
    # tests/fixtures/invalid/TODS-W101 is a single agency.txt and zero TODS
    # files. It used to report 39 of 42 rules as having run while simultaneously
    # finding "no TODS files were found in this package".
    _, findings, coverage = run_with_coverage(FIXTURES / "invalid" / "TODS-W101")
    assert "TODS-W101" in {f.rule_id for f in findings}
    ran = {o.id for o in coverage.ran}
    assert not (ran & NEEDS_GTFS), "GTFS reference rules cannot have run: there is no GTFS feed"


def test_rules_whose_gtfs_table_is_absent_are_skipped_not_run(tmp_path: Path) -> None:
    # A partial companion: stops.txt is there, so stop references are genuinely
    # checkable, but nothing resolves a trip_id or a service_id. Rules that read
    # the missing tables get their own skip reason rather than reporting a pass.
    package = _copy_valid_tods(tmp_path)
    (package / "stops.txt").write_text("stop_id\nS1\n")
    _, _, coverage = run_with_coverage(package, enabled=frozenset(CATEGORIES))
    by_id = {o.id: o.status for o in coverage.outcomes}
    assert by_id["TODS-E309"] == STATUS_RAN  # stops.txt is present
    for rule_id in ("TODS-E307", "TODS-E310", "TODS-E311", "TODS-I501"):  # need trips.txt
        assert by_id[rule_id] == STATUS_SKIPPED_NEEDS_GTFS_TABLE
    for rule_id in ("TODS-E308", "TODS-E312", "TODS-W406"):  # need the calendars
        assert by_id[rule_id] == STATUS_SKIPPED_NEEDS_GTFS_TABLE
    # The reason is distinct from "no companion feed at all", which is a
    # different problem with a different fix.
    assert STATUS_SKIPPED_NEEDS_GTFS not in by_id.values()
    assert "none of the files the check reads" in (coverage.summary_line() or "")
    # Which file was missing is answerable, not just that something was.
    companion = build_companion(load_package(package), load_package(package), source="package")
    by_rule = {r.id: r for r in all_rules()}
    assert missing_gtfs_tables(by_rule["TODS-E307"], companion) == ("trips.txt",)
    assert missing_gtfs_tables(by_rule["TODS-E308"], companion) == (
        "calendar.txt or calendar_dates.txt",
    )
    assert missing_gtfs_tables(by_rule["TODS-E309"], companion) == ()


def test_a_supplement_alone_does_not_make_a_gtfs_table_checkable(tmp_path: Path) -> None:
    # trips_supplement.txt modifies trips.txt; it is not trips.txt. With no base
    # table the supplemented view holds only the supplement's own rows, so every
    # real trip_id would read as missing. The valid package supplements trips,
    # stops, routes and both calendars, and still has nothing to resolve against.
    package = _copy_valid_tods(tmp_path)
    (package / "routes.txt").write_text("route_id\nR1\n")
    _, _, coverage = run_with_coverage(package, enabled=frozenset(CATEGORIES))
    by_id = {o.id: o.status for o in coverage.outcomes}
    assert by_id["TODS-E307"] == STATUS_SKIPPED_NEEDS_GTFS_TABLE
    assert by_id["TODS-E309"] == STATUS_SKIPPED_NEEDS_GTFS_TABLE


def test_every_needs_gtfs_rule_declares_the_files_it_reads() -> None:
    # The skip is only as honest as the declaration. A needs_gtfs rule with no
    # gtfs_tables would silently go back to being reported as run against a
    # companion that cannot answer it; rule() rejects that, and this pins it.
    for r in all_rules():
        assert bool(r.gtfs_tables) == r.needs_gtfs, r.id
        for group in r.gtfs_tables:
            assert group, r.id
            assert set(group) <= set(GTFS_PRIMARY_KEYS), r.id


def test_no_skipped_rule_is_ever_counted_as_run(tmp_path: Path) -> None:
    # The manifest's whole job is that "ran" means ran. Across every shape of
    # run: the counts add up, no skipped rule appears in ran, and every skipped
    # rule is disclosed under exactly one reason with human-readable text.
    stray = _copy_valid_tods(tmp_path)
    (stray / "agency.txt").write_text("agency_name\nA\n")
    runs = [
        run_with_coverage(VALID_TODS, VALID_GTFS)[2],
        run_with_coverage(VALID_TODS)[2],
        run_with_coverage(stray)[2],
        run_with_coverage(VALID_TODS, VALID_GTFS, enabled=frozenset(CATEGORIES))[2],
        run_with_coverage(FIXTURES / "spec_v1" / "valid", spec_version="1.0.0")[2],
    ]
    for coverage in runs:
        payload = coverage.to_dict()
        assert payload["ran"] + payload["skipped"] == payload["total"] == len(REGISTRY)
        assert {o.id for o in coverage.ran}.isdisjoint({o.id for o in coverage.skipped})
        grouped = coverage.skipped_by_reason()
        disclosed = [o.id for members in grouped.values() for o in members]
        assert sorted(disclosed) == sorted(o.id for o in coverage.skipped)
        assert len(disclosed) == len(set(disclosed))
        for outcome in coverage.skipped:
            assert outcome.reason, outcome.id
            assert not outcome.ran


def test_report_schema_documents_every_status_the_validator_emits() -> None:
    # A status missing from the schema means a real report fails its own
    # published contract. skipped:spec_version was missing until 0.9.0.
    assert {STATUS_RAN, *_STATUS_REASON} == SCHEMA_STATUSES


def test_spec_version_skips_validate_against_the_published_schema() -> None:
    payload = _report(str(FIXTURES / "spec_v1" / "valid"), "--spec-version", "1.0.0")
    jsonschema.validate(payload, SCHEMA)
    statuses = {r["status"] for r in payload["coverage"]["rules"]}
    assert STATUS_SKIPPED_SPEC_VERSION in statuses
    assert statuses <= SCHEMA_STATUSES


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
