"""Opt-in coverage (TODS-x5xx) and advisory (TODS-x6xx) rules."""

import pytest

from conftest import FIXTURES, VALID_GTFS, VALID_TODS, rule_ids
from tods_validate.runner import run

OPT_IN = ("TODS-I501", "TODS-I502", "TODS-I601")
_CATEGORIES = frozenset({"coverage", "advisory", "experimental"})


@pytest.mark.parametrize("rule_id", OPT_IN)
def test_opt_in_rule_silent_by_default(rule_id: str) -> None:
    _, findings = run(FIXTURES / "invalid" / rule_id)
    assert rule_id not in rule_ids(findings)


@pytest.mark.parametrize("rule_id", OPT_IN)
def test_opt_in_rule_fires_when_enabled(rule_id: str) -> None:
    _, findings = run(FIXTURES / "invalid" / rule_id, enabled=_CATEGORIES)
    assert rule_id in rule_ids(findings)


def test_enable_by_single_id() -> None:
    _, findings = run(FIXTURES / "invalid" / "TODS-I601", enabled=frozenset({"TODS-I601"}))
    assert "TODS-I601" in rule_ids(findings)


def test_opt_in_rules_silent_on_valid_feed_even_when_enabled() -> None:
    # The valid feed has full coverage and breaks, so opt-in rules stay quiet.
    _, findings = run(VALID_TODS, VALID_GTFS, enabled=_CATEGORIES)
    for rule_id in OPT_IN:
        assert rule_id not in rule_ids(findings), rule_id
