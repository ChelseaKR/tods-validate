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

from tods_validate.loader import FeedFile, Package, Row

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


# --------------------------------------------------------------------------
# The gate can only fire on slowness, so doing less work makes it greener.
# These pin the floor underneath it: a repetition that did not read the feed
# must not be reportable as an extremely fast one.
# --------------------------------------------------------------------------


def _package(rows_by_file: dict[str, int]) -> Package:
    package = Package(source="synthetic")
    for name, count in rows_by_file.items():
        package.files[name] = FeedFile(
            name=name,
            headers=("a",),
            rows=[Row(line=i + 2, values={"a": str(i)}) for i in range(count)],
        )
    return package


def _stub_run(gate: ModuleType, monkeypatch: pytest.MonkeyPatch, packages: list[Package]) -> None:
    """Make each timed repetition return the next package in ``packages``."""
    monkeypatch.setattr(gate, "build_feed", lambda directory, trips: directory.mkdir(parents=True))
    remaining = list(packages)

    def _fake_run(feed: Path) -> tuple[Package, list[object], object]:
        return remaining.pop(0), [], None

    monkeypatch.setattr(gate, "run_with_coverage", _fake_run)


def test_a_repetition_that_read_nothing_is_refused_not_reported_as_fast(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The defect this closes: run()'s result was discarded and the row count was
    # an assumed constant, so a validator that stopped reading the feed burned
    # no CPU, produced an enormous rate, and passed further inside the budget
    # than a correct one. Failure was unreachable from below.
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 100, "repeat": 1, "rowsPerCpuSecond": 1000, "maxRegressionFactor": 2.0},
    )
    _stub_run(gate, monkeypatch, [_package({"trips.txt": 0})])
    with pytest.raises(gate.NoWorkMeasured):
        gate.measure(100, 1)


def test_the_gate_exits_non_zero_when_no_work_was_measured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 100, "repeat": 1, "rowsPerCpuSecond": 1000, "maxRegressionFactor": 2.0},
    )
    _stub_run(gate, monkeypatch, [_package({"trips.txt": 3})])
    monkeypatch.setattr(sys, "argv", ["check_perf_budget.py"])
    assert gate.main() == 1


def test_a_repetition_that_did_the_work_is_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The control. Without it, a floor set impossibly high would satisfy the two
    # tests above and retire the gate instead of grounding it.
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 100, "repeat": 1, "rowsPerCpuSecond": 1, "maxRegressionFactor": 2.0},
    )
    full = {"trips.txt": 100, "run_events.txt": 100, "stops.txt": 10}
    _stub_run(gate, monkeypatch, [_package(full)])
    assert gate.measure(100, 1) > 0


def test_repetitions_that_disagree_about_the_row_count_are_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {"trips": 100, "repeat": 2, "rowsPerCpuSecond": 1, "maxRegressionFactor": 2.0},
    )
    _stub_run(
        gate,
        monkeypatch,
        [
            _package({"trips.txt": 100, "run_events.txt": 100}),
            _package({"trips.txt": 100, "run_events.txt": 150}),
        ],
    )
    with pytest.raises(gate.NoWorkMeasured):
        gate.measure(100, 2)


@pytest.mark.parametrize("declared", [50.0, 0.5, "2.0", None, True])
def test_a_budget_outside_the_reviewed_range_fails_rather_than_widening_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, declared: object
) -> None:
    # maxRegressionFactor is read unbounded out of the same data file as the
    # baseline. A large enough value does not loosen the gate, it retires it,
    # and retiring a gate is a reviewed change rather than a data edit.
    gate = _with_baseline(
        monkeypatch,
        tmp_path,
        {
            "trips": 10,
            "repeat": 1,
            "rowsPerCpuSecond": 1000,
            "maxRegressionFactor": declared,
        },
    )
    _measured(gate, monkeypatch, 400)  # 2.5x slower: inside a 50x budget
    monkeypatch.setattr(sys, "argv", ["check_perf_budget.py"])
    assert gate.main() == 1


def test_the_committed_budget_is_inside_the_reviewed_range() -> None:
    document = json.loads(BASELINE.read_text(encoding="utf-8"))
    gate = _gate()
    assert 1.0 <= document["maxRegressionFactor"] <= gate.MAX_SANE_BUDGET


def test_the_measurement_reports_the_rows_it_actually_parsed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End to end on a small real feed: the count is measured, not assumed.

    Small enough to stay fast; the point is that the number printed comes from
    the loader rather than from `trips * ROWS_PER_TRIP`.
    """
    gate = _gate()
    rate = gate.measure(50, 1)
    assert rate > 0
    printed = capsys.readouterr().out
    assert "rows parsed" in printed
    # 50 trips + 50 run events + 100 stops + 1 calendar + 5 vehicles + 5
    # assignments. The floor the gate checks is trips * ROWS_PER_TRIP = 100, so
    # the real feed clears it with room; a run that read nothing could not. The
    # gap between 211 and 100 is also why the rate's denominator stays the
    # fixed unit of work: switching it to the parsed count would move every
    # published number by that margin.
    assert "211 rows parsed" in printed, printed
