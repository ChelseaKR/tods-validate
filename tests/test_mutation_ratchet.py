"""The mutation ratchet is a gate, not a job summary (CQ-47).

`.github/workflows/mutation.yml` carried `continue-on-error: true` on the job
and `|| true` on every step, so it could not fail: a kill rate that halved
rendered exactly like one that did not move. These pin the comparison, and
that the workflow no longer suppresses its own result.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_mutation_ratchet.py"
BASELINE = ROOT / "perf" / "mutation-baseline.json"
WORKFLOW = ROOT / ".github" / "workflows" / "mutation.yml"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_mutation_ratchet", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _with(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stats: dict[str, int] | None,
    floor: float | None = 0.6,
) -> ModuleType:
    gate = _gate()
    stats_path = tmp_path / "stats.json"
    if stats is not None:
        stats_path.write_text(json.dumps(stats), encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"killRateFloor": floor}), encoding="utf-8")
    monkeypatch.setattr(gate, "STATS", stats_path)
    monkeypatch.setattr(gate, "BASELINE", baseline_path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    return gate


def test_a_rate_below_the_floor_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _with(monkeypatch, tmp_path, {"killed": 100, "survived": 100, "no_tests": 5})
    assert gate.main() == 1  # 50%


def test_a_rate_at_the_floor_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _with(monkeypatch, tmp_path, {"killed": 60, "survived": 40, "no_tests": 5})
    assert gate.main() == 0  # exactly 60%


def test_missing_stats_fail_rather_than_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A mutation run that produced no stats must not read as "floor held".
    gate = _with(monkeypatch, tmp_path, None)
    assert gate.main() == 1


def test_a_missing_floor_fails_rather_than_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _with(monkeypatch, tmp_path, {"killed": 999, "survived": 0}, floor=None)
    assert gate.main() == 1


def test_untested_mutants_do_not_inflate_the_rate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # `no_tests` counts mutants no test touches. Folding them in would let a
    # coverage change move a number meant to track assertion strength, and
    # counting them as kills would let dead code raise the rate.
    gate = _gate()
    assert gate.kill_rate({"killed": 60, "survived": 40, "no_tests": 1000}) == pytest.approx(0.6)


def test_the_committed_floor_is_below_the_committed_measurement() -> None:
    # A floor above the last measurement is a gate that is already red; a floor
    # at it is one that noise turns red. Both get muted, which is how this
    # workflow ended up unable to fail in the first place.
    gate = _gate()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    measured = gate.kill_rate(baseline["stats"])
    assert baseline["killRateFloor"] < measured
    assert baseline["killRateFloor"] >= measured - 0.05
    assert baseline["target"] > measured, "the target should still be something to move toward"


def test_the_workflow_no_longer_suppresses_its_own_result() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["mutmut"]
    assert "continue-on-error" not in job, (
        "the mutation job suppresses its own exit status again; the ratchet "
        "below it cannot fail anything"
    )
    steps = job["steps"]
    ratchet = [s for s in steps if "check_mutation_ratchet.py" in str(s.get("run", ""))]
    assert ratchet, "the workflow does not run the ratchet gate"
    assert "|| true" not in str(ratchet[0]["run"])
