"""``doctor``: one honest end-to-end pass composing validate/merge/gtfs-validator/stats."""

import json

from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main

E201 = str(FIXTURES / "invalid" / "TODS-E201")


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


def test_doctor_valid_feed_runs_all_stages() -> None:
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0, result.output
    assert "== Validate: RAN ==" in result.output
    assert "== Merge: RAN ==" in result.output
    assert "== GTFS-validator:" in result.output
    assert "== Stats: RAN ==" in result.output
    # No java/jar available in the test environment, so gtfs-validator is
    # honestly skipped, not silently passed.
    assert "SKIPPED" in result.output
    assert "GTFS validity NOT checked" in result.output


def test_doctor_no_companion_gtfs_skips_merge_and_validator_honestly() -> None:
    result = invoke("doctor", E201)
    assert result.exit_code == 1  # TODS-E201's error still fails the gate
    assert "== Validate: RAN ==" in result.output
    assert "== Merge: SKIPPED" in result.output
    assert "== GTFS-validator: SKIPPED" in result.output
    assert "== Stats: RAN ==" in result.output
    assert "GTFS validity NOT checked" in result.output
    # Skipping must never look like a pass: the reason is explicit.
    assert "merge stage was skipped" in result.output


def test_doctor_without_java_or_jar_skips_validator_with_honest_label(monkeypatch) -> None:
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0, result.output
    assert "== GTFS-validator: SKIPPED" in result.output
    assert "GTFS validity NOT checked" in result.output
    assert "java was not found on PATH" in result.output


def test_doctor_json_has_per_stage_status() -> None:
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "json")
    payload = json.loads(result.output)
    assert payload["validator"] == "tods-validate"
    stages = {s["name"]: s for s in payload["stages"]}
    assert set(stages) == {"validate", "merge", "gtfs-validator", "stats"}
    assert stages["validate"]["status"] == "ran"
    assert stages["merge"]["status"] == "ran"
    assert stages["gtfs-validator"]["status"] == "skipped"
    assert stages["gtfs-validator"]["reason"]
    assert stages["stats"]["status"] == "ran"
    assert "stats" in stages["stats"]


def test_doctor_json_no_gtfs_marks_merge_skipped() -> None:
    result = invoke("doctor", E201, "--format", "json")
    payload = json.loads(result.output)
    stages = {s["name"]: s for s in payload["stages"]}
    assert stages["merge"]["status"] == "skipped"
    assert stages["gtfs-validator"]["status"] == "skipped"
    assert stages["validate"]["errors"] >= 1


def test_doctor_markdown_labels_every_stage() -> None:
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "markdown")
    assert "# TODS doctor report:" in result.output
    assert "## Validate: RAN" in result.output
    assert "## Merge: RAN" in result.output
    assert "## GTFS-validator: SKIPPED" in result.output
    assert "## Stats: RAN" in result.output


def test_doctor_missing_path_exits_two() -> None:
    result = invoke("doctor", "no-such-directory")
    assert result.exit_code == 2
    assert "error" in result.output


def test_doctor_valid_feed_alone_no_gtfs_flag() -> None:
    """VALID_TODS has no base GTFS files of its own, only *_supplement.txt,
    so merge still runs (supplement-only additions) even without --gtfs."""
    result = invoke("doctor", str(VALID_TODS))
    assert result.exit_code == 0, result.output
    assert "== Merge: RAN ==" in result.output


def test_doctor_malformed_gtfs_validator_report_fails_honestly(
    tmp_path, monkeypatch
) -> None:
    import shutil
    import subprocess
    from pathlib import Path

    from tods_validate.doctor import _run_gtfs_validator_stage

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")
    fake_jar = tmp_path / "fake-validator.jar"
    fake_jar.write_text("fake jar content")

    # Test cases where report.json parses as valid JSON but is not the expected shape:
    # 1. raw is null / int / list / string (not a dict)
    # 2. raw is a dict missing "notices" key
    # 3. raw is a dict where "notices" is not a list
    bad_contents = [
        "null",
        "[]",
        '"just a string"',
        "123",
        '{"some_other_key": 1}',
        '{"notices": "not a list"}',
    ]

    for bad_content in bad_contents:
        def fake_run(cmd, capture_output, text, timeout, check, content=bad_content):
            # cmd[-1] is output report_dir
            out_dir = Path(cmd[-1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "report.json").write_text(content, encoding="utf-8")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        merged_zip = tmp_path / "merged.zip"
        merged_zip.write_text("fake zip")
        report_dir = tmp_path / f"report_{hash(bad_content)}"

        stage_res = _run_gtfs_validator_stage(
            merged_output=merged_zip,
            run_gtfs_validator=True,
            report_dir=report_dir,
            jar_path=str(fake_jar),
        )

        assert stage_res.status == "failed"
        assert "expected shape" in (stage_res.reason or "")


