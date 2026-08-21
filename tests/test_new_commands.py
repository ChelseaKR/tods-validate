"""New CLI surfaces: stats, anonymize, diff, batch, baseline, formats, flags."""

import json
from pathlib import Path

from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main

E201 = str(FIXTURES / "invalid" / "TODS-E201")


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


def test_sarif_format_is_valid_json_with_runs() -> None:
    result = invoke(E201, "--format", "sarif")
    payload = json.loads(result.output)
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["tool"]["driver"]["name"] == "tods-validate"
    assert payload["runs"][0]["results"][0]["ruleId"].startswith("TODS-")


def test_html_format_is_self_contained() -> None:
    result = invoke(E201, "--format", "html")
    assert result.output.lstrip().startswith("<!doctype html>")
    assert "TODS-E201" in result.output
    assert "http://" not in result.output  # no external assets


def test_json_carries_report_metadata_and_location() -> None:
    result = invoke(E201, "--format", "json")
    payload = json.loads(result.output)
    assert payload["reportVersion"]
    assert payload["toolVersion"]
    assert payload["summary"]["byRule"]["TODS-E201"] >= 1
    assert payload["findings"][0]["location"].startswith("run_events.txt#L")


def test_max_findings_caps_output_but_not_summary() -> None:
    result = invoke(E201, "--max-findings", "0")
    assert "more finding(s) not shown" in result.output
    assert "Summary:" in result.output


def test_quiet_suppresses_individual_findings() -> None:
    result = invoke(E201, "--quiet")
    assert "Summary:" in result.output
    assert "is required but empty" not in result.output


def test_spec_version_unsupported_is_exit_two() -> None:
    result = invoke(E201, "--spec-version", "9.9.9")
    assert result.exit_code == 2
    assert "unsupported --spec-version" in result.output


def test_enable_unknown_token_is_error() -> None:
    result = invoke(E201, "--enable", "nonsense")
    assert result.exit_code == 2
    assert "unknown --enable token" in result.output


def test_profile_strict_fails_on_warning() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), "--profile", "strict")
    assert result.exit_code == 1


def test_profile_ingest_ready_is_available_and_fails_on_warning() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), "--profile", "ingest-ready")
    assert result.exit_code == 1
    assert "TODS-W101" in result.output


def test_baseline_suppresses_known_findings(tmp_path: Path) -> None:
    baseline = tmp_path / "base.json"
    baseline.write_text(invoke(E201, "--format", "json").output, encoding="utf-8")
    result = invoke(E201, "--baseline", str(baseline))
    assert result.exit_code == 0  # nothing new since the baseline


def test_diff_reports_introduced_and_exit_code() -> None:
    result = invoke("diff", str(VALID_TODS), E201)
    assert "introduced: 1" in result.output
    assert result.exit_code == 1


def test_batch_rolls_up_and_fails_on_any_error() -> None:
    result = invoke("batch", E201, str(FIXTURES / "invalid" / "TODS-W101"))
    assert result.exit_code == 1
    assert E201 in result.output


def test_batch_json() -> None:
    result = invoke("batch", "--format", "json", E201)
    payload = json.loads(result.output)
    assert payload["feeds"][0]["errors"] >= 1


def test_batch_json_carries_coverage_per_feed() -> None:
    # #127: batch used the two-tuple run() wrapper, so its JSON carried no
    # coverage manifest at all -- a TODS-only feed's `status: pass` and
    # `0 error(s)` could not be told apart from a fully-checked feed.
    result = invoke("batch", "--format", "json", str(FIXTURES / "invalid" / "TODS-W101"))
    feed = json.loads(result.output)["feeds"][0]
    assert feed["status"] == "pass"
    assert feed["checksNotRun"] > 0  # the GTFS reference rules could not run
    assert feed["coverage"]["skipped"] == feed["checksNotRun"]
    assert feed["coverage"]["total"] == feed["coverage"]["ran"] + feed["coverage"]["skipped"]


def test_batch_markdown() -> None:
    result = invoke("batch", "--format", "markdown", E201, str(FIXTURES / "invalid" / "TODS-W101"))
    assert "# TODS fleet compliance report" in result.output
    assert "| source | errors | warnings | infos | checks not run | status |" in result.output
    assert "| fail |" in result.output
    assert "| pass |" in result.output
    assert result.exit_code == 1


