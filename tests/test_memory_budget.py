"""The memory budget is a gate, not a number in a document (FIX-04).

Same shape as `tests/test_perf_budget.py`, on the other axis: the measurement
is stubbed so the suite stays fast, and what the gate *does* with a
measurement is what gets pinned. The one test that does measure is the
end-to-end one, which is also the only place the ratio quoted in `SECURITY.md`
is checked against reality.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_memory_budget.py"
BASELINE = ROOT / "perf" / "baseline.json"
SECURITY = ROOT / "SECURITY.md"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_memory_budget", SCRIPT)
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
    monkeypatch.setattr(sys, "argv", ["check_memory_budget.py"])
    return gate


def _measured(gate: ModuleType, monkeypatch: pytest.MonkeyPatch, ratio: float) -> None:
    monkeypatch.setattr(gate, "measure", lambda trips: (ratio, int(ratio * 1000), 1000))


def test_committed_baseline_is_a_valid_document() -> None:
    document = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert document["memoryTrips"] > 0
    assert document["maxMemoryRegressionFactor"] >= 1.0
    assert "peakBytesPerInputByte" in document
    assert "memoryMeasuredOn" in document


def test_growth_past_the_budget_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"memoryTrips": 10, "peakBytesPerInputByte": 37.0, "maxMemoryRegressionFactor": 1.15},
    )
    _measured(gate, monkeypatch, 45.0)  # 1.22x the committed ratio
    assert gate.main() == 1


def test_growth_within_the_budget_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"memoryTrips": 10, "peakBytesPerInputByte": 37.0, "maxMemoryRegressionFactor": 1.15},
    )
    _measured(gate, monkeypatch, 40.0)  # 1.08x
    assert gate.main() == 0


def test_an_unrecorded_baseline_fails_rather_than_passing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The failure this whole shape exists for: nothing to compare against must
    # not read as "within budget".
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"memoryTrips": 10, "peakBytesPerInputByte": None, "maxMemoryRegressionFactor": 1.15},
    )
    _measured(gate, monkeypatch, 1.0)
    assert gate.main() == 1


def test_a_missing_baseline_file_fails_rather_than_passing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _gate()
    monkeypatch.setattr(gate, "BASELINE", tmp_path / "absent.json")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_memory_budget.py"])
    _measured(gate, monkeypatch, 1.0)
    assert gate.main() == 1


def test_the_measurement_is_traced_bytes_not_resident_set_size() -> None:
    # RSS depends on the allocator and the platform; traced peak counts the
    # bytes this code asked Python for, which is what makes the committed
    # number comparable across machines.
    source = SCRIPT.read_text(encoding="utf-8")
    assert "tracemalloc.get_traced_memory()" in source
    assert "resource.getrusage" not in source


def test_security_md_quotes_the_committed_ratio() -> None:
    # SECURITY.md states a memory ceiling next to the zip-bomb limits. A
    # ceiling written once and never re-derived is the claim this repository
    # keeps finding; this ties the prose to the measured number.
    ratio = json.loads(BASELINE.read_text(encoding="utf-8"))["peakBytesPerInputByte"]
    assert f"{ratio:.0f}x" in SECURITY.read_text(encoding="utf-8"), (
        f"SECURITY.md does not quote the committed peak-memory ratio ({ratio:.0f}x); "
        "the prose and perf/baseline.json have drifted apart"
    )


def test_the_real_measurement_matches_the_committed_baseline() -> None:
    # The one test that actually measures. Everything above stubs the
    # measurement, so without this the gate could be internally consistent and
    # still describe a program that no longer exists.
    gate = _gate()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    # At the committed size, because the ratio is size-dependent: fixed
    # overhead (imports, the rule registry) is a larger share of a small feed,
    # so a smaller measurement is not comparable to the committed number.
    ratio, peak, input_bytes = gate.measure(int(baseline["memoryTrips"]))
    budget = float(baseline["maxMemoryRegressionFactor"])
    committed = float(baseline["peakBytesPerInputByte"])
    assert peak > 0
    assert input_bytes > 0
    assert ratio / committed <= budget, (
        f"measured {ratio:.2f}x against a committed {committed:.2f}x, past the {budget:.2f}x budget"
    )
