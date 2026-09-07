"""Operational feasibility checks (OPS-x0xx): can the pick actually be worked?

Every other rule in this package answers a question about the *file*: is this
value well-formed, does this ID resolve, do these rows agree. This module asks
the one question a run-cutter asks about a delivered pick -- can a person
actually work it -- and that question is not answerable from the package
alone. It needs geography.

Why these are not ``TODS-`` rules
---------------------------------
``TODS-W409`` already carries this argument in its own description: "an
operator is one person who cannot teleport". But it compares two location
*identifiers* for equality, so it answers "do these two events name the same
place?", not "could a person get from the first place to the second in the
time given?". A pick in which an operator finishes downtown at 14:00, declares
a correct five-minute deadhead, and starts a run thirty kilometres away at
14:05 satisfies W409 and every other rule here, and is not something a human
being can do.

Closing that gap means asserting a travel-time model, and the TODS spec says
nothing about travel time. The project's promise is that a ``TODS-`` ID cites
the section of the spec it enforces, so encoding this judgement under a
``TODS-`` ID would spend that promise on an opinion. It gets its own
namespace, its own opt-in category, and its own band in the coverage manifest
instead. See ADR 0008.

What the check refuses to do
----------------------------
The failure mode this module is most exposed to is answering confidently
about a pair it cannot see. Two stops without coordinates are not "close
together"; a package with no companion GTFS has not been checked and found
fine. Every movement that cannot be resolved to two real positions is counted
as ``unmeasurable`` and reported as such through the coverage manifest, never
folded into the movements that passed. A run whose whole feed lacks coordinates
therefore reports "0 of 40 movements measured", not a clean result.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from ..findings import Finding, Severity
from ..run_events import _Event
from ..schema import SPEC_VERSION
from . import GTFS_STOPS, Measurement, ValidationContext, rule

# Mean Earth radius (km), IUGG. Great-circle distance over a sphere is the
# honest model here: it needs no road network, no projection and no network
# access, and it always understates the real driving distance, so it can only
# ever make a pair look *more* feasible than it is. A check that errs toward
# saying nothing is the right shape for one that is asserting a pick cannot be
# worked.
_EARTH_RADIUS_KM = 6371.0088

# This check reads v2.1.0's run_events.txt field names and the supplemented
# companion GTFS; see docs/spec-versions.md.
_V2_ONLY = (SPEC_VERSION,)

_UNIT = "movement"
_UNMEASURABLE_REASON = (
    "one or both endpoints have no usable stop_lat/stop_lon in the companion GTFS"
)


def great_circle_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (latitude, longitude) points.

    Uses the haversine form rather than the spherical law of cosines: the
    latter loses catastrophic precision at short distances, which is exactly
    the range this check spends most of its time in (two stops a few hundred
    metres apart). ``asin`` is clamped because floating-point error can push
    the argument marginally past 1.0 for antipodal points.
    """
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(min(1.0, h)))


def _ordered_events(events: list[_Event]) -> list[_Event]:
    return sorted((e for e in events if e.sequence is not None), key=lambda e: e.sequence or 0)


@dataclass(frozen=True)
class _Leg:
    """One movement a person has to make, and the time they have to make it."""

    origin_location: str
    destination_location: str
    seconds: int
    row: int
    reference_row: int
    field: str
    what: str


def _legs(ordered: list[_Event]) -> Iterator[_Leg]:
    """Every movement implied by a run, in event order.

    Two kinds, and the second is the one the motivating case needs.

    **Within one event.** A deadhead row that starts downtown at 14:00 and ends
    thirty kilometres away at 14:05 declares the movement *inside itself*. This
    is the exact pick the issue behind this rule describes, and a check that
    only looked between events would not see it: consecutive events connect
    perfectly, TODS-W409 is satisfied, and nothing is wrong except that no
    vehicle can do it. Skipping this would leave the rule unable to fire on its
    own motivating example.

    **Between two consecutive events.** The gap the run allows for getting from
    where one event ended to where the next begins. Where the two locations are
    identical this is a zero-distance leg and is dropped by the caller; where
    they differ, TODS-W409 also reports the discontinuity, and this adds
    whether the discontinuity is survivable.

    A leg is emitted only when both of its times parse. A missing or malformed
    time is already reported by TODS-E201/E203, and counting it here as well
    would republish one defect as a second, different-looking one.
    """
    for event in ordered:
        if event.start is not None and event.end is not None:
            yield _Leg(
                origin_location=event.start_location,
                destination_location=event.end_location,
                seconds=event.end - event.start,
                row=event.row.line,
                reference_row=event.row.line,
                field="end_location",
                what=f"the movement within event_sequence {event.sequence}",
            )
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.end is None or current.start is None:
            continue
        yield _Leg(
            origin_location=previous.end_location,
            destination_location=current.start_location,
            seconds=current.start - previous.end,
            row=current.row.line,
            reference_row=previous.row.line,
            field="start_location",
            what=(
                f"the gap between event_sequence {previous.sequence} "
                f"(row {previous.row.line}) and event_sequence {current.sequence}"
            ),
        )


