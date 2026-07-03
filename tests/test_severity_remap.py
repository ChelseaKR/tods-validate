"""The `[severity]` config remap table and its mandatory disclosure.

TODS-W101 is a WARNING-band rule (structure.py); TODS-E201 is an ERROR-band
rule (fields.py). Both have dedicated fixtures under tests/fixtures/invalid/.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from conftest import FIXTURES
from tods_validate.cli import main
from tods_validate.config import Config, ConfigError, load_config
from tods_validate.findings import Finding, Severity
from tods_validate.report import (
    render_github,
    render_html,
    render_markdown,
    render_sarif,
    render_text,
)
from tods_validate.runner import run


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


# --- config parsing -------------------------------------------------------


def test_severity_table_upgrades_warning_to_error(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[severity]\n"TODS-W101" = "error"\n', encoding="utf-8")
    config = load_config(path)
    assert config.severity_remap == (("TODS-W101", "ERROR"),)
    assert config.severity_acknowledged == frozenset()


def test_severity_table_rejects_unknown_rule_id(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[severity]\n"TODS-E999" = "warning"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown rule ID"):
        load_config(path)


def test_severity_table_rejects_bad_level(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[severity]\n"TODS-W101" = "critical"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="level must be one of"):
        load_config(path)


def test_severity_table_must_be_a_table(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text("severity = 3\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a table"):
        load_config(path)


def test_downgrading_error_rule_without_acknowledged_raises(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[severity]\n"TODS-E201" = "warning"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="acknowledged"):
        load_config(path)


def test_downgrading_error_rule_with_acknowledged_succeeds(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text(
        '[severity]\n"TODS-E201" = {level = "warning", acknowledged = true}\n', encoding="utf-8"
    )
    config = load_config(path)
    assert config.severity_remap == (("TODS-E201", "WARNING"),)
    assert config.severity_acknowledged == frozenset({"TODS-E201"})


def test_severity_table_inline_table_rejects_unknown_key(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[severity]\n"TODS-W101" = {level = "info", bogus = true}\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(path)


def test_merge_severity_remap_override_wins(tmp_path: Path) -> None:
    from tods_validate.config import _merge, _parse_data

    base = _parse_data({"severity": {"TODS-W101": "info"}}, "base")
    override = _parse_data({"severity": {"TODS-W101": "error"}}, "override")
    merged = _merge(base, override)
    assert merged.severity_remap == (("TODS-W101", "ERROR"),)


def test_config_equality_still_works() -> None:
    assert Config() == Config()


# --- runner application ----------------------------------------------------


def test_runner_upgrades_warning_and_records_original() -> None:
    _, findings = run(FIXTURES / "invalid" / "TODS-W101", severity_remap={"TODS-W101": "ERROR"})
    hit = [f for f in findings if f.rule_id == "TODS-W101"]
    assert hit
    for f in hit:
        assert f.severity is Severity.ERROR
        assert f.severity_original is Severity.WARNING


def test_runner_leaves_unmapped_rules_alone() -> None:
    _, findings = run(FIXTURES / "invalid" / "TODS-W101", severity_remap={"TODS-E999": "INFO"})
    hit = [f for f in findings if f.rule_id == "TODS-W101"]
    assert hit
    for f in hit:
        assert f.severity_original is None


def test_runner_no_remap_when_mapped_severity_matches_original() -> None:
    _, findings = run(FIXTURES / "invalid" / "TODS-W101", severity_remap={"TODS-W101": "WARNING"})
    hit = [f for f in findings if f.rule_id == "TODS-W101"]
    assert hit
    for f in hit:
        assert f.severity_original is None


# --- CLI end-to-end: exit code changes with an upgrade remap --------------


def test_cli_upgrade_warning_to_error_changes_exit_code(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text('[severity]\n"TODS-W101" = "error"\n', encoding="utf-8")
    result = invoke(
        str(FIXTURES / "invalid" / "TODS-W101"), "--config", str(config), "--fail-on", "error"
    )
    assert result.exit_code == 1, result.output
    assert "ERROR TODS-W101" in result.output


def test_cli_without_remap_warning_does_not_fail_on_error(tmp_path: Path) -> None:
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), "--fail-on", "error")
    assert result.exit_code == 0, result.output


def test_cli_unknown_severity_rule_id_exits_two(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text('[severity]\n"TODS-E999" = "warning"\n', encoding="utf-8")
    result = invoke(str(FIXTURES / "valid" / "tods"), "--config", str(config))
    assert result.exit_code == 2
    assert "TODS-E999" in result.output


# --- disclosure across every output format ---------------------------------

FINDING = Finding(
    rule_id="TODS-W101",
    severity=Severity.ERROR,
    file="run_events.txt",
    row=3,
    message="Example message.",
    severity_original=Severity.WARNING,
)

ACK_FINDING = Finding(
    rule_id="TODS-E201",
    severity=Severity.WARNING,
    file="run_events.txt",
    row=4,
    message="Example message two.",
    severity_original=Severity.ERROR,
)


def test_text_report_discloses_remap() -> None:
    text = render_text([FINDING], "feed/")
    assert "Local policy: 1 severity remapped" in text
    assert "TODS-W101: WARNING -> ERROR" in text
    assert "(spec: WARNING)" in text


def test_text_report_discloses_multiple_remaps_pluralized() -> None:
    text = render_text([FINDING, ACK_FINDING], "feed/")
    assert "Local policy: 2 severities remapped" in text
    assert "TODS-E201: ERROR -> WARNING (acknowledged)" in text


def test_markdown_report_discloses_remap() -> None:
    out = render_markdown([FINDING], "feed/")
    assert "Local policy: 1 severity remapped" in out
    assert "(spec: WARNING)" in out


def test_markdown_stamp_output_discloses_remap() -> None:
    out = render_markdown([FINDING], "feed/", stamp=True)
    assert "Local policy: 1 severity remapped" in out
    assert "_Generated by tods-validate" in out


def test_json_to_dict_carries_severity_original() -> None:
    payload = FINDING.to_dict()
    assert payload["severity_original"] == "WARNING"
    clean = Finding(rule_id="TODS-I102", severity=Severity.INFO, message="x")
    assert clean.to_dict()["severity_original"] is None


def test_github_annotations_disclose_remap() -> None:
    out = render_github([FINDING], "feed/")
    assert "(spec: WARNING)" in out
    assert "Local policy: 1 severity remapped" in out


def test_sarif_discloses_remap() -> None:
    import json

    payload = json.loads(render_sarif([FINDING], "feed/"))
    result = payload["runs"][0]["results"][0]
    assert result["properties"]["severityOriginal"] == "WARNING"
    assert payload["runs"][0]["properties"]["severityRemapDisclosure"]


def test_html_report_discloses_remap() -> None:
    out = render_html([FINDING], "feed/")
    assert "Local policy: 1 severity remapped" in out


def test_no_disclosure_when_nothing_remapped() -> None:
    clean = Finding(rule_id="TODS-I102", severity=Severity.INFO, message="ok")
    assert "Local policy" not in render_text([clean], "feed/")
    assert "Local policy" not in render_markdown([clean], "feed/")
    assert "Local policy" not in render_github([clean], "feed/")
    assert "Local policy" not in render_html([clean], "feed/")


def test_cli_json_report_carries_severity_original_field(tmp_path: Path) -> None:
    import json

    config = tmp_path / "tods-validate.toml"
    config.write_text('[severity]\n"TODS-W101" = "error"\n', encoding="utf-8")
    result = invoke(
        str(FIXTURES / "invalid" / "TODS-W101"), "--config", str(config), "--format", "json"
    )
    payload = json.loads(result.output)
    hits = [f for f in payload["findings"] if f["rule_id"] == "TODS-W101"]
    assert hits
    assert all(f["severity_original"] == "WARNING" for f in hits)


def test_cli_stamp_output_discloses_remap(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text('[severity]\n"TODS-W101" = "error"\n', encoding="utf-8")
    result = invoke(
        str(FIXTURES / "invalid" / "TODS-W101"),
        "--config",
        str(config),
        "--format",
        "markdown",
        "--stamp",
    )
    assert "Local policy: " in result.output
    assert "severity remapped" in result.output or "severities remapped" in result.output
