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


# The advisory threshold itself. The TODS-I601 fixture spans eight hours
# against a six-hour bound, so it proves the rule fires and says nothing about
# where the bound is: moving _LONG_SPAN_SECONDS to seven hours left every test
# green. These two runs sit either side of the boundary, one second apart.

_HEADER = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time"
)


def _run_spanning(tmp_path, end_time: str) -> set[str]:
    (tmp_path / "run_events.txt").write_text(
        f"{_HEADER}\ndaily,1,10,Operator,s1,06:00:00,s1,{end_time}\n",
        encoding="utf-8",
    )
    _, findings = run(tmp_path, enabled=_CATEGORIES)
    return rule_ids(findings)


def test_a_run_exactly_at_the_long_span_bound_is_not_flagged(tmp_path) -> None:
    from tods_validate.rules.coverage import _LONG_SPAN_SECONDS

    assert _LONG_SPAN_SECONDS == 6 * 3600, (
        "the bound moved; update both sides of this boundary pair rather than "
        "only the one that went red"
    )
    assert "TODS-I601" not in _run_spanning(tmp_path, "12:00:00")


def test_a_run_one_second_past_the_long_span_bound_is_flagged(tmp_path) -> None:
    assert "TODS-I601" in _run_spanning(tmp_path, "12:00:01")
