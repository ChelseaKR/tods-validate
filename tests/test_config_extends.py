"""Config profiles and extends inheritance."""

from pathlib import Path

import pytest

from tods_validate.config import ConfigError, load_config


def test_profile_sets_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "tods-validate.toml"
    cfg.write_text('profile = "strict"\n', encoding="utf-8")
    config = load_config(cfg)
    assert config.fail_on == "warning"
    assert "coverage" in config.enable


def test_profile_ingest_ready_is_at_least_as_strict_as_strict(tmp_path: Path) -> None:
    cfg = tmp_path / "tods-validate.toml"
    cfg.write_text('profile = "ingest-ready"\n', encoding="utf-8")
    config = load_config(cfg)
    assert config.fail_on == "warning"
    assert "coverage" in config.enable
    assert "advisory" in config.enable
    assert config.ignore == ()


def test_local_overrides_profile(tmp_path: Path) -> None:
    cfg = tmp_path / "tods-validate.toml"
    cfg.write_text('profile = "strict"\nfail-on = "error"\n', encoding="utf-8")
    config = load_config(cfg)
    assert config.fail_on == "error"  # local file wins over the profile


def test_extends_merges_base(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    base.write_text('ignore = ["TODS-W206"]\nfail-on = "warning"\n', encoding="utf-8")
    child = tmp_path / "tods-validate.toml"
    child.write_text('extends = "base.toml"\nignore = ["TODS-I108"]\n', encoding="utf-8")
    config = load_config(child)
    assert set(config.ignore) == {"TODS-W206", "TODS-I108"}
    assert config.fail_on == "warning"  # inherited from base


def test_extends_missing_target_errors(tmp_path: Path) -> None:
    child = tmp_path / "tods-validate.toml"
    child.write_text('extends = "nope.toml"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="does not exist"):
        load_config(child)


def test_unknown_profile_errors(tmp_path: Path) -> None:
    cfg = tmp_path / "tods-validate.toml"
    cfg.write_text('profile = "turbo"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown profile"):
        load_config(cfg)


def test_max_findings_must_be_non_negative(tmp_path: Path) -> None:
    cfg = tmp_path / "tods-validate.toml"
    cfg.write_text("max-findings = -1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="non-negative"):
        load_config(cfg)
