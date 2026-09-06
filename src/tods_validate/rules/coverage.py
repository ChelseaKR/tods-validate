"""Opt-in coverage and advisory checks (TODS-x5xx, TODS-x6xx).

These do not check spec conformance; they surface judgement calls a scheduler
or analyst might want to know about. They are off by default (a clean feed can
legitimately trip them) and are enabled with ``--enable coverage`` /
``--enable advisory`` or by rule ID.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..findings import Finding, Severity
from ..schema import SPEC_URL, SPEC_VERSION
from . import GTFS_TRIPS, ValidationContext, rule

_BREAK_KEYWORDS = ("break", "lunch", "meal")
# A continuous on-duty span longer than this (seconds) with no break event is
# worth a second look. Conservative; real rules vary by labor agreement.
_LONG_SPAN_SECONDS = 6 * 3600
# These checks assume v2.1.0's run_events.txt/vehicle_assignments.txt field
# names and the companion-GTFS coverage they describe; see docs/spec-versions.md.
_V2_ONLY = (SPEC_VERSION,)


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-I501",
    severity=Severity.INFO,
    title="GTFS trips have no run event",
    description=(
        "Some trips in the companion GTFS feed are never referenced by a run event, so "
        "no crew work is described for them. This is informational: not every trip must "
        "appear in run_events.txt, but wide gaps can mean an incomplete export."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_TRIPS,),
    category="coverage",
    default_enabled=False,
)
def trips_without_run_events(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    covered = {event.trip_id for event in context.events}
    covered.discard("")
    all_trips = set(context.gtfs.trip_service)
    uncovered = sorted(all_trips - covered)
    if uncovered and all_trips:
        sample = ", ".join(uncovered[:5])
        more = f", and {len(uncovered) - 5} more" if len(uncovered) > 5 else ""
        yield Finding(
            rule_id="TODS-I501",
            severity=Severity.INFO,
            file="run_events.txt",
            message=(
                f"{len(uncovered)} of {len(all_trips)} GTFS trip(s) are not referenced by "
                f"any run event (e.g. {sample}{more}). No crew work is described for them."
            ),
            data={"value": sample, "field": "trip_id"},
        )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-I502",
    severity=Severity.INFO,
    title="Blocks have no vehicle assignment",
    description=(
        "Some blocks in the companion GTFS feed have no row in vehicle_assignments.txt, "
        "so no vehicle is assigned to operate them. Informational: vehicle assignments "
        "are optional, but unassigned blocks may signal an incomplete export."
    ),
    spec_section=f"{SPEC_URL}#vehicle_assignmentstxt",
    needs_gtfs=True,
    gtfs_tables=(GTFS_TRIPS,),
    category="coverage",
    default_enabled=False,
)
def blocks_without_vehicle(context: ValidationContext) -> Iterator[Finding]:
    assert context.gtfs is not None
    feed = context.package.get("vehicle_assignments.txt")
    assigned = {row.values.get("block_id", "") for row in feed.rows} if feed else set()
    assigned.discard("")
    all_blocks = set(context.gtfs.block_ids)
    unassigned = sorted(all_blocks - assigned)
    if unassigned and all_blocks:
        sample = ", ".join(unassigned[:5])
        more = f", and {len(unassigned) - 5} more" if len(unassigned) > 5 else ""
        yield Finding(
            rule_id="TODS-I502",
            severity=Severity.INFO,
            file="vehicle_assignments.txt",
            message=(
                f"{len(unassigned)} of {len(all_blocks)} block(s) have no vehicle "
                f"assignment (e.g. {sample}{more})."
            ),
            data={"value": sample, "field": "block_id"},
        )


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-I601",
    severity=Severity.INFO,
    title="Run has a long span with no break event",
    description=(
        "A run is on duty for a long continuous span with no event whose type names a "
        "break, lunch, or meal. Advisory only: break modelling varies by agency and "
        "labor agreement, so this is never an error."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    category="advisory",
    default_enabled=False,
    interpretation="advisory: 'break' detected by event_type containing break/lunch/meal",
)
def long_run_without_break(context: ValidationContext) -> Iterator[Finding]:
    for (service_id, run_id), events in context.events_by_run.items():
        times = [(e.start, e.end) for e in events if e.start is not None and e.end is not None]
        if not times:
            continue
        span = max(e for _s, e in times) - min(s for s, _e in times)
        has_break = any(
            any(k in event.row.values.get("event_type", "").lower() for k in _BREAK_KEYWORDS)
            for event in events
        )
        if span > _LONG_SPAN_SECONDS and not has_break:
            first_row = min(event.row.line for event in events)
            yield Finding(
                rule_id="TODS-I601",
                severity=Severity.INFO,
                file="run_events.txt",
                row=first_row,
                message=(
                    f"run (service_id {service_id!r}, run_id {run_id!r}) spans "
                    f"{span // 3600}h{(span % 3600) // 60:02d}m with no break, lunch, or "
                    "meal event. Check whether a break belongs in the run."
                ),
                data={"value": f"{service_id},{run_id}"},
            )


# The two run_events.txt fields the spec leaves as free text: "Producers may use
# any values, but should be consistent" (spec, run_events.txt, `event_type` and
# `job_type`). Two spellings of one value are the same value written differently,
# and TODS-I602 groups them by case-folding and dropping the three separators the
# spec's own examples use between words ("Report Time", "Sign-in", "Pre_Trip").
_FREE_TEXT_FIELDS = ("event_type", "job_type")
_SEPARATORS = str.maketrans({"-": "", "_": "", " ": ""})


def _spelling_key(value: str) -> str:
    """The group a free-text value belongs to, or "" for values with no letters.

    A value that normalizes to the empty string ("-", "__", a blank cell) carries
    no name to be inconsistent about, and grouping those together would report
    absence as a disagreement. They are dropped instead.
    """
    return value.casefold().translate(_SEPARATORS)


@rule(
    spec_versions=_V2_ONLY,
    id="TODS-I602",
    severity=Severity.INFO,
    title="One value is spelled more than one way",
    description=(
        "run_events.txt writes the same event_type or job_type two or more ways, "
        "differing only in capitalization or in the separator between words. The spec "
        "lets a producer use any values but asks for them to be consistent, and a "
        "consumer that matches on the literal value reads the spellings as unrelated "
        "types. Advisory only: two spellings can be two genuinely different values."
    ),
    spec_section=f"{SPEC_URL}#run_eventstxt",
    category="advisory",
    default_enabled=False,
    interpretation=(
        "advisory: two values count as one value spelled differently when they match "
        "after case-folding and removing spaces, hyphens, and underscores"
    ),
)
def inconsistent_free_text_spelling(context: ValidationContext) -> Iterator[Finding]:
    feed = context.package.get("run_events.txt")
    if feed is None:
        return
    for field_name in _FREE_TEXT_FIELDS:
        # key -> spelling -> line numbers. Both dicts keep insertion order, so
        # "the spelling that appears first in the file" is well defined below.
        groups: dict[str, dict[str, list[int]]] = {}
        for row in feed.rows:
            # Stripped before grouping so that padding alone is not a second
            # spelling: leading and trailing spaces are TODS-W206's finding,
            # and reporting them here as well would double-count one mistake.
            value = row.values.get(field_name, "").strip()
            key = _spelling_key(value)
            if not key:
                continue
            groups.setdefault(key, {}).setdefault(value, []).append(row.line)
        for spellings in groups.values():
            if len(spellings) < 2:
                continue
            # Most-used spelling first: it is the one a producer most likely
            # meant to use throughout. Ties break on first appearance, so the
            # order does not depend on dict iteration luck.
            order = sorted(spellings, key=lambda s: (-len(spellings[s]), spellings[s][0]))
            listing = "; ".join(
                f"{spelling!r} ({len(spellings[spelling])} row(s))" for spelling in order
            )
            # The row where the disagreement becomes visible: the first row
            # carrying a spelling other than the file's first one.
            first_seen = next(iter(spellings))
            row_line = min(
                lines[0] for spelling, lines in spellings.items() if spelling != first_seen
            )
            yield Finding(
                rule_id="TODS-I602",
                severity=Severity.INFO,
                file="run_events.txt",
                row=row_line,
                field=field_name,
                message=(
                    f"{field_name} is spelled {len(spellings)} ways for what looks like "
                    f"one value: {listing}. Pick one spelling and use it throughout, or "
                    "confirm these really are different types."
                ),
                data={"value": ", ".join(sorted(spellings)), "field": field_name},
            )
