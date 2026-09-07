"""OPS-W001: is a movement in this run possible in the time allowed?

The rule asserts a physical claim about a schedule, so these tests are written
around the three ways such a check goes wrong: it answers about a pair it could
not see, it answers with a threshold nobody stated, or it answers about the
wrong pair entirely.
"""

from __future__ import annotations

import pytest

from conftest import VALID_GTFS, VALID_TODS, rule_ids
from tods_validate.rules import DEFAULT_MAX_IMPLIED_SPEED_KPH, Measurement
from tods_validate.rules.feasibility import great_circle_km
from tods_validate.runner import run, run_with_coverage

_ENABLED = frozenset({"feasibility"})

_HEADER = (
    "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,end_time"
)

# Two points 30.0 km apart on the same meridian: 0.27 degrees of latitude.
_NEAR = (34.050000, -118.250000)
_FAR = (34.320000, -118.250000)


def _write(tmp_path, rows: str, stops: str | None = None) -> None:
    (tmp_path / "run_events.txt").write_text(f"{_HEADER}\n{rows}\n", encoding="utf-8")
    if stops is None:
        stops = (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            f"near,Near,{_NEAR[0]:.6f},{_NEAR[1]:.6f}\n"
            f"far,Far,{_FAR[0]:.6f},{_FAR[1]:.6f}\n"
        )
    (tmp_path / "stops.txt").write_text(stops, encoding="utf-8")


def _findings(tmp_path, **kwargs):
    _, findings, _ = run_with_coverage(tmp_path, enabled=_ENABLED, **kwargs)
    return [f for f in findings if f.rule_id == "OPS-W001"]


def _measurement(tmp_path, **kwargs) -> Measurement | None:
    _, _, coverage = run_with_coverage(tmp_path, enabled=_ENABLED, **kwargs)
    for outcome in coverage.outcomes:
        if outcome.id == "OPS-W001":
            return outcome.measurement
    raise AssertionError("OPS-W001 is not in the coverage manifest")


# ---------------------------------------------------------------------------
# The distance model
# ---------------------------------------------------------------------------


def test_great_circle_matches_a_known_distance() -> None:
    # Los Angeles to San Francisco city halls, 559 km great-circle.
    km = great_circle_km((34.0522, -118.2437), (37.7749, -122.4194))
    assert 558.0 < km < 560.0, km


def test_great_circle_is_zero_for_one_point() -> None:
    assert great_circle_km(_NEAR, _NEAR) == 0.0


def test_the_test_fixture_points_really_are_thirty_km_apart() -> None:
    """The fixtures below encode 360 km/h; that only holds if this does.

    Without this, a mistake in the fixture coordinates would move every
    implied speed in this module at once and every threshold assertion would
    keep passing against a different distance than the one it names.
    """
    assert 29.9 < great_circle_km(_NEAR, _FAR) < 30.1


# ---------------------------------------------------------------------------
# The threshold, pinned as a literal
# ---------------------------------------------------------------------------


def test_the_default_ceiling_is_the_published_number() -> None:
    """A published constant needs a test that names it.

    Every finding quotes this number and docs/rules.md documents it, so it is
    part of the tool's output, not an implementation detail. A property test
    over "fast pairs are flagged" cannot notice it moving.
    """
    assert DEFAULT_MAX_IMPLIED_SPEED_KPH == 120.0


def test_a_pair_just_under_the_ceiling_is_not_flagged(tmp_path) -> None:
    # 30.0 km in 16 minutes is 112.5 km/h.
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:16:00")
    assert _findings(tmp_path) == []


def test_a_pair_just_over_the_ceiling_is_flagged(tmp_path) -> None:
    # 30.0 km in 14 minutes is 128.6 km/h.
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:14:00")
    assert len(_findings(tmp_path)) == 1


def test_the_configured_ceiling_is_what_is_applied(tmp_path) -> None:
    """The ceiling is honoured, not merely accepted and ignored."""
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:16:00")  # 112.5 km/h
    assert _findings(tmp_path) == []
    assert len(_findings(tmp_path, max_implied_speed_kph=100.0)) == 1


def test_every_finding_quotes_the_ceiling_in_force(tmp_path) -> None:
    """The assumption travels with the finding, at whatever value it holds."""
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:05:00")
    (finding,) = _findings(tmp_path, max_implied_speed_kph=90.0)
    assert "90 km/h" in finding.message
    assert "straight-line" in finding.message


# ---------------------------------------------------------------------------
# The case TODS-W409 cannot see -- the reason this rule exists
# ---------------------------------------------------------------------------


