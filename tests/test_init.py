"""`tods-validate init`: scaffold a starter package that validates clean."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from tods_validate.api import validate_feed
from tods_validate.cli import main
from tods_validate.init import (
    GTFS_BASE_FILES,
    SHAPES,
    DestinationNotEmptyError,
    scaffold,
    table_header,
)
from tods_validate.schema import TABLES


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


# ---------------------------------------------------------------------------
# scaffold() itself
# ---------------------------------------------------------------------------


def test_scaffold_runs_shape_writes_expected_files(tmp_path: Path) -> None:
    written = scaffold(tmp_path, "runs")

    names = {p.relative_to(tmp_path).as_posix() for p in written}
    assert names == {
        *GTFS_BASE_FILES,
        *SHAPES["runs"],
        "tods-validate.toml",
        ".github/workflows/tods-validate.yml",
    }
    # vehicles are opt-in via --shape runs+vehicles
    assert "vehicles.txt" not in names
    assert "vehicle_assignments.txt" not in names
    for path in written:
        assert path.exists()


def test_scaffold_runs_vehicles_shape_adds_vehicle_files(tmp_path: Path) -> None:
    written = scaffold(tmp_path, "runs+vehicles")
    names = {p.relative_to(tmp_path).as_posix() for p in written}
    assert "vehicles.txt" in names
    assert "vehicle_assignments.txt" in names


def test_scaffold_rejects_unknown_shape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown shape"):
        scaffold(tmp_path, "bogus")


def test_scaffold_refuses_nonempty_dest_without_force(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("x", encoding="utf-8")
    with pytest.raises(DestinationNotEmptyError):
        scaffold(tmp_path, "runs")


def test_scaffold_force_overwrites_nonempty_dest(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("x", encoding="utf-8")
    written = scaffold(tmp_path, "runs", force=True)
    assert written  # did not raise, and wrote the usual files


def test_scaffold_is_idempotent_into_its_own_output(tmp_path: Path) -> None:
    scaffold(tmp_path, "runs")
    # Re-running without --force on the directory it just wrote to is exactly
    # the "not empty" case; --force must be able to scaffold over it cleanly.
    written = scaffold(tmp_path, "runs", force=True)
    assert written


def test_scaffold_config_and_workflow_content(tmp_path: Path) -> None:
    scaffold(tmp_path, "runs")
    config = (tmp_path / "tods-validate.toml").read_text(encoding="utf-8")
    assert 'fail-on = "error"' in config

    workflow = (tmp_path / ".github" / "workflows" / "tods-validate.yml").read_text(
        encoding="utf-8"
    )
    assert "uses: ChelseaKR/tods-validate@" in workflow


# ---------------------------------------------------------------------------
# Drift guard: schema-derived headers can never diverge from schema.TABLES.
# ---------------------------------------------------------------------------


def test_table_header_matches_schema_field_names_exactly() -> None:
    for filename, spec in TABLES.items():
        assert table_header(filename) == [f.name for f in spec.fields]


def test_generated_tods_native_files_have_schema_exact_headers(tmp_path: Path) -> None:
    """run_events/employee_run_dates/vehicles/vehicle_assignments carry every
    field the spec defines (no supplement-style optional subsetting), so the
    sample data copied in must still expose the full schema header."""
    scaffold(tmp_path, "runs+vehicles")
    for filename in (
        "run_events.txt",
        "employee_run_dates.txt",
        "vehicles.txt",
        "vehicle_assignments.txt",
    ):
        header = (tmp_path / filename).read_text(encoding="utf-8").splitlines()[0].split(",")
        assert header == table_header(filename)


def test_every_shape_table_is_a_known_schema_table() -> None:
    for filenames in SHAPES.values():
        for filename in filenames:
            assert filename in TABLES


# ---------------------------------------------------------------------------
# End-to-end: the scaffold validates clean.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_scaffold_validates_with_zero_errors_and_warnings(tmp_path: Path, shape: str) -> None:
    scaffold(tmp_path, shape)
    result = validate_feed(tmp_path)
    assert result.ok, [f"{f.rule_id}: {f.message}" for f in result.errors]
    assert result.error_count == 0
    assert result.errors == []
    assert result.warnings == []


def test_cli_init_then_validate_is_clean(tmp_path: Path) -> None:
    dest = tmp_path / "feed"
    result = invoke("init", str(dest))
    assert result.exit_code == 0, result.output
    assert "wrote" in result.output

    result = invoke("validate", str(dest))
    assert result.exit_code == 0, result.output


def test_cli_init_default_dest_is_cwd(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0, result.output
        assert (Path(cwd) / "run_events.txt").exists()


def test_cli_init_rejects_nonempty_dest_without_force(tmp_path: Path) -> None:
    (tmp_path / "already-here.txt").write_text("x", encoding="utf-8")
    result = invoke("init", str(tmp_path))
    assert result.exit_code == 2
    assert "not empty" in result.output


def test_cli_init_shape_flag(tmp_path: Path) -> None:
    dest = tmp_path / "feed"
    result = invoke("init", str(dest), "--shape", "runs+vehicles")
    assert result.exit_code == 0, result.output
    assert (dest / "vehicles.txt").exists()


def test_cli_init_rejects_unknown_shape(tmp_path: Path) -> None:
    result = invoke("init", str(tmp_path / "feed"), "--shape", "bogus")
    assert result.exit_code != 0
