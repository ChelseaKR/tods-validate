"""The synthetic feed generator is deterministic, labeled, and well-formed."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

from tods_validate.findings import Severity
from tods_validate.runner import run

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_feed.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_feed", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the module's dataclasses (`from __future__ import
    # annotations`) resolve their string annotations via sys.modules at
    # decoration time.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_same_seed_and_params_produce_byte_identical_output(tmp_path: Path) -> None:
    generator = _load_generator()
    out1, out2 = tmp_path / "a", tmp_path / "b"
    for out in (out1, out2):
        generator.build_feed(out, trips=250, deadhead_pct=12.0, seed=7, inject_errors=0.2)

    names1 = sorted(p.name for p in out1.iterdir())
    names2 = sorted(p.name for p in out2.iterdir())
    assert names1 == names2
    for name in names1:
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name


def test_different_seed_changes_output(tmp_path: Path) -> None:
    generator = _load_generator()
    out1, out2 = tmp_path / "a", tmp_path / "b"
    generator.build_feed(out1, trips=250, deadhead_pct=12.0, seed=1, inject_errors=0.0)
    generator.build_feed(out2, trips=250, deadhead_pct=12.0, seed=2, inject_errors=0.0)
    assert (out1 / "run_events.txt").read_bytes() != (out2 / "run_events.txt").read_bytes()


def test_clean_profile_validates_with_no_errors_or_warnings(tmp_path: Path) -> None:
    generator = _load_generator()
    out = tmp_path / "clean"
    exit_code = generator.main(
        ["--profile", "clean-100k", "--trips", "300", "--seed", "5", "--out", str(out)]
    )
    assert exit_code == 0
    _, findings = run(out)
    assert [f.rule_id for f in findings if f.severity != Severity.INFO] == []


@pytest.mark.parametrize("profile", ["drifted-gtfs", "messy-export"])
def test_error_injecting_profiles_exercise_reference_and_semantic_rules(
    profile: str, tmp_path: Path
) -> None:
    generator = _load_generator()
    out = tmp_path / profile
    preset = generator.PROFILES[profile]
    generator.build_feed(
        out,
        trips=int(preset["trips"]),
        deadhead_pct=preset["deadhead_pct"],
        seed=3,
        inject_errors=preset["inject_errors"],
        profile=profile,
    )
    _, findings = run(out)
    rule_ids = {f.rule_id for f in findings}
    # A messy/drifted profile should trip at least one reference (x3xx) or
    # semantic (x4xx) rule band -- the whole point of error injection.
    assert any(rid.split("-")[1][1] in ("3", "4") for rid in rule_ids), sorted(rule_ids)


def test_package_is_loudly_labeled_synthetic_and_reproducible(tmp_path: Path) -> None:
    generator = _load_generator()
    out = tmp_path / "labeled"
    exit_code = generator.main(["--trips", "40", "--seed", "11", "--out", str(out)])
    assert exit_code == 0

    banner = (out / "SYNTHETIC.md").read_text()
    assert "SYNTHETIC" in banner
    assert "11" in banner  # the seed is recorded for reproducibility

    manifest = json.loads((out / "synthetic_manifest.json").read_text())
    assert manifest["synthetic"] is True
    assert manifest["seed"] == 11
    assert manifest["trips"] == 40


def test_out_ending_in_zip_writes_a_valid_archive(tmp_path: Path) -> None:
    generator = _load_generator()
    exit_code = generator.main(
        ["--trips", "50", "--seed", "1", "--out", str(tmp_path / "feed.zip")]
    )
    assert exit_code == 0
    zip_path = tmp_path / "feed.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "run_events.txt" in names
    assert "SYNTHETIC.md" in names
    assert "synthetic_manifest.json" in names

    _, findings = run(zip_path)
    assert [f.rule_id for f in findings if f.severity != Severity.INFO] == []


def test_profile_presets_trips_and_deadhead_pct_but_flags_override(tmp_path: Path) -> None:
    generator = _load_generator()
    out = tmp_path / "override"
    exit_code = generator.main(
        ["--profile", "clean-100k", "--trips", "60", "--seed", "1", "--out", str(out)]
    )
    assert exit_code == 0
    manifest = json.loads((out / "synthetic_manifest.json").read_text())
    assert manifest["trips"] == 60  # explicit --trips wins over the profile's preset
    assert manifest["profile"] == "clean-100k"
