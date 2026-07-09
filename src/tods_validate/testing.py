"""Test helpers for TODS exporters.

Drop these into your exporter's own pytest suite to assert that the feeds you
generate validate cleanly, or that a known-bad input still trips the rule you
expect. They wrap :func:`tods_validate.validate_feed`, so an exporter team gets
a CI gate against the same checks the CLI and GitHub Action run, without
shelling out:

    from tods_validate.testing import assert_feed_valid, assert_feed_produces

    def test_my_exporter_output_is_clean(tmp_path):
        my_exporter.write(tmp_path)
        assert_feed_valid(tmp_path / "tods", gtfs=tmp_path / "gtfs")

    def test_missing_run_event_trip_is_caught(tmp_path):
        my_exporter.write_with_dangling_trip(tmp_path)
        assert_feed_produces(tmp_path / "tods", "TODS-E307")

On failure they raise ``AssertionError`` carrying the same human-readable
report the CLI prints, so a CI failure reads like a validation report rather
than a stack trace. The frames inside these helpers are hidden from pytest
tracebacks (``__tracebackhide__``), so the report is what you see.

These are deliberately kept out of the top-level ``tods_validate`` namespace so
that importing the library never pulls in test-only helpers; import them from
``tods_validate.testing`` explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .api import ValidationResult, validate_feed
from .findings import Severity
from .policy import GatingPolicy
from .report import render_text

_SEVERITY_BY_NAME = {
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
    "info": Severity.INFO,
}


def _coerce_severity(value: str | Severity) -> Severity:
    if isinstance(value, Severity):
        return value
    try:
        return _SEVERITY_BY_NAME[value.lower()]
    except KeyError:
        raise ValueError(
            f"fail_on must be one of {sorted(_SEVERITY_BY_NAME)} or a Severity, got {value!r}"
        ) from None


def assert_feed_valid(
    path: str | Path,
    gtfs: str | Path | None = None,
    *,
    enable: Iterable[str] = (),
    encoding: str | None = None,
    fail_on: str | Severity = "error",
    ignore: Iterable[str] = (),
) -> ValidationResult:
    """Assert the TODS feed at ``path`` validates with no blocking findings.

    Arguments mirror :func:`tods_validate.validate_feed`. ``fail_on`` sets the
    severity that counts as a failure (``"error"`` by default, ``"warning"`` to
    also gate on warnings); ``ignore`` is a set of rule IDs your agency has
    decided to accept and that should not fail the assertion. Returns the
    :class:`tods_validate.ValidationResult` so a passing test can make further
    checks. Raises ``AssertionError`` with the rendered report when any finding
    at or above ``fail_on`` remains after ``ignore`` is applied.
    """
    __tracebackhide__ = True
    threshold = _coerce_severity(fail_on)
    policy = GatingPolicy(fail_on=threshold.name.lower(), ignore=frozenset(ignore))
    result = validate_feed(path, gtfs, enable=enable, encoding=encoding)
    gate = policy.apply(result.findings)
    blocking = [f for f in gate.gating if f.severity >= threshold]
    if blocking:
        raise AssertionError(
            f"{result.source}: expected no findings at or above {threshold.name}, "
            f"found {len(blocking)}:\n" + render_text(blocking, result.source)
        )
    return result


def assert_feed_produces(
    path: str | Path,
    expected: str | Iterable[str],
    gtfs: str | Path | None = None,
    *,
    enable: Iterable[str] = (),
    encoding: str | None = None,
    exactly: bool = False,
) -> ValidationResult:
    """Assert that validating ``path`` produces (at least) the ``expected`` rules.

    ``expected`` is a single rule ID or an iterable of them. By default the
    check is a subset test, so the feed may also produce other findings; pass
    ``exactly=True`` to require the produced rule-ID set to match ``expected``
    with nothing extra. This is the helper for regression-testing that a
    known-bad fixture keeps tripping the right rule. Returns the
    :class:`tods_validate.ValidationResult`; raises ``AssertionError`` naming the
    missing (and, when ``exactly``, the unexpected) rule IDs.
    """
    __tracebackhide__ = True
    wanted = frozenset({expected} if isinstance(expected, str) else expected)
    result = validate_feed(path, gtfs, enable=enable, encoding=encoding)
    produced = {f.rule_id for f in result.findings}
    missing = wanted - produced
    extra = (produced - wanted) if exactly else frozenset()
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"expected but not produced: {sorted(missing)}")
        if extra:
            parts.append(f"produced but not expected: {sorted(extra)}")
        raise AssertionError(
            f"{result.source}: " + "; ".join(parts) + f" (produced {sorted(produced)})"
        )
    return result


__all__ = ["assert_feed_produces", "assert_feed_valid"]