def test_a_declared_deadhead_that_cannot_be_driven_is_flagged(tmp_path) -> None:
    """The motivating case, and the one a between-events-only check misses.

    Every consecutive pair here connects, so TODS-W409 is satisfied. The
    impossible movement is declared *inside* event 20: thirty kilometres in
    five minutes.
    """
    _write(
        tmp_path,
        "daily,1,10,Operator,near,13:00:00,near,14:00:00\n"
        "daily,1,20,Deadhead,near,14:00:00,far,14:05:00\n"
        "daily,1,30,Operator,far,14:05:00,far,15:00:00",
    )
    _, findings, _ = run_with_coverage(tmp_path, enabled=_ENABLED)
    assert "TODS-W409" not in rule_ids(findings), (
        "the fixture no longer demonstrates the gap: W409 now fires on it too"
    )
    (finding,) = [f for f in findings if f.rule_id == "OPS-W001"]
    assert "within event_sequence 20" in finding.message
    assert "360 km/h" in finding.message


def test_an_impossible_gap_between_two_events_is_flagged(tmp_path) -> None:
    _write(
        tmp_path,
        "daily,1,10,Operator,near,13:00:00,near,14:00:00\n"
        "daily,1,20,Operator,far,14:05:00,far,15:00:00",
    )
    messages = [f.message for f in _findings(tmp_path)]
    assert any("gap between event_sequence 10" in m for m in messages), messages


def test_a_workable_run_is_silent(tmp_path) -> None:
    _write(
        tmp_path,
        "daily,1,10,Operator,near,13:00:00,near,14:00:00\n"
        "daily,1,20,Deadhead,near,14:00:00,far,15:00:00\n"
        "daily,1,30,Operator,far,15:00:00,far,16:00:00",
    )
    assert _findings(tmp_path) == []


# ---------------------------------------------------------------------------
# Absence must not be rendered as a pass
# ---------------------------------------------------------------------------


def test_an_endpoint_with_no_coordinate_is_unmeasurable_not_feasible(tmp_path) -> None:
    """'garage' is a real location in real feeds and is not a GTFS stop."""
    _write(tmp_path, "daily,1,10,Deadhead,garage,08:00:00,far,08:01:00")
    assert _findings(tmp_path) == []
    measurement = _measurement(tmp_path)
    assert measurement is not None
    assert measurement.measured == 0
    assert measurement.unmeasurable == 1
    assert measurement.reason


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        ("", ""),  # blank
        ("not-a-number", "-118.25"),  # malformed
        ("91.0", "-118.25"),  # latitude out of range
        ("34.05", "181.0"),  # longitude out of range
        ("nan", "-118.25"),  # float() accepts this; every comparison is False
        ("inf", "-118.25"),
    ],
)
def test_an_unusable_coordinate_is_unmeasurable_never_null_island(
    tmp_path, lat: str, lon: str
) -> None:
    """The failure this guards is a blank coerced to 0.0.

    (0, 0) is a real point in the Gulf of Guinea. A blank latitude read as
    zero does not crash: it yields a distance of several thousand kilometres,
    which would be reported as a confident finding about the operator rather
    than a gap in the feed. A NaN is the mirror image -- every comparison
    against it is False, so the pair would silently pass.
    """
    _write(
        tmp_path,
        "daily,1,10,Deadhead,near,08:00:00,far,08:01:00",
        stops=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            f"near,Near,{_NEAR[0]:.6f},{_NEAR[1]:.6f}\n"
            f"far,Far,{lat},{lon}\n"
        ),
    )
    assert _findings(tmp_path) == []
    measurement = _measurement(tmp_path)
    assert measurement is not None
    assert measurement.unmeasurable == 1


def test_a_stop_deleted_by_a_supplement_becomes_unmeasurable(tmp_path) -> None:
    """ADR 0007's posture: a companion that lost a row answers with less."""
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:01:00")
    (tmp_path / "stops_supplement.txt").write_text("stop_id,TODS_delete\nfar,1\n", encoding="utf-8")
    assert _findings(tmp_path) == []
    measurement = _measurement(tmp_path)
    assert measurement is not None
    assert measurement.unmeasurable == 1


def test_with_no_companion_gtfs_the_rule_is_skipped_not_passed(tmp_path) -> None:
    (tmp_path / "run_events.txt").write_text(
        f"{_HEADER}\ndaily,1,10,Deadhead,near,08:00:00,far,08:01:00\n", encoding="utf-8"
    )
    _, _, coverage = run_with_coverage(tmp_path, enabled=_ENABLED)
    (outcome,) = [o for o in coverage.outcomes if o.id == "OPS-W001"]
    assert not outcome.ran
    assert outcome.status == "skipped:needs_gtfs"
    assert outcome.measurement is None


