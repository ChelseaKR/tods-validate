"""Conformance corpus: every fixture must trip the rule it is named for.

This is the assertion behind the published conformance corpus — a TODS exporter
can run its own output through tods-validate and check the rule IDs it expects.
All opt-in categories are enabled so coverage and advisory fixtures are covered
too.
"""

from pathlib import Path

import pytest

from conftest import FIXTURES, rule_ids
from tods_validate.rules import CATEGORIES
from tods_validate.runner import run

_FIXTURE_IDS = sorted(p.name for p in (FIXTURES / "invalid").iterdir() if p.is_dir())
_ALL_CATEGORIES = frozenset(set(CATEGORIES))


@pytest.mark.parametrize("rule_id", _FIXTURE_IDS)
def test_fixture_trips_its_own_rule(rule_id: str) -> None:
    path = FIXTURES / "invalid" / rule_id
    _, findings = run(path, enabled=_ALL_CATEGORIES)
    assert rule_id in rule_ids(findings), (
        f"{rule_id} fixture did not produce {rule_id}: got {sorted(rule_ids(findings))}"
    )


def test_corpus_covers_every_rule() -> None:
    from tods_validate.rules import all_rules

    assert set(_FIXTURE_IDS) == {r.id for r in all_rules()}


def test_fixture_directory_is_not_empty() -> None:
    for rule_id in _FIXTURE_IDS:
        files = list((FIXTURES / "invalid" / Path(rule_id)).iterdir())
        assert files, f"{rule_id} fixture directory is empty"