def test_batch_markdown_discloses_fleet_wide_coverage() -> None:
    # A TODS-only feed's row must carry its skip count beside "pass", and the
    # roll-up must state the fleet's aggregate scope -- the same disclosure
    # every single-feed format already carries (#127).
    result = invoke("batch", "--format", "markdown", str(FIXTURES / "invalid" / "TODS-W101"))
    assert "Rule-set coverage:" in result.output
    lines = [line for line in result.output.splitlines() if line.startswith("| `")]
    assert len(lines) == 1
    # "| `source` | errors | warnings | infos | checks not run | status |"
    cells = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    assert cells[-1] == "pass"
    assert int(cells[-2]) > 0  # checks not run, right beside "pass"


def test_batch_text_discloses_fleet_wide_coverage() -> None:
    result = invoke("batch", str(FIXTURES / "invalid" / "TODS-W101"))
    assert "not run" in result.output
    assert "Rule-set coverage:" in result.output
    data_line = next(line for line in result.output.splitlines() if "TODS-W101" in line)
    assert int(data_line.split()[3]) > 0  # errors warnings infos "not run" source


def test_batch_require_complete_run_fails_a_partial_feed() -> None:
    # The GTFS reference rules are unrequested skips on this TODS-only feed
    # (no --gtfs, no --ignore, no opt-out asked for), so --require-complete-run
    # must fail it even though it has zero findings of its own.
    without = invoke("batch", "--format", "json", str(FIXTURES / "invalid" / "TODS-W101"))
    assert without.exit_code == 0  # a skip alone does not fail a feed by default
    assert json.loads(without.output)["feeds"][0]["status"] == "pass"
    with_flag = invoke(
        "batch",
        "--format",
        "json",
        "--require-complete-run",
        str(FIXTURES / "invalid" / "TODS-W101"),
    )
    assert with_flag.exit_code == 1
    assert json.loads(with_flag.output)["feeds"][0]["status"] == "fail"


def test_batch_markdown_stamp() -> None:
    unstamped = invoke("batch", "--format", "markdown", E201)
    assert "Generated by tods-validate" not in unstamped.output

    stamped = invoke("batch", "--format", "markdown", "--stamp", E201)
    assert "Generated by tods-validate" in stamped.output


