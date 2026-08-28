"""The bundle budget is a gate, not a file of numbers.

Same shape as `tests/test_perf_budget.py` and `tests/test_memory_budget.py`:
the comparison logic is exercised against stubbed measurements, and one test
measures for real so the committed numbers cannot describe a program that no
longer exists.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_bundle_budget.py"
BUDGET = ROOT / "perf" / "bundle-baseline.json"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_bundle_budget", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _with_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, document: dict[str, object]
) -> ModuleType:
    gate = _gate()
    path = tmp_path / "bundle-baseline.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(gate, "BUDGET", path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    return gate


def test_the_committed_budget_covers_every_measured_surface() -> None:
    # A surface measured but not budgeted would print and pass. Every key the
    # measurement produces has to have a ceiling.
    gate = _gate()
    limits = json.loads(BUDGET.read_text(encoding="utf-8"))["limits"]
    assert set(gate.measure()) == set(limits)


def test_a_surface_over_budget_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _with_budget(monkeypatch, tmp_path, {"limits": {"playgroundPageBytes": 100}})
    monkeypatch.setattr(gate, "measure", lambda: {"playgroundPageBytes": 101})
    assert gate.main() == 1


def test_a_surface_within_budget_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _with_budget(monkeypatch, tmp_path, {"limits": {"playgroundPageBytes": 100}})
    monkeypatch.setattr(gate, "measure", lambda: {"playgroundPageBytes": 100})
    assert gate.main() == 0


def test_a_surface_with_no_recorded_budget_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The fail-open this shape exists to refuse: a new surface must not be
    # unbudgeted-and-therefore-fine.
    gate = _with_budget(monkeypatch, tmp_path, {"limits": {"playgroundPageBytes": 100}})
    monkeypatch.setattr(gate, "measure", lambda: {"playgroundPageBytes": 1, "newSurface": 1})
    assert gate.main() == 1


def test_an_unrecorded_budget_file_fails_rather_than_passing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _gate()
    monkeypatch.setattr(gate, "BUDGET", tmp_path / "absent.json")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "measure", lambda: {"playgroundPageBytes": 1})
    assert gate.main() == 1


def test_the_real_surfaces_are_within_the_committed_budget() -> None:
    # The one test that measures. Everything above stubs it.
    gate = _gate()
    limits = json.loads(BUDGET.read_text(encoding="utf-8"))["limits"]
    over = {
        name: (value, limits[name])
        for name, value in gate.measure().items()
        if value > limits[name]
    }
    assert not over, f"over the committed bundle budget: {over}"
