"""The phase-gate tripwire cannot report a pass it did not earn.

`docs/MULTIYEAR-PLAN.md` says a phase is not scheduled until it can be worked,
which leaves one thing unanswered: how anybody finds out that it can be.
`scripts/check_phase_gates.py` answers it by re-reading the gates. These pin
the property that matters, which is not "does it notice a change" but "can it
report unchanged for something it never read" -- the failure phase 1 fixed
three times over in this repository.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_phase_gates.py"
GATES = ROOT / "docs" / "phase-gates.json"


def _tripwire() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_phase_gates", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _document(states: list[str]) -> dict[str, object]:
    return {
        "recordedAt": "2026-08-27",
        "gates": [
            {
                "id": f"gate-{index}",
                "phase": 5,
                "repo": "owner/repo",
                "kind": "issue",
                "number": 100 + index,
                "recordedState": state,
                "trigger": "someone answering",
                "unblocks": "a phase",
            }
            for index, state in enumerate(states)
        ],
    }


def test_a_moved_gate_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire = _tripwire()
    monkeypatch.setattr(tripwire, "fetch_state", lambda repo, kind, number: "closed")
    changed, unreadable, compared = tripwire.compare(_document(["open", "open"]))
    assert len(changed) == 2
    assert unreadable == []
    assert len(compared) == 2
    assert "someone answering" in changed[0], "a moved gate must say what it unblocks"


def test_a_gate_that_could_not_be_read_is_not_reported_as_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The whole point. An unreadable gate must never be counted among the ones
    # that held: that is how a tripwire turns an outage into a green tick.
    tripwire = _tripwire()

    def unreadable(repo: str, kind: str, number: int) -> str:
        raise tripwire.Unreadable(f"{repo}#{number}: network down")

    monkeypatch.setattr(tripwire, "fetch_state", unreadable)
    changed, not_read, compared = tripwire.compare(_document(["open", "open"]))
    assert changed == []
    assert len(not_read) == 2
    assert compared == [], "an unread gate must not appear among the compared ones"


def test_a_partial_read_reports_what_it_did_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    # The subtler half: some gates read, some not. A report that only counts
    # the ones it managed cannot be told from a complete one.
    tripwire = _tripwire()

    def sometimes(repo: str, kind: str, number: int) -> str:
        if number == 101:
            raise tripwire.Unreadable(f"{repo}#{number}: rate limited")
        return "open"

    monkeypatch.setattr(tripwire, "fetch_state", sometimes)
    changed, not_read, compared = tripwire.compare(_document(["open", "open", "open"]))
    assert changed == []
    assert len(not_read) == 1
    assert len(compared) == 2


def test_a_run_that_compared_nothing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire = _tripwire()
    with pytest.raises(tripwire.Unreadable):
        tripwire.compare({"recordedAt": "2026-08-27", "gates": []})


def test_an_unchanged_set_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Positive control. A tripwire that reported every gate as moved would
    # satisfy the first test and be useless.
    tripwire = _tripwire()
    monkeypatch.setattr(tripwire, "fetch_state", lambda repo, kind, number: "open")
    changed, not_read, compared = tripwire.compare(_document(["open", "open"]))
    assert changed == []
    assert not_read == []
    assert len(compared) == 2


def test_the_exit_code_is_non_zero_for_both_kinds_of_news(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tripwire = _tripwire()
    monkeypatch.setattr(sys, "argv", ["check_phase_gates.py"])
    monkeypatch.setattr(tripwire, "GATES", GATES)

    monkeypatch.setattr(tripwire, "compare", lambda d: (["moved"], [], ["a"]))
    assert tripwire.main() == 1
    monkeypatch.setattr(tripwire, "compare", lambda d: ([], ["not read"], ["a"]))
    assert tripwire.main() == 1
    monkeypatch.setattr(tripwire, "compare", lambda d: ([], [], ["a"]))
    assert tripwire.main() == 0


def test_every_recorded_gate_is_well_formed() -> None:
    # A gate missing its trigger or its unblocks line is a row nobody can act
    # on when it moves, which is the moment it matters most.
    document = json.loads(GATES.read_text(encoding="utf-8"))
    assert document["gates"], "no gates are recorded"
    seen = set()
    for gate in document["gates"]:
        for field in (
            "id",
            "phase",
            "repo",
            "kind",
            "number",
            "recordedState",
            "trigger",
            "unblocks",
        ):
            assert gate.get(field) not in (None, ""), f"{gate.get('id')} has no {field}"
        assert gate["kind"] in ("issue", "pull")
        assert gate["id"] not in seen, f"duplicate gate id {gate['id']}"
        seen.add(gate["id"])


def test_the_plan_and_the_gate_list_name_the_same_blockers() -> None:
    # The plan cites issue numbers in prose. If a gate is recorded here but the
    # plan never mentions it, one of the two is out of date, and prose is the
    # half that rots silently.
    plan = (ROOT / "docs" / "MULTIYEAR-PLAN.md").read_text(encoding="utf-8")
    document = json.loads(GATES.read_text(encoding="utf-8"))
    for gate in document["gates"]:
        assert f"#{gate['number']}" in plan, (
            f"docs/phase-gates.json records {gate['repo']}#{gate['number']} but "
            "the plan never names it"
        )