def test_stats_text_and_json() -> None:
    text = invoke("stats", str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    assert "Run events" in text.output
    js = invoke("stats", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "json")
    payload = json.loads(js.output)
    assert payload["run_events"] == 11
    assert payload["trip_coverage_pct"] == 100.0
    # Operational profile additions.
    assert payload["files_present"]  # which files shipped
    assert len(payload["service_date_range"]) == 2  # [min, max] dated assignment


def test_stats_markdown_profile() -> None:
    md = invoke("stats", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "markdown")
    assert "# TODS feed profile:" in md.output
    assert "| Metric | Value |" in md.output
    assert "Date range" in md.output
    assert "Files present" in md.output


def test_stats_single_path_output_is_unchanged() -> None:
    """Passing exactly one PATH keeps the original single-feed profile shape."""
    solo = invoke("stats", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "json")
    payload = json.loads(solo.output)
    assert "feeds" not in payload  # not the comparison shape
    assert "aggregate" not in payload
    assert payload["source"] == str(VALID_TODS)
    assert payload["run_events"] == 11


def test_stats_comparison_text_has_per_feed_columns_and_aggregate() -> None:
    result = invoke("stats", str(VALID_TODS), E201, "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0
    assert str(VALID_TODS) in result.output
    assert E201 in result.output
    assert "Aggregate" in result.output
    assert "Run events" in result.output


def test_stats_comparison_markdown_has_aggregate_table() -> None:
    result = invoke(
        "stats", str(VALID_TODS), E201, "--gtfs", str(VALID_GTFS), "--format", "markdown"
    )
    assert "# TODS feed comparison: 2 feed(s)" in result.output
    assert "| Metric |" in result.output
    assert "## Aggregate" in result.output
    assert "| Total | Mean | Min | Max |" in result.output


def test_stats_comparison_json_has_feeds_and_aggregate() -> None:
    result = invoke("stats", str(VALID_TODS), E201, "--gtfs", str(VALID_GTFS), "--format", "json")
    payload = json.loads(result.output)
    assert len(payload["feeds"]) == 2
    assert payload["feeds"][0]["source"] == str(VALID_TODS)
    aggregate = payload["aggregate"]
    assert aggregate["feed_count"] == 2
    assert aggregate["error_count"] == 0
    run_events = aggregate["metrics"]["run_events"]
    assert run_events["total"] == 11 + 1  # VALID_TODS has 11, TODS-E201 has 1
    assert run_events["min"] == 1
    assert run_events["max"] == 11


def test_stats_comparison_missing_feed_reported_without_crashing() -> None:
    missing = str(FIXTURES / "does-not-exist")
    result = invoke("stats", str(VALID_TODS), missing, "--format", "json")
    assert result.exit_code == 0  # stats is descriptive; benign exit
    payload = json.loads(result.output)
    assert len(payload["feeds"]) == 2
    broken = next(f for f in payload["feeds"] if f["source"] == missing)
    assert broken["error"] is not None
    ok_feed = next(f for f in payload["feeds"] if f["source"] == str(VALID_TODS))
    assert ok_feed["error"] is None
    # The unreadable feed is excluded from the aggregate numbers, not zeroed in.
    assert payload["aggregate"]["feed_count"] == 1
    assert payload["aggregate"]["error_count"] == 1
    assert payload["aggregate"]["metrics"]["run_events"]["total"] == 11

    text_result = invoke("stats", str(VALID_TODS), missing)
    assert text_result.exit_code == 0
    assert "error" in text_result.output.lower()


def test_anonymize_pseudonymizes_consistently(tmp_path: Path) -> None:
    out = tmp_path / "anon"
    result = invoke("anonymize", str(VALID_TODS), "-o", str(out), "--salt", "fixed")
    assert result.exit_code == 0
    erd = (out / "employee_run_dates.txt").read_text(encoding="utf-8")
    assert "emp_" in erd
    # The same employee maps to the same pseudonym throughout the file.
    veh = (out / "vehicles.txt").read_text(encoding="utf-8")
    va = (out / "vehicle_assignments.txt").read_text(encoding="utf-8")
    veh_ids = {line.split(",")[0] for line in veh.splitlines()[1:]}
    va_ids = {line.split(",")[3] for line in va.splitlines()[1:]}
    assert va_ids <= veh_ids  # vehicle_id references still resolve


def test_anonymize_pseudonymizes_vehicle_label(tmp_path: Path) -> None:
    out = tmp_path / "anon"
    result = invoke("anonymize", str(VALID_TODS), "-o", str(out), "--salt", "fixed")
    assert result.exit_code == 0
    veh = (out / "vehicles.txt").read_text(encoding="utf-8")
    assert "vlbl_" in veh
    assert "Old Reliable" not in veh
    assert "Buster" not in veh
    assert "vehicles.txt:vehicle_label" in result.output


def test_anonymize_also_pseudonymizes_extension_field(tmp_path: Path) -> None:
    out = tmp_path / "anon"
    result = invoke(
        "anonymize",
        str(VALID_TODS),
        "-o",
        str(out),
        "--salt",
        "fixed",
        "--also",
        "run_events.txt:job_type",
    )
    assert result.exit_code == 0
    run_events = (out / "run_events.txt").read_text(encoding="utf-8")
    header, *rows = run_events.splitlines()
    job_type_col = header.split(",").index("job_type")
    job_types = {row.split(",")[job_type_col] for row in rows if row}
    assert job_types
    assert all(v.startswith("job_type_") for v in job_types)
    assert "run_events.txt:job_type: " in result.output  # replacement count line
    # A pseudonymized column is no longer reported as carried through.
    carried_through = result.output.split("Carried through unprotected", 1)[1]
    assert "run_events.txt:job_type" not in carried_through


def test_anonymize_rejects_malformed_also(tmp_path: Path) -> None:
    out = tmp_path / "anon"
    result = invoke("anonymize", str(VALID_TODS), "-o", str(out), "--also", "not-a-pair")
    assert result.exit_code == 2
    assert "invalid --also value" in result.output


def test_anonymize_also_rejects_default_protected_field(tmp_path: Path) -> None:
    # --also must not be able to silently overwrite (and de-correlate or
    # weaken) a field already protected by default, e.g. vehicle_id, whose
    # pseudonym prefix must match across vehicles.txt and
    # vehicle_assignments.txt for the assignment to still resolve.
    out = tmp_path / "anon"
    result = invoke(
        "anonymize",
        str(VALID_TODS),
        "-o",
        str(out),
        "--salt",
        "fixed",
        "--also",
        "vehicles.txt:vehicle_label",
    )
    assert result.exit_code == 2
    assert "already pseudonymized by default" in result.output
    assert not out.exists()


def test_anonymize_carried_through_reports_numeric_identifier(tmp_path: Path) -> None:
    # A numeric-looking extension identifier (a badge number) is exactly the
    # kind of re-identifying data the disclosure table exists for, and must
    # not be excluded just because it looks like a number.
    feed_dir = tmp_path / "feed"
    feed_dir.mkdir()
    (feed_dir / "vehicles.txt").write_text(
        "vehicle_id,badge_number\nbus-1,48213\n",
        encoding="utf-8",
    )
    out = tmp_path / "anon"
    result = invoke("anonymize", str(feed_dir), "-o", str(out), "--salt", "fixed")
    assert result.exit_code == 0
    carried_through = result.output.split("Carried through unprotected", 1)[1]
    assert "vehicles.txt:badge_number" in carried_through


def test_anonymize_carried_through_table_always_shown(tmp_path: Path) -> None:
    out = tmp_path / "anon"
    result = invoke("anonymize", str(VALID_TODS), "-o", str(out), "--salt", "fixed")
    assert result.exit_code == 0
    assert "Carried through unprotected" in result.output
    # run_events.txt job_type is free text and not in the default map.
    assert "run_events.txt:job_type" in result.output


def test_anonymize_carried_through_empty_prints_none(tmp_path: Path) -> None:
    # A package whose only free-text columns are all in the default map (or
    # covered by --also) should print the header with an explicit "(none)"
    # rather than an empty/absent table.
    feed_dir = tmp_path / "feed"
    feed_dir.mkdir()
    (feed_dir / "vehicles.txt").write_text(
        "vehicle_id,vehicle_label,license_plate\nbus-1,Old Reliable,OR-E285104\n",
        encoding="utf-8",
    )
    out = tmp_path / "anon"
    result = invoke("anonymize", str(feed_dir), "-o", str(out), "--salt", "fixed")
    assert result.exit_code == 0
    assert "Carried through unprotected" in result.output
    assert "(none)" in result.output


def test_merge_writes_manifest(tmp_path: Path) -> None:
    out = tmp_path / "merged"
    result = invoke("merge", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "-o", str(out))
    assert result.exit_code == 0
    manifest = json.loads((out / "merge-report.json").read_text(encoding="utf-8"))
    assert manifest["validator"] == "tods-validate"
    assert "trips.txt" in manifest["files"]


def test_github_outputs_written(tmp_path: Path, monkeypatch) -> None:
    output_file = tmp_path / "gh_output"
    output_file.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    invoke(E201, "--format", "github")
    written = output_file.read_text(encoding="utf-8")
    assert "error-count=1" in written


def _copy_gtfs_with_trip_renamed(tmp_path: Path, old_id: str, new_id: str) -> tuple[Path, Path]:
    """Copy VALID_GTFS into old/new dirs, renaming one trip_id in the new copy."""
    import shutil

    old_dir, new_dir = tmp_path / "old_gtfs", tmp_path / "new_gtfs"
    shutil.copytree(VALID_GTFS, old_dir)
    shutil.copytree(VALID_GTFS, new_dir)
    for name in ("trips.txt", "stop_times.txt"):
        path = new_dir / name
        path.write_text(path.read_text(encoding="utf-8").replace(old_id, new_id), encoding="utf-8")
    return old_dir, new_dir


def test_drift_reports_broken_trip_id_and_fails(tmp_path: Path) -> None:
    old_dir, new_dir = _copy_gtfs_with_trip_renamed(tmp_path, "103", "103A")
    result = invoke("drift", str(old_dir), str(new_dir), "--tods", str(VALID_TODS))
    assert result.exit_code == 1
    assert "103" in result.output
    assert "103A" in result.output


def test_drift_clean_when_gtfs_unchanged() -> None:
    result = invoke("drift", str(VALID_GTFS), str(VALID_GTFS), "--tods", str(VALID_TODS))
    assert result.exit_code == 0
    assert "No referenced" in result.output


def test_drift_json_format(tmp_path: Path) -> None:
    old_dir, new_dir = _copy_gtfs_with_trip_renamed(tmp_path, "103", "103A")
    result = invoke(
        "drift", str(old_dir), str(new_dir), "--tods", str(VALID_TODS), "--format", "json"
    )
    payload = json.loads(result.output)
    assert payload["brokenTripIds"][0]["value"] == "103"
    assert payload["brokenTripIds"][0]["candidates"] == ["103A"]
