"""Configuration file loading and the --ignore/--config CLI options."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from conftest import FIXTURES
from tods_validate.cli import main
from tods_validate.config import Config, ConfigError, load_config


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
    path.write_text("nonsense-key = 3\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown setting"):
        load_config(path)


def test_bad_ignore_type_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('ignore = "TODS-W206"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="list of rule IDs"):
        load_config(path)


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


def test_workspace_table_sets_history_dir(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[workspace]\n"history-dir" = ".tods-history"\n', encoding="utf-8")
    config = load_config(path)
    assert config.history_dir == ".tods-history"


def test_workspace_unknown_subkey_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('[workspace]\nbogus = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown setting"):
        load_config(path)


def test_workspace_not_a_table_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "tods-validate.toml"
    path.write_text('workspace = "nope"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a table"):
        load_config(path)


def test_batch_history_writes_ledger_entries(tmp_path: Path) -> None:
    history_dir = tmp_path / ".tods-history"
    result = invoke(
        "batch",
        str(FIXTURES / "invalid" / "TODS-E201"),
        "--history",
        str(history_dir),
    )
    assert result.exit_code == 1, result.output
    lines = (history_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_batch_history_from_workspace_config(tmp_path: Path) -> None:
    history_dir = tmp_path / ".tods-history"
    config = tmp_path / "tods-validate.toml"
    config.write_text(
        f'[workspace]\n"history-dir" = "{history_dir.as_posix()}"\n', encoding="utf-8"
    )
    result = invoke("batch", str(FIXTURES / "invalid" / "TODS-E201"), "--config", str(config))
    assert result.exit_code == 1, result.output
    assert (history_dir / "history.jsonl").is_file()


def test_trend_reports_no_history_when_absent(tmp_path: Path) -> None:
    result = invoke("trend", "--history", str(tmp_path / "nope"))
    assert result.exit_code == 0
    assert "No run history yet." in result.output


def test_trend_renders_table_after_two_batch_runs(tmp_path: Path) -> None:
    history_dir = tmp_path / ".tods-history"
    fixture = str(FIXTURES / "invalid" / "TODS-E201")
    invoke("batch", fixture, "--history", str(history_dir))
    invoke("batch", fixture, "--history", str(history_dir))
    result = invoke("trend", "--history", str(history_dir))
    assert result.exit_code == 0
    assert "# Run history trend" in result.output
    assert "|" in result.output
