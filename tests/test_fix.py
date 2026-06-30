"""The fix command: safe, deterministic whitespace trimming (unit + e2e)."""

from pathlib import Path

from click.testing import CliRunner

from tods_validate.cli import main
from tods_validate.fix import fix_package
from tods_validate.runner import run

# run_events.txt with four whitespace-padded values, like the spec's own
# column-aligned examples (which trip TODS-W206).
_PADDED = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time\n"
    "weekday ,10000 ,10 ,sign-in   ,garage,08:45:00,garage,08:50:00\n"
)
_CLEAN = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time\n"
    "weekday,10000,10,sign-in,garage,08:45:00,garage,08:50:00\n"
)


def _src(tmp_path: Path, text: str = _PADDED) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "run_events.txt").write_text(text)
    return src


def test_fix_package_counts_trimmed_values_dry_run(tmp_path: Path) -> None:
    result = fix_package(_src(tmp_path))
    assert result.trimmed == {"run_events.txt": 4}
    assert result.total_trimmed == 4
    assert result.written == []  # dry run writes nothing


def test_fix_writes_clean_package_and_clears_w206(tmp_path: Path) -> None:
    src = _src(tmp_path)
    _, before = run(src)
    assert any(f.rule_id == "TODS-W206" for f in before), "padded feed should trip W206"
    out = tmp_path / "out"
    result = fix_package(src, output=out)
    assert "run_events.txt" in result.written
    _, after = run(out)
    assert not any(f.rule_id == "TODS-W206" for f in after), "fixed feed should be W206-free"


def test_fix_is_idempotent(tmp_path: Path) -> None:
    src = _src(tmp_path)
    out = tmp_path / "out"
    fix_package(src, output=out)
    again = fix_package(out)
    assert again.trimmed == {}
    assert not again.changed_any


def test_fix_writes_zip(tmp_path: Path) -> None:
    src = _src(tmp_path)
    out = tmp_path / "fixed.zip"
    result = fix_package(src, output=out)
    assert out.is_file()
    assert "run_events.txt" in result.written
    _, after = run(out)
    assert not any(f.rule_id == "TODS-W206" for f in after)


def test_fix_cli_dry_run_reports_without_writing(tmp_path: Path) -> None:
    src = _src(tmp_path)
    result = CliRunner().invoke(main, ["fix", str(src)])
    assert result.exit_code == 0
    assert "trimmed whitespace on 4 value(s)" in result.output
    assert "dry run" in result.output


def test_fix_cli_writes_output(tmp_path: Path) -> None:
    src = _src(tmp_path)
    out = tmp_path / "out"
    result = CliRunner().invoke(main, ["fix", str(src), "-o", str(out)])
    assert result.exit_code == 0
    assert "wrote" in result.output
    assert "weekday ," not in (out / "run_events.txt").read_text()  # padding gone


def test_fix_cli_nothing_to_fix(tmp_path: Path) -> None:
    src = _src(tmp_path, _CLEAN)
    result = CliRunner().invoke(main, ["fix", str(src)])
    assert result.exit_code == 0
    assert "Nothing to fix" in result.output


_HEADER = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time\n"
)
_ROW = "weekday,10000,10,sign-in,garage,08:45:00,garage,08:50:00\n"


def test_fix_drops_entirely_blank_rows(tmp_path: Path) -> None:
    src = _src(tmp_path, _HEADER + _ROW + ",,,,,,,\n")  # a stray all-blank row
    _, before = run(src)
    assert any(f.rule_id == "TODS-E201" for f in before), "the blank row should trip E201"
    result = fix_package(src, output=tmp_path / "out")
    assert result.blank_rows_dropped == {"run_events.txt": 1}
    _, after = run(tmp_path / "out")
    assert not any(f.rule_id == "TODS-E201" for f in after)


def test_fix_drops_exact_duplicate_rows(tmp_path: Path) -> None:
    src = _src(tmp_path, _HEADER + _ROW + _ROW)  # the same row twice
    result = fix_package(src, output=tmp_path / "out")
    assert result.duplicate_rows_dropped == {"run_events.txt": 1}
    body = (tmp_path / "out" / "run_events.txt").read_text().splitlines()
    assert body.count(_ROW.strip()) == 1  # only one copy remains


def test_fix_keeps_rows_that_share_a_key_but_differ(tmp_path: Path) -> None:
    # Same primary key, different end_time: a real conflict, not a duplicate.
    conflict = "weekday,10000,10,sign-in,garage,08:45:00,garage,08:55:00\n"
    src = _src(tmp_path, _HEADER + _ROW + conflict)
    result = fix_package(src, output=tmp_path / "out")
    assert result.duplicate_rows_dropped == {}  # nothing dropped
    kept = (tmp_path / "out" / "run_events.txt").read_text().splitlines()
    assert len(kept) == 3  # header + both rows


def test_fix_cli_reports_all_categories(tmp_path: Path) -> None:
    src = _src(
        tmp_path,
        _HEADER
        + "weekday ,10000,10,x,garage,08:45:00,garage,08:50:00\n"
        + _ROW
        + _ROW
        + ",,,,,,,\n",
    )
    result = CliRunner().invoke(main, ["fix", str(src)])
    assert result.exit_code == 0
    assert "trimmed whitespace" in result.output
    assert "blank row" in result.output
    assert "duplicate row" in result.output
