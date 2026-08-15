"""The v1 public-contract snapshot is checked against the implementation.

``scripts/check_public_contract.py`` is a ``make verify`` gate, but until now it
reached CI only through the release workflows -- so the contract was verified
for the first time *after* a release tag was cut, and a change to a rule's
declared category could land on main with fully green CI. These tests run the
same comparison in the ordinary test suite, so the gate holds wherever the
suite runs, and pin the two fields that used to be compared against themselves.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from tods_validate.policy import EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_public_contract.py"


def _checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_public_contract", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_implementation_matches_the_reviewed_snapshot() -> None:
    expected, actual = _checker().drift()
    assert actual == expected


def test_a_rule_category_change_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    # The change this gate exists for, and the one everything else is blind to:
    # docs/rules.md renders opt-in text from default_enabled, not category, and
    # the conformance corpus enables every category. Flipping TODS-E307 from
    # core to advisory changes which rules a CI pipeline gets by default.
    checker = _checker()
    rules = tuple(
        replace(r, category="advisory") if r.id == "TODS-E307" else r for r in checker.all_rules()
    )
    monkeypatch.setattr(checker, "all_rules", lambda: rules)
    expected, actual = checker.drift()
    assert actual != expected
    assert checker.main() == 1


def test_exit_codes_are_read_from_the_implementation(monkeypatch: pytest.MonkeyPatch) -> None:
    # Not three literals retyped inside the checker: change what the CLI exits
    # with and the published contract has to be updated to match.
    checker = _checker()
    assert checker._actual_contract()["cliExitCodes"] == {
        "clean": EXIT_CLEAN,
        "findingsAtOrAboveThreshold": EXIT_FINDINGS,
        "usageOrInputError": EXIT_USAGE,
    }
    monkeypatch.setattr(checker, "EXIT_USAGE", 3)
    expected, actual = checker.drift()
    assert actual != expected


def test_a_field_that_cannot_be_recomputed_is_not_compared_at_all() -> None:
    # contractVersion used to be read out of the snapshot and then compared to
    # the snapshot, so it could not mismatch under any code change. It is now
    # excluded by name rather than pretending to be verified -- and the snapshot
    # still has to carry it.
    checker = _checker()
    expected, actual = checker.drift()
    assert "contractVersion" not in actual
    assert "contractVersion" not in expected
    assert checker.UNCHECKED_FIELDS == ("contractVersion",)
    assert set(expected) == set(actual)


def test_the_snapshot_must_carry_the_unchecked_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checker = _checker()
    truncated = tmp_path / "snapshot.json"
    truncated.write_text('{"cliExitCodes": {}}', encoding="utf-8")
    monkeypatch.setattr(checker, "SNAPSHOT", truncated)
    with pytest.raises(SystemExit):
        checker.drift()
