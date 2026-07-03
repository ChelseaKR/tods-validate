"""CLI behavior: exit codes, output formats, --gtfs, zip input."""

import json
import zipfile
from pathlib import Path

from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


def test_valid_feed_exits_zero() -> None:
    result = invoke(str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0, result.output
    assert "No problems found." in result.output


def test_errors_exit_one() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-E201"))
    assert result.exit_code == 1
    assert "TODS-E201" in result.output


def test_warnings_alone_exit_zero_by_default() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"))
    assert result.exit_code == 0
    assert "TODS-W101" in result.output


def test_fail_on_warning() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), "--fail-on", "warning")
    assert result.exit_code == 1


def test_missing_path_exits_two() -> None:
    result = invoke("no-such-directory")
    assert result.exit_code == 2
    assert "error" in result.output


def test_json_format_is_stable_and_parseable() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-E201"), "--format", "json")
    payload = json.loads(result.output)
    assert payload["validator"] == "tods-validate"
    assert payload["specVersion"] == "2.1.0"
    assert payload["summary"]["errors"] >= 1
    finding = payload["findings"][0]
    assert set(finding) == {
        "rule_id",
        "severity",
        "file",
        "row",
        "field",
        "location",
        "data",
        "message",
        "suggestion",
        "caused_by",
        "fingerprint",
    }


def test_github_format_emits_annotations() -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-E201"), "--format", "github")
    assert "::error file=run_events.txt,line=2,title=TODS-E201::" in result.output


def test_zip_package(tmp_path: Path) -> None:
    archive = tmp_path / "tods.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for f in VALID_TODS.iterdir():
            zf.write(f, arcname=f.name)
    result = invoke(str(archive), "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0, result.output


def test_version_mentions_spec_version() -> None:
    result = invoke("--version")
    assert "TODS v2.1.0" in result.output
