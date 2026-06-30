"""The exporter-facing test helpers in tods_validate.testing."""

import pytest

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate import testing, validate_feed
from tods_validate.findings import Severity

E201 = FIXTURES / "invalid" / "TODS-E201"
W206 = FIXTURES / "invalid" / "TODS-W206"


def test_assert_feed_valid_passes_on_the_valid_feed() -> None:
    result = testing.assert_feed_valid(VALID_TODS, VALID_GTFS)
    assert result.ok
    # A stricter gate still passes: the reference feed has no warnings either.
    testing.assert_feed_valid(VALID_TODS, VALID_GTFS, fail_on="warning")
    testing.assert_feed_valid(VALID_TODS, VALID_GTFS, fail_on=Severity.WARNING)


def test_assert_feed_valid_raises_with_the_rendered_report() -> None:
    with pytest.raises(AssertionError, match="ERROR TODS-E201"):
        testing.assert_feed_valid(E201)


def test_assert_feed_valid_ignore_suppresses_accepted_rules() -> None:
    error_ids = {f.rule_id for f in validate_feed(E201).errors}
    assert error_ids  # sanity: the fixture really does error
    # Ignoring every error rule the fixture trips makes the gate pass.
    testing.assert_feed_valid(E201, ignore=error_ids)


def test_assert_feed_valid_warning_gate_catches_warnings() -> None:
    with pytest.raises(AssertionError, match="WARNING"):
        testing.assert_feed_valid(W206, fail_on="warning")


def test_assert_feed_valid_rejects_unknown_fail_on() -> None:
    with pytest.raises(ValueError, match="fail_on"):
        testing.assert_feed_valid(VALID_TODS, VALID_GTFS, fail_on="nope")


def test_assert_feed_produces_accepts_string_or_iterable() -> None:
    testing.assert_feed_produces(E201, "TODS-E201")
    testing.assert_feed_produces(E201, ["TODS-E201"])


def test_assert_feed_produces_reports_missing_rules() -> None:
    with pytest.raises(AssertionError, match="expected but not produced"):
        testing.assert_feed_produces(E201, "TODS-E999")


def test_assert_feed_produces_exactly_flags_extras() -> None:
    produced = {f.rule_id for f in validate_feed(E201).findings}
    # The full produced set matches exactly.
    testing.assert_feed_produces(E201, produced, exactly=True)
    # Dropping one expected rule leaves the rest reported as unexpected extras.
    one = next(iter(produced))
    with pytest.raises(AssertionError, match="produced but not expected"):
        testing.assert_feed_produces(E201, produced - {one}, exactly=True)
