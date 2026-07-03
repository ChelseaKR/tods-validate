"""Configuration file loading and the --ignore/--config CLI options."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from conftest import FIXTURES
from tods_validate.cli import main
from tods_validate.config import Config, ConfigError, _profile_config, load_config


def invoke(*args: str, cwd: Path | None = None):
    runner = CliRunner()
    if cwd is None:
        return runner.invoke(main, list(args))
    import contextlib
    import os

    @contextlib.contextmanager
    def chdir(path: Path):
        before = os.getcwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(before)

    with chdir(cwd):
        return runner.invoke(main, list(args))


def test_missing_discovered_file_is_empty_config(tmp_path: Path) -> None:
    assert load_config(None, start_dir=tmp_path) == Config()


def test_discovered_file_is_used(tmp_path: Path) -> None:
    (tmp_path / "tods-validate.toml").write_text(
        'ignore = ["TODS-W206"]\n"fail-on" = "warning"\n', encoding="utf-8"
    )
    config = load_config(None, start_dir=tmp_path)
    assert config.ignore == ("TODS-W206",)
    assert config.fail_on == "warning"


def test_unknown_key_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text("severity = 3\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown setting"):
        load_config(path)


def test_bad_ignore_type_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('ignore = "TODS-W206"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="list of rule IDs"):
        load_config(path)


def test_ingest_ready_profile_config_is_a_strict_gate() -> None:
    config = _profile_config("ingest-ready")
    assert config.fail_on == "warning"
    assert "coverage" in config.enable
    assert "advisory" in config.enable


def test_unknown_profile_name_is_a_key_error() -> None:
    # PROFILES membership is validated by the caller (see
    # test_config_extends.test_unknown_profile_errors); _profile_config
    # itself just indexes the dict.
    with pytest.raises(KeyError):
        _profile_config("nonexistent-profile")


def test_cli_ignore_suppresses_rule_and_exit_code() -> None:
    fixture = str(FIXTURES / "invalid" / "TODS-E201")
    result = invoke(fixture, "--ignore", "TODS-E201")
    assert result.exit_code == 0, result.output
    assert "ERROR TODS-E201" not in result.output
    assert "No problems found." in result.output


def test_cli_unknown_ignore_id_exits_two() -> None:
    result = invoke(str(FIXTURES / "valid" / "tods"), "--ignore", "TODS-E999")
    assert result.exit_code == 2
    assert "TODS-E999" in result.output


def test_cli_config_file_applies(tmp_path: Path) -> None:
    config = tmp_path / "policy.toml"
    config.write_text('ignore = ["TODS-W101"]\n', encoding="utf-8")
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), "--config", str(config))
    assert result.exit_code == 0, result.output
    assert "WARNING TODS-W101" not in result.output


def test_cli_discovers_config_in_cwd(tmp_path: Path) -> None:
    (tmp_path / "tods-validate.toml").write_text('"fail-on" = "warning"\n', encoding="utf-8")
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), cwd=tmp_path)
    assert result.exit_code == 1  # warning now fails via config


def test_cli_flag_overrides_config(tmp_path: Path) -> None:
    (tmp_path / "tods-validate.toml").write_text('"fail-on" = "warning"\n', encoding="utf-8")
    result = invoke(str(FIXTURES / "invalid" / "TODS-W101"), "--fail-on", "error", cwd=tmp_path)
    assert result.exit_code == 0


def test_cli_missing_config_file_exits_two(tmp_path: Path) -> None:
    result = invoke(str(FIXTURES / "valid" / "tods"), "--config", str(tmp_path / "nope.toml"))
    assert result.exit_code == 2
