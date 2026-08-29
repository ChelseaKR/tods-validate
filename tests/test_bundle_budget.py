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


# ---------------------------------------------------------------------------
# The committed measurement, and the prose that quotes it.
#
# `limits` was gated from the day the file landed; `measured` never was. On
# 2026-08-29 the recorded playgroundPageBytes was 39% under the real page and
# publishedSiteBytes 57% under the real tree, both stale since the meta and
# canonical tags landed on the 45 published pages, and both still inside their
# ceilings, so nothing went red. docs/BENCHMARKS.md carried the same two stale
# numbers, and the rationale strings carried them a third time in KiB.
#
# The measurement is bytes, and bytes are exact, so the comparison below is
# exact. Nothing here writes: `scripts/check_bundle_budget.py --update` is how
# the file is regenerated, and it runs only when a person asks.

BENCHMARKS = ROOT / "docs" / "BENCHMARKS.md"

# How each rationale string is expected to quote its own measurement. Precision
# differs per surface because the surfaces differ in size, so the renderings are
# named rather than guessed.
_RATIONALE_FIGURE = {
    "playgroundPageBytes": lambda value: f"{value / 1024:.1f} KiB",
    "publishedSiteBytes": lambda value: f"{value / 1024:.0f} KiB",
    "publishedPageCount": lambda value: f"{value:d}",
    "reportBytesAt10kFindings": lambda value: f"{value / 1024 / 1024:.2f} MiB",
}


def test_the_committed_measurement_is_what_the_surfaces_measure_now() -> None:
    gate = _gate()
    committed = json.loads(BUDGET.read_text(encoding="utf-8"))["measured"]
    assert gate.measure() == committed, (
        "perf/bundle-baseline.json's measured block does not describe the surfaces this "
        "commit ships. Regenerate it: python scripts/check_bundle_budget.py --update"
    )


def test_every_measured_surface_has_a_rationale_that_quotes_its_own_number() -> None:
    document = json.loads(BUDGET.read_text(encoding="utf-8"))
    measured = document["measured"]
    rationale = document["rationale"]
    assert set(rationale) == set(measured), sorted(set(rationale) ^ set(measured))
    assert set(_RATIONALE_FIGURE) == set(measured), sorted(set(_RATIONALE_FIGURE) ^ set(measured))
    for name, value in measured.items():
        figure = _RATIONALE_FIGURE[name](value)
        assert figure in rationale[name], (
            f"the rationale for {name} does not quote its measured value ({figure}); "
            "the prose and the measurement have drifted apart"
        )


def test_the_rationale_counts_the_rules_the_registry_holds() -> None:
    # "One page per rule plus two indexes; 43 rules today" is a count, and a
    # count typed once is a count that stops being true.
    from tods_validate.rules import all_rules

    rationale = json.loads(BUDGET.read_text(encoding="utf-8"))["rationale"]
    assert f"{len(all_rules())} rules today" in rationale["publishedPageCount"]


def test_the_benchmarks_doc_quotes_the_committed_bundle_numbers() -> None:
    # docs/BENCHMARKS.md restates the whole table. It is the third copy of these
    # numbers and was the second to go stale.
    document = json.loads(BUDGET.read_text(encoding="utf-8"))
    text = BENCHMARKS.read_text(encoding="utf-8")
    for name, value in document["measured"].items():
        limit = document["limits"][name]
        row = f"| {value:,} | {limit:,} |"
        assert row in text, (
            f"docs/BENCHMARKS.md has no bundle row reading {row!r} for {name}; "
            "the doc and perf/bundle-baseline.json have drifted apart"
        )