@rule(
    spec_versions=_V2_ONLY,
    id="OPS-W001",
    severity=Severity.WARNING,
    title="A movement in this run is too far to be made in the time allowed",
    description=(
        "A movement the run requires -- either inside one event, or in the gap between two "
        "consecutive events -- covers more ground than the time allowed for it permits, so "
        "the implied travel speed exceeds the configured ceiling. Unlike TODS-W409, which "
        "compares location identifiers, this resolves both endpoints to coordinates in the "
        "companion GTFS and measures the distance. It encodes a judgement the TODS spec does "
        "not make, which is why it is opt-in and carries an OPS- rather than a TODS- ID."
    ),
    # Deliberately not a spec URL: this rule is not entailed by the spec, and
    # tests/test_registry.py enforces that only TODS- IDs cite one.
    spec_section="https://github.com/ChelseaKR/tods-validate/blob/main/docs/adr/0008-operational-feasibility-namespace.md",
    needs_gtfs=True,
    gtfs_tables=(GTFS_STOPS,),
    category="feasibility",
    default_enabled=False,
    interpretation=(
        "straight-line: distance is great-circle between stop coordinates, which understates "
        "road distance, so the implied speed reported is a lower bound on the speed actually "
        "required"
    ),
)
def pair_not_workable(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    coords = context.gtfs.stop_coords
    ceiling = context.max_implied_speed_kph
    measured = 0
    unmeasurable = 0

    for events in context.events_by_run.values():
        for leg in _legs(_ordered_events(events)):
            origin = coords.get(leg.origin_location)
            destination = coords.get(leg.destination_location)
            if origin is None or destination is None:
                unmeasurable += 1
                continue

            measured += 1
            distance_km = great_circle_km(origin, destination)
            if distance_km == 0.0:
                continue
            if leg.seconds < 0:
                # The leg ends before it begins. That is a time defect owned by
                # the semantics band (TODS-W40x); dividing by it here would
                # produce a negative speed, which compares as *below* the
                # ceiling and would silently pass.
                continue

            if leg.seconds == 0:
                implied = None
                speed_phrase = "no time at all is allowed for it"
            else:
                implied = distance_km / (leg.seconds / 3600.0)
                if implied <= ceiling:
                    continue
                speed_phrase = f"an implied {implied:,.0f} km/h"

            yield Finding(
                rule_id="OPS-W001",
                severity=Severity.WARNING,
                file="run_events.txt",
                row=leg.row,
                field=leg.field,
                message=(
                    f"run_events.txt row {leg.row}: {leg.what} covers "
                    f"{distance_km:,.1f} km, from {leg.origin_location!r} to "
                    f"{leg.destination_location!r}, in {leg.seconds / 60.0:,.0f} minute(s) "
                    f"-- {speed_phrase}. The ceiling in force is {ceiling:,.0f} km/h "
                    "(straight-line); distance is measured great-circle between the "
                    "companion GTFS stop coordinates and so understates the road distance."
                ),
                suggestion=(
                    "Check the running or deadhead time allowed for this movement, or "
                    "correct a location that points at the wrong stop. If the pick is right "
                    "and the ceiling is wrong for this agency, set 'max-implied-speed-kph' "
                    "in tods-validate.toml."
                ),
                data={
                    "value": leg.destination_location,
                    "expected": leg.origin_location,
                    "referenced": f"run_events.txt#L{leg.reference_row}",
                },
            )

    context.measurements["OPS-W001"] = Measurement(
        measured=measured,
        unmeasurable=unmeasurable,
        unit=_UNIT,
        reason=_UNMEASURABLE_REASON if unmeasurable else None,
    )
