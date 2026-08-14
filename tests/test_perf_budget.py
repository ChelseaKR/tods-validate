"""The perf budget is a gate, not a script that exists (QM-02).

These tests exercise the comparison, not the benchmark: the measurement is
stubbed so the suite stays fast and machine-independent, while what the gate
*does* with a measurement -- pass, fail, or refuse to answer -- is pinned.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_perf_budget.py"
BASELINE = ROOT / "perf" / "baseline.json"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_perf_budget", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _with_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, document: dict[str, object]
) -> ModuleType:
    gate = _gate()
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(gate, "BASELINE", path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    return gate


def _measured(gate: ModuleType, monkeypatch: pytest.MonkeyPatch, rate: float) -> None:
    monkeypatch.setattr(gate, "measure", lambda trips, repeat: rate)


def test_committed_baseline_is_a_valid_document() -> None:
    document = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert document["trips"] > 0
    assert document["repeat"] >= 1
    assert document["maxRegressionFactor"] >= 1.0
    # rowsPerCpuSecond may legitimately be null until it is recorded from the
    # CI runner; the gate below is what refuses to pass in that state.
    assert "rowsPerCpuSecond" in document
    assert "measuredOn" in document


def test_a_regression_past_the_budget_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 10, "repeat": 1, "rowsPerCpuSecond": 1000, "maxRegressionFactor": 2.0},
    )
    _measured(gate, monkeypatch, 400)  # 2.5x slower
    monkeypatch.setattr(sys, "argv", ["check_perf_budget.py"])
    assert gate.main() == 1


def test_a_regression_within_the_budget_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 10, "repeat": 1, "rowsPerCpuSecond": 1000, "maxRegressionFactor": 2.0},
    )
    _measured(gate, monkeypatch, 600)  # 1.67x slower
    monkeypatch.setattr(sys, "argv", ["check_perf_budget.py"])
    assert gate.main() == 0


def test_an_unrecorded_baseline_fails_rather_than_passing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The failure mode that matters: nothing to compare against must not read as
    # "within budget". A perf gate that passes when it has no baseline is the
    # same defect as a check reported as run when it never executed.
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 10, "repeat": 1, "rowsPerCpuSecond": None, "maxRegressionFactor": 2.0},
    )
    _measured(gate, monkeypatch, 999_999)
    monkeypatch.setattr(sys, "argv", ["check_perf_budget.py"])
    assert gate.main() == 1


def test_a_missing_baseline_file_fails_rather_than_passing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _gate()
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "absent.json")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    _measured(gate, monkeypatch, 999_999)
    monkeypatch.setattr(sys, "argv", ["check_perf_budget.py"])
    assert gate.main() == 1


def test_measurement_uses_cpu_time_not_wall_clock() -> None:
    # Wall clock on a shared runner measures the runner's other tenants; a
    # budget that fires on someone else's build is a budget that gets muted.
    source = SCRIPT.read_text(encoding="utf-8")
    assert "time.process_time()" in source
