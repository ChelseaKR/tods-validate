"""Opt-in coverage (TODS-x5xx) and advisory (TODS-x6xx) rules."""

import pytest

from conftest import FIXTURES, VALID_GTFS, VALID_TODS, rule_ids
from tods_validate.runner import run

OPT_IN = ("TODS-I501", "TODS-I502", "TODS-I601", "TODS-I602")
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


# TODS-I602: which pairs of values count as one value spelled two ways. The
# fixture proves the rule fires at all; these pin the two mechanisms that make
# it fire (case and separator) and the three shapes that must not.

_I602_HEADER = (
    "service_id,run_id,event_sequence,job_type,event_type,"
    "start_location,start_time,end_location,end_time"
)


def _run_with_types(tmp_path, *pairs: tuple[str, str]):
    """Write one run whose rows carry the given (job_type, event_type) pairs."""
    rows = "\n".join(
        f"daily,1,{(index + 1) * 10},{job_type},{event_type},s1,"
        f"{6 + index:02d}:00:00,s1,{6 + index:02d}:30:00"
        for index, (job_type, event_type) in enumerate(pairs)
    )
    (tmp_path / "run_events.txt").write_text(f"{_I602_HEADER}\n{rows}\n", encoding="utf-8")
    _, findings = run(tmp_path, enabled=_CATEGORIES)
    return [f for f in findings if f.rule_id == "TODS-I602"]


def test_case_alone_makes_two_spellings_of_one_event_type(tmp_path) -> None:
    findings = _run_with_types(tmp_path, ("Operator", "Sign-In"), ("Operator", "SIGN-IN"))
    assert [f.field for f in findings] == ["event_type"]
    assert "'Sign-In'" in findings[0].message
    assert "'SIGN-IN'" in findings[0].message


def test_separator_alone_makes_two_spellings_of_one_event_type(tmp_path) -> None:
    findings = _run_with_types(tmp_path, ("Operator", "Sign In"), ("Operator", "Sign_In"))
    assert [f.field for f in findings] == ["event_type"]


def test_job_type_is_checked_independently_of_event_type(tmp_path) -> None:
    findings = _run_with_types(tmp_path, ("Bus Operator", "Sign-In"), ("bus_operator", "Sign-In"))
    assert [f.field for f in findings] == ["job_type"]


def test_two_genuinely_different_values_are_not_one_value(tmp_path) -> None:
    assert _run_with_types(tmp_path, ("Operator", "Sign-In"), ("Operator", "Pull-Out")) == []


def test_padding_alone_is_not_a_second_spelling(tmp_path) -> None:
    """Leading and trailing spaces are TODS-W206's finding, not this one.

    Without the strip, ``"Sign-In "`` and ``"Sign-In"`` would be reported here
    as well, so one mistake would be counted twice under two rule IDs.
    """
    findings = _run_with_types(tmp_path, ("Operator", "Sign-In"), ("Operator", "Sign-In "))
    assert findings == []


def test_values_that_are_only_separators_do_not_group_together(tmp_path) -> None:
    """Absence is not a disagreement.

    ``"-"`` and ``"_"`` both normalize to the empty string. Grouping them would
    report two rows that name no event type as two spellings of one, which is
    a missing value (TODS-E201) dressed up as an inconsistency.
    """
    assert _run_with_types(tmp_path, ("Operator", "-"), ("Operator", "_")) == []


def test_the_finding_points_at_the_row_where_the_second_spelling_appears(tmp_path) -> None:
    findings = _run_with_types(
        tmp_path,
        ("Operator", "Sign-In"),
        ("Operator", "Sign-In"),
        ("Operator", "sign in"),
    )
    # Header is line 1, so the third data row is line 4.
    assert [f.row for f in findings] == [4]
    # Most-used spelling first, so the message names the one to standardize on.
    assert findings[0].message.index("'Sign-In'") < findings[0].message.index("'sign in'")
