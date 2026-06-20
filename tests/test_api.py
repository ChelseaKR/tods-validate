"""The public Python API (tods_validate.validate_feed)."""

import pytest

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate import Finding, Severity, ValidationResult, validate_feed
from tods_validate.loader import PackageNotFoundError


def test_validate_feed_clean() -> None:
    result = validate_feed(VALID_TODS, VALID_GTFS)
    assert isinstance(result, ValidationResult)
    assert result.ok
    assert result.error_count == 0
    assert result.findings == []


def test_validate_feed_reports_errors() -> None:
    result = validate_feed(FIXTURES / "invalid" / "TODS-E201")
    assert not result.ok
    assert result.error_count >= 1
    assert all(isinstance(f, Finding) for f in result.errors)
    assert all(f.severity is Severity.ERROR for f in result.errors)


def test_validate_feed_enable_opt_in() -> None:
    result = validate_feed(FIXTURES / "invalid" / "TODS-I601", enable=["advisory"])
    assert "TODS-I601" in {f.rule_id for f in result.infos}


def test_validate_feed_missing_path_raises() -> None:
    with pytest.raises(PackageNotFoundError):
        validate_feed("definitely-not-a-real-path")
