"""Conformance corpus: every fixture must match its reviewed rule-ID set.

This is the assertion behind the published conformance corpus — a TODS exporter
can run its own output through tods-validate and check the rule IDs it expects.
All opt-in categories are enabled so coverage and advisory fixtures are covered
too.
"""

import json
from pathlib import Path

import pytest

from conftest import FIXTURES, rule_ids
from tods_validate.rules import CATEGORIES
from tods_validate.runner import run

_FIXTURE_IDS = sorted(p.name for p in (FIXTURES / "invalid").iterdir() if p.is_dir())
_ALL_CATEGORIES = frozenset(set(CATEGORIES))
_EXPECTATIONS: dict[str, list[str]] = json.loads(
    (FIXTURES / "expectations.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("rule_id", _FIXTURE_IDS)
def test_fixture_matches_reviewed_expectations(rule_id: str) -> None:
    path = FIXTURES / "invalid" / rule_id
    _, findings = run(path, enabled=_ALL_CATEGORIES)
    actual = sorted(rule_ids(findings))
    expected = _EXPECTATIONS[f"invalid/{rule_id}"]
    assert actual == expected, (
        f"{rule_id} fixture produced {actual}; reviewed expectation is {expected}. "
        "Update the fixture or explicitly review and update expectations.json."
    )


def test_corpus_covers_every_rule() -> None:
    from tods_validate.rules import all_rules

    assert set(_FIXTURE_IDS) == {r.id for r in all_rules()}
    assert set(_EXPECTATIONS) == {f"invalid/{rule_id}" for rule_id in _FIXTURE_IDS} | {"valid"}
    for rule_id in _FIXTURE_IDS:
        assert rule_id in _EXPECTATIONS[f"invalid/{rule_id}"]


def test_valid_fixture_matches_reviewed_expectations() -> None:
    _, findings = run(
        FIXTURES / "valid" / "tods",
        FIXTURES / "valid" / "gtfs",
        enabled=_ALL_CATEGORIES,
    )
    assert sorted(rule_ids(findings)) == _EXPECTATIONS["valid"]


def test_fixture_directory_is_not_empty() -> None:
    for rule_id in _FIXTURE_IDS:
        files = list((FIXTURES / "invalid" / Path(rule_id)).iterdir())
        assert files, f"{rule_id} fixture directory is empty"