def test_zero_time_for_a_real_distance_is_flagged_not_divided_by_zero(tmp_path) -> None:
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:00:00")
    (finding,) = _findings(tmp_path)
    assert "no time at all" in finding.message


def test_a_negative_gap_does_not_pass_as_a_negative_speed(tmp_path) -> None:
    """An overlap must not read as 'below the ceiling'.

    Dividing a positive distance by a negative duration yields a negative
    implied speed, and `-360 <= 120` is True, so the naive form of this check
    reports the single most broken shape in the file as fine.
    """
    _write(
        tmp_path,
        "daily,1,10,Operator,near,14:00:00,near,15:00:00\n"
        "daily,1,20,Operator,far,14:30:00,far,16:00:00",
    )
    assert all("gap between" not in f.message for f in _findings(tmp_path))


# ---------------------------------------------------------------------------
# Disclosure
# ---------------------------------------------------------------------------


def test_a_partial_measurement_is_disclosed_in_the_manifest(tmp_path) -> None:
    _write(
        tmp_path,
        "daily,1,10,Deadhead,garage,08:00:00,far,08:30:00\n"
        "daily,1,20,Operator,far,08:30:00,far,09:00:00",
    )
    _, _, coverage = run_with_coverage(tmp_path, enabled=_ENABLED)
    (line,) = coverage.measurement_lines()
    assert "OPS-W001" in line
    assert "unmeasurable" in line


def test_a_complete_measurement_adds_no_noise(tmp_path) -> None:
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,09:00:00")
    _, _, coverage = run_with_coverage(tmp_path, enabled=_ENABLED)
    assert coverage.measurement_lines() == []


def test_the_text_report_carries_the_partial_measurement(tmp_path) -> None:
    """The manifest is only worth keeping if a reader of the report sees it."""
    from tods_validate.report import render_text

    _write(tmp_path, "daily,1,10,Deadhead,garage,08:00:00,far,08:30:00")
    _, findings, coverage = run_with_coverage(tmp_path, enabled=_ENABLED)
    text = render_text(findings, str(tmp_path), coverage=coverage)
    assert "unmeasurable" in text


def test_the_valid_feed_reports_what_it_could_not_measure() -> None:
    """A clean run over the project's own valid feed is still a partial one.

    Its run events start and end at 'garage', which is not a GTFS stop, so six
    of its twenty movements have no coordinate. Nothing here is wrong with the
    feed; the point is that a report saying "no problems found" also says how
    much of this check it was able to apply.
    """
    _, findings, coverage = run_with_coverage(VALID_TODS, VALID_GTFS, enabled=_ENABLED)
    assert "OPS-W001" not in rule_ids(findings)
    (outcome,) = [o for o in coverage.outcomes if o.id == "OPS-W001"]
    assert outcome.measurement is not None
    assert outcome.measurement.unmeasurable > 0
    assert outcome.measurement.measured > 0


# ---------------------------------------------------------------------------
# The rule stays opt-in
# ---------------------------------------------------------------------------


def test_the_rule_is_silent_unless_enabled(tmp_path) -> None:
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:01:00")
    _, findings = run(tmp_path)
    assert "OPS-W001" not in rule_ids(findings)


def test_enabling_by_rule_id_works(tmp_path) -> None:
    _write(tmp_path, "daily,1,10,Deadhead,near,08:00:00,far,08:01:00")
    _, findings = run(tmp_path, enabled=frozenset({"OPS-W001"}))
    assert "OPS-W001" in rule_ids(findings)


def test_strict_and_ingest_ready_profiles_are_unchanged_by_this_rule() -> None:
    """Adding a category must not silently widen an existing profile."""
    from tods_validate.config import PROFILES

    for name in ("strict", "ingest-ready"):
        assert "feasibility" not in PROFILES[name]["enable"], name


# ---------------------------------------------------------------------------
# Measurement's own contract
# ---------------------------------------------------------------------------


def test_an_undisclosed_gap_is_rejected() -> None:
    with pytest.raises(ValueError, match="must say why"):
        Measurement(measured=1, unmeasurable=1, unit="movement")


def test_a_complete_measurement_needs_no_reason() -> None:
    assert Measurement(measured=3, unmeasurable=0, unit="movement").summary() == (
        "3 movements measured."
    )


def test_unmeasurable_is_never_folded_into_measured() -> None:
    m = Measurement(measured=14, unmeasurable=6, unit="movement", reason="no coordinates")
    assert m.total == 20
    assert "14 of 20" in m.summary()
    assert "6 unmeasurable" in m.summary()
