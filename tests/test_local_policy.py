"""Local policy rules (LOCAL-P0xx, #189, ADR 0009).

The four "Done when" criteria of #189 are the first four tests. Everything
after them pins a definition, a refusal, or a surface, and each rule is tested
on both sides of its limit so that a check comparing the wrong way round, or
not at all, is a failure rather than a quiet pass.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import jsonschema
import pytest
from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate import local_policy as local_policy_module
from tods_validate.cli import main
from tods_validate.config import ConfigError, load_config
from tods_validate.findings import Finding, Severity
from tods_validate.gtfs_companion import build_companion
from tods_validate.loader import load_package
from tods_validate.local_policy import (
    AGENCY_POLICY_NOTE,
    DECISION_RECORD,
    LOCAL_NAMESPACE,
    LOCAL_RULES,
    LocalPolicy,
)
from tods_validate.rules import LOCAL_BAND, REGISTRY, RunCoverage
from tods_validate.runner import run_with_coverage
from tods_validate.stats import collect_stats
from tods_validate.suggest import suggest_for_findings

SCHEMA = json.loads((Path(__file__).parent.parent / "docs" / "report.schema.json").read_text())
EVERY_SETTING = """\
[policy]
max-run-minutes = 600
max-piece-minutes = 300
min-break-minutes = 30
max-spread-minutes = 780
max-consecutive-days-per-employee = 6
require-vehicle-assignment-for-revenue-events = true
break-event-types = ["Break"]
"""


def _policy(tmp_path: Path, body: str, name: str = "tods-validate.toml") -> LocalPolicy | None:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return load_config(path).local_policy


def _run(
    tmp_path: Path,
    body: str,
    tods: Path = VALID_TODS,
    gtfs: Path | None = VALID_GTFS,
) -> tuple[list[Finding], RunCoverage]:
    policy = _policy(tmp_path, body)
    _, findings, coverage = run_with_coverage(tods, gtfs, local_policy=policy)
    return findings, coverage


def _local(findings: list[Finding], rule_id: str | None = None) -> list[Finding]:
    return [
        f
        for f in findings
        if f.rule_id.startswith(LOCAL_NAMESPACE) and (rule_id is None or f.rule_id == rule_id)
    ]


def _outcome(coverage: RunCoverage, rule_id: str):  # type: ignore[no-untyped-def]
    (outcome,) = (o for o in coverage.local if o.id == rule_id)
    return outcome


def _package(tmp_path: Path, **files: str) -> Path:
    """The valid TODS package, copied, with ``files`` (name -> content) replaced."""
    dest = tmp_path / "tods"
    shutil.copytree(VALID_TODS, dest)
    for name, content in files.items():
        (dest / name.replace("__", ".")).write_text(content, encoding="utf-8")
    return dest


RUN_EVENTS_HEADER = (
    "service_id,run_id,event_sequence,piece_id,block_id,job_type,event_type,trip_id,"
    "start_location,start_time,start_mid_trip,end_location,end_time,end_mid_trip\n"
)


# --- #189 "Done when" ---------------------------------------------------------


def test_with_no_policy_table_there_is_no_local_band_and_nothing_reaches_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Done when 1: no [policy] table, no local band, reports unchanged.

    The strong half is the monkeypatch: with the evaluator replaced by one that
    raises, every report format still renders, so without a policy the local
    code path is never entered at all, which is what makes the reports
    byte-identical to a build without it.
    """

    def _must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("local policy was evaluated without a [policy] table")

    monkeypatch.setattr("tods_validate.runner.evaluate_local_policy", _must_not_run)
    config = tmp_path / "tods-validate.toml"
    config.write_text('fail-on = "error"\nenable = ["coverage", "advisory"]\n', encoding="utf-8")
    assert load_config(config).local_policy is None
    for fmt in ("text", "json", "markdown", "sarif", "github", "html"):
        result = CliRunner().invoke(
            main,
            ["validate", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", fmt]
            + ["--config", str(config)],
        )
        assert result.exit_code == 0, (fmt, result.output)
        assert LOCAL_NAMESPACE not in result.output, fmt
        assert "Local policy" not in result.output, fmt
        assert "localPolicy" not in result.output, fmt
    _, _, coverage = run_with_coverage(VALID_TODS, VALID_GTFS)
    assert coverage.local == ()
    assert coverage.local_lines() == []
    assert "localPolicy" not in coverage.to_dict()


def test_a_run_over_the_spread_limit_is_one_finding_quoting_the_threshold(tmp_path: Path) -> None:
    """Done when 2. Run 10000 in the valid fixture spreads 09:30 to 15:00, 330 minutes."""
    findings, _ = _run(tmp_path, "[policy]\nmax-spread-minutes = 329\n")
    (finding,) = _local(findings)
    assert finding.rule_id == "LOCAL-P004"
    assert finding.file == "run_events.txt"
    assert finding.row == 10
    assert finding.field == "end_time"
    assert "max-spread-minutes = 329" in finding.message
    assert "5h30m" in finding.message
    assert finding.message.endswith(AGENCY_POLICY_NOTE)
    assert finding.severity is Severity.WARNING
    # And at exactly the spread it is within the limit, not over it.
    at_limit, _ = _run(tmp_path, "[policy]\nmax-spread-minutes = 330\n")
    assert _local(at_limit) == []


def test_a_negative_break_minimum_is_refused_at_config_load(tmp_path: Path) -> None:
    """Done when 3, through the loader and through the command line (exit 2)."""
    body = '[policy]\nmin-break-minutes = -5\nbreak-event-types = ["Break"]\n'
    with pytest.raises(ConfigError, match=r"'min-break-minutes' must be a whole number .* -5"):
        _policy(tmp_path, body)
    result = CliRunner().invoke(
        main, ["validate", str(VALID_TODS), "--config", str(tmp_path / "tods-validate.toml")]
    )
    assert result.exit_code == 2
    assert "min-break-minutes" in result.output


def test_the_conformance_corpus_carries_no_local_rule() -> None:
    """Done when 4. The parity tests themselves are tests/test_conformance*.py."""
    assert not [p.name for p in (FIXTURES / "invalid").iterdir() if p.name.startswith("LOCAL")]
    expectations = (FIXTURES / "expectations.json").read_text(encoding="utf-8")
    assert LOCAL_NAMESPACE not in expectations
    assert not [r.id for r in REGISTRY if r.id.startswith(LOCAL_NAMESPACE)]


# --- config -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("max-spread-minutes = 0", "greater than zero, not 0"),
        ("max-spread-minutes = 7.5", "whole number of minutes"),
        ("max-spread-minutes = true", "whole number of minutes"),
        ('max-spread-minutes = "600"', "whole number of minutes"),
        ("max-consecutive-days-per-employee = -1", "whole number of days"),
        ('require-vehicle-assignment-for-revenue-events = "yes"', "true or false"),
        ("max-spread-minutes = { limit = 600, level = 'error' }", "unknown key"),
        ("max-spread-minutes = { severity = 'error' }", "with no 'limit'"),
        ("max-spread-minutes = { limit = 600, severity = 'fatal' }", "severity must be one of"),
        ("max_spread_minutes = 600", "Did you mean 'max-spread-minutes'"),
        ("max-shift-minutes = 600", "unknown setting 'max-shift-minutes'"),
        ('max-run-minutes = 600\nbreak-event-types = "Break"', "must be a list"),
        ('max-run-minutes = 600\nbreak-event-types = ["Break", " "]', "blank entry"),
        ("min-break-minutes = 30", "needs a non-empty 'break-event-types'"),
        ("min-break-minutes = 30\nbreak-event-types = []", "needs a non-empty"),
        ("max-run-minutes = 600", "needs 'break-event-types'"),
        ('max-spread-minutes = 600\nbreak-event-types = ["Break"]', "would do nothing"),
    ],
)
def test_an_unusable_policy_setting_is_refused(tmp_path: Path, body: str, match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        _policy(tmp_path, f"[policy]\n{body}\n")


def test_policy_must_be_a_table(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="'policy' must be a table"):
        _policy(tmp_path, "policy = 5\n")


def test_an_empty_policy_table_is_no_policy(tmp_path: Path) -> None:
    assert _policy(tmp_path, "[policy]\n") is None


def test_an_empty_break_vocabulary_is_a_statement_not_an_omission(tmp_path: Path) -> None:
    policy = _policy(tmp_path, "[policy]\nmax-run-minutes = 600\nbreak-event-types = []\n")
    assert policy is not None
    assert policy.break_event_types == frozenset()


def test_severity_is_set_beside_the_limit(tmp_path: Path) -> None:
    findings, coverage = _run(
        tmp_path, '[policy]\nmax-spread-minutes = { limit = 300, severity = "error" }\n'
    )
    (finding,) = _local(findings)
    assert finding.severity is Severity.ERROR
    assert _outcome(coverage, "LOCAL-P004").severity is Severity.ERROR


def test_the_severity_table_does_not_remap_a_local_rule(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"takes its severity from its own \[policy\] setting"):
        _policy(tmp_path, '[severity]\n"LOCAL-P004" = "error"\n')


def test_an_inheriting_file_may_rely_on_its_parents_break_vocabulary(tmp_path: Path) -> None:
    (tmp_path / "base.toml").write_text(
        '[policy]\nmax-run-minutes = 600\nbreak-event-types = ["Break"]\n'
        "require-vehicle-assignment-for-revenue-events = true\n",
        encoding="utf-8",
    )
    policy = _policy(
        tmp_path,
        'extends = "base.toml"\n[policy]\nmin-break-minutes = 20\n'
        "require-vehicle-assignment-for-revenue-events = false\n",
    )
    assert policy is not None
    assert [limit.setting for limit in policy.limits] == [
        "max-run-minutes = 600",
        "min-break-minutes = 20",
    ]
    assert policy.break_event_types == frozenset({"Break"})


def test_the_local_band_lists_settings_in_rule_order_whatever_the_file_order(
    tmp_path: Path,
) -> None:
    _, coverage = _run(
        tmp_path,
        '[policy]\nmax-spread-minutes = 780\nbreak-event-types = ["Break"]\n'
        "max-run-minutes = 600\n",
    )
    assert [o.id for o in coverage.local] == ["LOCAL-P001", "LOCAL-P004"]


# --- the six rules --------------------------------------------------------------


def test_max_run_leaves_out_declared_breaks_and_points_at_the_crossing_event(
    tmp_path: Path,
) -> None:
    # Run 10000 works 230 minutes outside its 70-minute Break; it passes 200
    # during event_sequence 80 (row 9), when the running total reaches 220.
    body = '[policy]\nmax-run-minutes = 200\nbreak-event-types = ["Break"]\n'
    (finding,) = _local(_run(tmp_path, body)[0], "LOCAL-P001")
    assert finding.row == 9
    assert "3h50m" in finding.message
    assert finding.data == {
        "value": "230",
        "expected": "<= 200",
        "policy": "max-run-minutes = 200",
    }
    assert _local(_run(tmp_path, body.replace("200", "230"))[0], "LOCAL-P001") == []


def test_max_run_with_an_empty_vocabulary_counts_the_break_as_work(tmp_path: Path) -> None:
    body = "[policy]\nmax-run-minutes = 299\nbreak-event-types = []\n"
    (finding,) = _local(_run(tmp_path, body)[0], "LOCAL-P001")
    assert finding.data is not None
    assert finding.data["value"] == "300"
    assert "none are declared" in finding.message


def test_max_run_counts_overlapping_events_once(tmp_path: Path) -> None:
    tods = _package(
        tmp_path,
        run_events__txt=RUN_EVENTS_HEADER
        + "daily,1,10,,,Operator,Work,,garage,08:00:00,,garage,10:00:00,\n"
        + "daily,1,20,,,Operator,Work,,garage,09:00:00,,garage,11:00:00,\n",
    )
    body = "[policy]\nmax-run-minutes = 180\nbreak-event-types = []\n"
    # Summed, the two events are 240 minutes; the time they cover is 180.
    assert _local(_run(tmp_path, body, tods=tods)[0], "LOCAL-P001") == []


def test_max_piece_is_measured_per_piece_and_a_run_with_no_piece_id_is_unmeasurable(
    tmp_path: Path,
) -> None:
    # Piece 10000-1 is 09:45-11:50 (125 min); 10000-2 is 13:00-15:00 (120 min).
    findings, coverage = _run(tmp_path, "[policy]\nmax-piece-minutes = 124\n")
    (finding,) = _local(findings, "LOCAL-P002")
    assert "'10000-1'" in finding.message
    assert finding.row == 6
    outcome = _outcome(coverage, "LOCAL-P002")
    assert outcome.measurement is not None
    assert (outcome.measurement.measured, outcome.measurement.unmeasurable) == (1, 1)
    assert "no event in the run carries a piece_id" in (outcome.measurement.reason or "")


def test_min_break_matches_the_declared_type_exactly(tmp_path: Path) -> None:
    # The fixture's one Break runs 11:50-13:00, 70 minutes.
    (finding,) = _local(
        _run(tmp_path, '[policy]\nmin-break-minutes = 71\nbreak-event-types = ["Break"]\n')[0],
        "LOCAL-P003",
    )
    assert finding.row == 7
    assert finding.data is not None
    assert finding.data["expected"] == ">= 71"
    assert (
        _local(
            _run(tmp_path, '[policy]\nmin-break-minutes = 70\nbreak-event-types = ["Break"]\n')[0]
        )
        == []
    )
    # "break" is not "Break": the vocabulary is the agency's, spelled as exported.
    lowercase = '[policy]\nmin-break-minutes = 71\nbreak-event-types = ["break"]\n'
    _, coverage = _run(tmp_path, lowercase)
    outcome = _outcome(coverage, "LOCAL-P003")
    assert outcome.measurement is not None
    assert outcome.measurement.total == 0
    reason = outcome.measurement.reason or ""
    assert "no event in run_events.txt has an event_type listed" in reason


def _employee_dates(days: list[date], employee: str = "emp-1") -> str:
    rows = "".join(f"{d:%Y%m%d},daily,10000,{employee}\n" for d in days)
    return "date,service_id,run_id,employee_id\n" + rows


def test_consecutive_days_points_at_the_first_day_over_the_limit(tmp_path: Path) -> None:
    start = date(2026, 1, 5)
    week = [start + timedelta(days=i) for i in range(7)]
    tods = _package(tmp_path, employee_run_dates__txt=_employee_dates(week))
    body = "[policy]\nmax-consecutive-days-per-employee = 6\n"
    (finding,) = _local(_run(tmp_path, body, tods=tods)[0], "LOCAL-P005")
    assert finding.file == "employee_run_dates.txt"
    assert finding.row == 8  # header, then day 1 on row 2: day 7 is row 8
    assert "7 consecutive days, 2026-01-05 to 2026-01-11" in finding.message
    no_finding, _ = _run(tmp_path, body.replace("6", "7"), tods=tods)
    assert _local(no_finding) == []


def test_a_gap_of_one_day_breaks_a_streak(tmp_path: Path) -> None:
    start = date(2026, 1, 5)
    days = [start + timedelta(days=i) for i in (0, 1, 2, 4, 5, 6)]
    tods = _package(tmp_path, employee_run_dates__txt=_employee_dates(days))
    body = "[policy]\nmax-consecutive-days-per-employee = 3\n"
    assert _local(_run(tmp_path, body, tods=tods)[0]) == []


def test_an_unreadable_date_makes_that_employee_unmeasurable_not_clean(tmp_path: Path) -> None:
    content = _employee_dates([date(2026, 1, 5)]) + "not-a-date,daily,10000,emp-1\n"
    tods = _package(tmp_path, employee_run_dates__txt=content)
    _, coverage = _run(tmp_path, "[policy]\nmax-consecutive-days-per-employee = 6\n", tods=tods)
    measurement = _outcome(coverage, "LOCAL-P005").measurement
    assert measurement is not None
    assert (measurement.measured, measurement.unmeasurable) == (0, 1)


def test_revenue_events_are_the_events_stats_counts_as_revenue(tmp_path: Path) -> None:
    _, coverage = _run(tmp_path, "[policy]\nrequire-vehicle-assignment-for-revenue-events = true\n")
    measurement = _outcome(coverage, "LOCAL-P006").measurement
    assert measurement is not None
    assert measurement.total == collect_stats(VALID_TODS, VALID_GTFS).trip_events


def test_a_block_with_unassigned_operating_days_is_one_finding_per_block_and_service(
    tmp_path: Path,
) -> None:
    findings, _ = _run(tmp_path, "[policy]\nrequire-vehicle-assignment-for-revenue-events = true\n")
    (finding,) = _local(findings, "LOCAL-P006")
    # The service is the trip's, not the run's: the supervisor's ride-check
    # under crew-weekday rides trip 101, a daily trip on BLOCK-A.
    companion = build_companion(load_package(VALID_GTFS), load_package(VALID_TODS), "gtfs")
    operating = companion.service_dates["daily"]
    assigned = {date(2026, 1, 6), date(2026, 1, 7)}
    assert finding.data is not None
    assert finding.data["value"] == str(len(operating - assigned))
    assert "block 'BLOCK-A' (service_id 'daily')" in finding.message
    assert finding.row == 4


def test_every_operating_day_assigned_is_no_finding(tmp_path: Path) -> None:
    companion = build_companion(load_package(VALID_GTFS), load_package(VALID_TODS), "gtfs")
    rows = "".join(
        f"{d:%Y%m%d},daily,BLOCK-A,bus-1\n" for d in sorted(companion.service_dates["daily"])
    )
    header = "date,service_id,block_id,vehicle_id\n"
    tods = _package(tmp_path, vehicle_assignments__txt=header + rows)
    body = "[policy]\nrequire-vehicle-assignment-for-revenue-events = true\n"
    assert _local(_run(tmp_path, body, tods=tods)[0]) == []


def test_revenue_assignment_without_a_companion_is_skipped_and_disclosed(tmp_path: Path) -> None:
    body = "[policy]\nrequire-vehicle-assignment-for-revenue-events = true\n"
    tods = tmp_path / "tods-only"
    tods.mkdir()
    for name in ("run_events.txt", "vehicle_assignments.txt", "vehicles.txt"):
        shutil.copy(VALID_TODS / name, tods / name)
    findings, coverage = _run(tmp_path, body, tods=tods, gtfs=None)
    assert _local(findings) == []
    assert _outcome(coverage, "LOCAL-P006").status == "skipped:needs_gtfs"
    assert "LOCAL-P006" in {o.id for o in coverage.unrequested_skips}
    lines = coverage.local_lines()
    assert any("not run, no companion GTFS feed was provided" in line for line in lines)


def test_a_file_not_read_in_full_makes_every_run_unmeasurable(tmp_path: Path) -> None:
    ragged = (VALID_TODS / "run_events.txt").read_text(encoding="utf-8") + "daily,9,1,extra\n"
    tods = _package(tmp_path, run_events__txt=ragged)
    findings, coverage = _run(tmp_path, "[policy]\nmax-spread-minutes = 1\n", tods=tods)
    assert _local(findings) == []
    measurement = _outcome(coverage, "LOCAL-P004").measurement
    assert measurement is not None
    assert measurement.measured == 0
    assert measurement.unmeasurable > 0
    assert "run_events.txt was not read in full" in (measurement.reason or "")


def test_an_untimed_event_makes_its_run_unmeasurable(tmp_path: Path) -> None:
    tods = _package(
        tmp_path,
        run_events__txt=RUN_EVENTS_HEADER
        + "daily,1,10,,,Operator,Work,,garage,08:00:00,,garage,23:00:00,\n"
        + "daily,1,20,,,Operator,Work,,garage,9am,,garage,23:30:00,\n",
    )
    findings, coverage = _run(tmp_path, "[policy]\nmax-spread-minutes = 60\n", tods=tods)
    assert _local(findings) == []
    measurement = _outcome(coverage, "LOCAL-P004").measurement
    assert measurement is not None
    assert (measurement.measured, measurement.unmeasurable) == (0, 1)


def test_a_package_without_the_file_says_so_rather_than_reporting_zero(tmp_path: Path) -> None:
    tods = tmp_path / "vehicles-only"
    tods.mkdir()
    shutil.copy(VALID_TODS / "vehicles.txt", tods / "vehicles.txt")
    _, coverage = _run(tmp_path, "[policy]\nmax-spread-minutes = 600\n", tods=tods, gtfs=None)
    expected = (
        "LOCAL-P004 (max-spread-minutes = 600): 0 runs measured "
        "(the package has no run_events.txt)."
    )
    assert expected in coverage.local_lines()


def test_under_the_older_spec_every_local_rule_is_skipped(tmp_path: Path) -> None:
    policy = _policy(tmp_path, EVERY_SETTING)
    _, findings, coverage = run_with_coverage(
        VALID_TODS, VALID_GTFS, local_policy=policy, spec_version="1.0.0"
    )
    assert _local(findings) == []
    assert {o.status for o in coverage.local} == {"skipped:spec_version"}


# --- what every local finding is, and is not --------------------------------------


def test_every_local_finding_says_it_is_agency_policy_and_offers_no_fix(tmp_path: Path) -> None:
    body = EVERY_SETTING.replace("600", "60").replace("300", "30").replace("780", "60")
    body = body.replace("min-break-minutes = 30", "min-break-minutes = 90")
    tods = _package(
        tmp_path,
        employee_run_dates__txt=_employee_dates(
            [date(2026, 1, 5) + timedelta(days=i) for i in range(8)]
        ),
    )
    findings, _ = _run(tmp_path, body, tods=tods)
    local = _local(findings)
    assert {f.rule_id for f in local} == {r.id for r in LOCAL_RULES}
    for finding in local:
        assert finding.message.endswith(AGENCY_POLICY_NOTE), finding.rule_id
        assert finding.suggestion is None, finding.rule_id
    assert suggest_for_findings(local, load_package(tods)) == []


def test_a_report_with_a_policy_matches_the_schema_and_keeps_the_totals_apart(
    tmp_path: Path,
) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text(EVERY_SETTING, encoding="utf-8")
    result = CliRunner().invoke(
        main,
        ["validate", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "json"]
        + ["--config", str(config)],
    )
    payload = json.loads(result.stdout)
    jsonschema.validate(payload, SCHEMA)
    assert payload["coverage"]["total"] == len(REGISTRY)
    local = payload["coverage"]["localPolicy"]
    assert local["total"] == len(LOCAL_RULES)
    assert [r["policySetting"] for r in local["rules"]][0] == "max-run-minutes = 600"


def test_the_schemas_copy_of_a_rule_outcome_matches_the_original() -> None:
    coverage = SCHEMA["properties"]["coverage"]["properties"]
    original = coverage["rules"]["items"]["properties"]
    copy = coverage["localPolicy"]["properties"]["rules"]["items"]["properties"]
    assert copy["status"]["enum"] == original["status"]["enum"]
    measurement = dict(copy["measurement"])
    measurement.pop("description")
    expected = dict(original["measurement"])
    expected.pop("description")
    assert measurement == expected


def test_the_schema_rule_id_pattern_admits_local_ids_and_nothing_near_them() -> None:
    finding = SCHEMA["properties"]["findings"]["items"]["properties"]
    pattern = re.compile(finding["rule_id"]["pattern"])
    for rule in LOCAL_RULES:
        assert pattern.search(rule.id), rule.id
    for near in ("LOCAL-E001", "LOCAL-P01", "LOCAL-PP001", "LOCAL_P001"):
        assert not pattern.search(near), near


def test_the_band_renders_in_every_report_format(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text("[policy]\nmax-spread-minutes = 780\n", encoding="utf-8")
    for fmt in ("text", "markdown", "html", "github"):
        result = CliRunner().invoke(
            main,
            ["validate", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", fmt]
            + ["--config", str(config)],
        )
        assert result.exit_code == 0, (fmt, result.output)
        assert f"{LOCAL_BAND}: 1 of 1 ran." in result.output, fmt
        assert "LOCAL-P004 (max-spread-minutes = 780): 2 runs measured." in result.output, fmt


def test_sarif_describes_a_local_rule_from_its_definition(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text("[policy]\nmax-spread-minutes = 300\n", encoding="utf-8")
    result = CliRunner().invoke(
        main,
        ["validate", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "sarif"]
        + ["--config", str(config)],
    )
    (descriptor,) = json.loads(result.stdout)["runs"][0]["tool"]["driver"]["rules"]
    assert descriptor["id"] == "LOCAL-P004"
    assert descriptor["helpUri"] == DECISION_RECORD
    assert descriptor["fullDescription"]["text"].endswith(AGENCY_POLICY_NOTE)


def test_ignoring_a_run_keeps_the_local_band() -> None:
    coverage = run_with_coverage(VALID_TODS, VALID_GTFS)[2]
    local_coverage = RunCoverage(coverage.outcomes, coverage.outcomes[:1])
    assert local_coverage.with_ignored({"TODS-W206"}).local == local_coverage.local


# --- the command line -------------------------------------------------------------


def test_explain_describes_a_local_rule_without_a_config() -> None:
    result = CliRunner().invoke(main, ["explain", "LOCAL-P001"])
    assert result.exit_code == 0, result.output
    assert "Configured by [policy] max-run-minutes." in result.output
    assert f"Not a TODS specification requirement. Decision record: {DECISION_RECORD}" in (
        result.output
    )
    assert "Spec:" not in result.output


def test_rules_lists_local_rules_only_when_a_config_sets_them(tmp_path: Path) -> None:
    bare = json.loads(CliRunner().invoke(main, ["rules", "--format", "json"]).stdout)
    assert not [r for r in bare if r["id"].startswith(LOCAL_NAMESPACE)]
    config = tmp_path / "tods-validate.toml"
    config.write_text(
        '[policy]\nmax-spread-minutes = { limit = 780, severity = "error" }\n', encoding="utf-8"
    )
    listed = json.loads(
        CliRunner().invoke(main, ["rules", "--format", "json", "--config", str(config)]).stdout
    )
    assert listed[: len(bare)] == bare
    (local,) = listed[len(bare) :]
    assert local["id"] == "LOCAL-P004"
    assert local["severity"] == "ERROR"
    assert local["category"] == "local-policy"
    assert local["policySetting"] == "max-spread-minutes = 780"
    assert local["specSection"] == DECISION_RECORD


@pytest.mark.parametrize(
    ("flag", "match"),
    [("--ignore", "cannot ignore LOCAL-P001"), ("--enable", "cannot --enable LOCAL-P001")],
)
def test_a_local_rule_is_not_switched_by_flags(flag: str, match: str) -> None:
    result = CliRunner().invoke(main, ["validate", str(VALID_TODS), flag, "LOCAL-P001"])
    assert result.exit_code == 2
    assert match in result.output
    assert "[policy]" in result.output


def test_an_error_severity_local_finding_fails_the_run(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    args = ["validate", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--config", str(config)]
    config.write_text("[policy]\nmax-spread-minutes = 300\n", encoding="utf-8")
    assert CliRunner().invoke(main, args).exit_code == 0
    config.write_text(
        '[policy]\nmax-spread-minutes = { limit = 300, severity = "error" }\n', encoding="utf-8"
    )
    assert CliRunner().invoke(main, args).exit_code == 1


def test_the_evaluator_is_the_only_way_local_rules_run() -> None:
    # A local rule handed to the registry machinery refuses to run rather than
    # reporting a clean result it never computed.
    rule = local_policy_module.as_rule(LOCAL_RULES[0])
    with pytest.raises(RuntimeError, match="evaluated by tods_validate.local_policy.evaluate"):
        rule.check(None)  # type: ignore[arg-type]
