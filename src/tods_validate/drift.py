"""GTFS-drift analysis: which TODS-referenced GTFS IDs broke between two GTFS versions.

Implements EXP-02 from ``docs/ideation/03-expansions.md``: the recurring
real-world failure the research roadmap's R8 only gives a static hint for
("your GTFS moved under your TODS") gets an actual diagnosis here — given a
TODS package and two versions of its companion GTFS feed, report exactly
which referenced ``trip_id``/``stop_id`` values disappeared and which
``block_id`` a trip moved to, with conservative rename candidates.

Only ``run_events.txt`` is inspected for references today (it is the file
the spec's own worked example and the existing W302/W313/E307/E309 rules
center on, and the file R8's hint targets); this is deliberately the same
scope those rules cover, not a claim that no other file holds GTFS
references.

Rename inference never auto-applies. A candidate is only proposed when
exactly one GTFS ID that is new in the second feed is a close (but not
identical) match to the broken value, per :func:`difflib.get_close_matches`
at a conservative cutoff -- consistent with the "review-grade, not applied"
posture of ``suggest.py``.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .gtfs_companion import CompanionGTFS, build_companion
from .loader import Package

_RENAME_CUTOFF = 0.8

# The run_events.txt fields that hold GTFS references we can diagnose here.
_LOCATION_FIELDS = ("start_location", "end_location")


@dataclass(frozen=True)
class ReferenceBreak:
    """A GTFS ID that TODS references, present in OLD, missing from NEW."""

    kind: str  # "trip_id" | "stop_id"
    value: str
    used_by: tuple[str, ...]  # e.g. "run_events.txt:14"
    candidates: tuple[str, ...] = ()  # unique, conservative rename guesses


@dataclass(frozen=True)
class BlockChange:
    """A trip TODS references whose block_id differs between OLD and NEW."""

    trip_id: str
    old_block: str
    new_block: str
    used_by: tuple[str, ...]


@dataclass(frozen=True)
class DriftReport:
    old_source: str
    new_source: str
    broken_trip_ids: tuple[ReferenceBreak, ...] = ()
    broken_stop_ids: tuple[ReferenceBreak, ...] = ()
    changed_blocks: tuple[BlockChange, ...] = ()

    @property
    def has_breaks(self) -> bool:
        return bool(self.broken_trip_ids or self.broken_stop_ids or self.changed_blocks)


def _rename_candidates(value: str, available: set[str]) -> tuple[str, ...]:
    """A single close-but-not-identical match, or none.

    Deliberately conservative: more than one plausible match is not a
    rename, it is ambiguity, and this never guesses under ambiguity.
    """
    matches = difflib.get_close_matches(value, sorted(available), n=2, cutoff=_RENAME_CUTOFF)
    matches = [m for m in matches if m != value]
    if len(matches) == 1:
        return (matches[0],)
    return ()


@dataclass
class _References:
    trip_uses: dict[str, list[str]] = field(default_factory=dict)
    location_uses: dict[str, list[str]] = field(default_factory=dict)


def _collect_references(tods: Package) -> _References:
    refs = _References()
    run_events = tods.get("run_events.txt")
    if run_events is None:
        return refs
    for row in run_events.rows:
        trip_id = row.values.get("trip_id", "")
        if trip_id:
            refs.trip_uses.setdefault(trip_id, []).append(f"run_events.txt:{row.line}")
        for field_name in _LOCATION_FIELDS:
            location = row.values.get(field_name, "")
            if location:
                refs.location_uses.setdefault(location, []).append(
                    f"run_events.txt:{row.line} ({field_name})"
                )
    return refs


def _broken_trip_ids(
    refs: _References, old: CompanionGTFS, new: CompanionGTFS
) -> tuple[ReferenceBreak, ...]:
    new_only_trips = set(new.trip_service) - set(old.trip_service)
    breaks = []
    for trip_id in sorted(refs.trip_uses):
        if trip_id in old.trip_service and trip_id not in new.trip_service:
            breaks.append(
                ReferenceBreak(
                    kind="trip_id",
                    value=trip_id,
                    used_by=tuple(refs.trip_uses[trip_id]),
                    candidates=_rename_candidates(trip_id, new_only_trips),
                )
            )
    return tuple(breaks)


def _broken_stop_ids(
    refs: _References, old: CompanionGTFS, new: CompanionGTFS
) -> tuple[ReferenceBreak, ...]:
    new_only_stops = new.stop_ids - old.stop_ids
    breaks = []
    for stop_id in sorted(refs.location_uses):
        if stop_id in old.stop_ids and stop_id not in new.stop_ids:
            breaks.append(
                ReferenceBreak(
                    kind="stop_id",
                    value=stop_id,
                    used_by=tuple(refs.location_uses[stop_id]),
                    candidates=_rename_candidates(stop_id, new_only_stops),
                )
            )
    return tuple(breaks)


def _changed_blocks(
    refs: _References, old: CompanionGTFS, new: CompanionGTFS
) -> tuple[BlockChange, ...]:
    changes = []
    for trip_id in sorted(refs.trip_uses):
        old_block = old.trip_block.get(trip_id)
        new_block = new.trip_block.get(trip_id)
        if old_block is None or new_block is None:
            continue  # the trip itself is missing in one version; that is a broken_trip_ids finding
        if old_block != new_block:
            changes.append(
                BlockChange(
                    trip_id=trip_id,
                    old_block=old_block,
                    new_block=new_block,
                    used_by=tuple(refs.trip_uses[trip_id]),
                )
            )
    return tuple(changes)


def analyze_drift(old_gtfs: Package, new_gtfs: Package, tods: Package) -> DriftReport:
    """Diagnose which of ``tods``'s GTFS references break moving OLD -> NEW.

    Supplements from ``tods`` are applied to both GTFS versions before
    comparing (the same "TODS-Supplemented GTFS" resolution the validator's
    reference rules use), so a break reported here is a break a real
    ``validate`` run against NEW would also surface -- this only adds the
    diagnosis of *why*.
    """
    old = build_companion(old_gtfs, tods, source=old_gtfs.source)
    new = build_companion(new_gtfs, tods, source=new_gtfs.source)
    refs = _collect_references(tods)
    return DriftReport(
        old_source=old_gtfs.source,
        new_source=new_gtfs.source,
        broken_trip_ids=_broken_trip_ids(refs, old, new),
        broken_stop_ids=_broken_stop_ids(refs, old, new),
        changed_blocks=_changed_blocks(refs, old, new),
    )


def _render_break_lines(label: str, breaks: tuple[ReferenceBreak, ...]) -> list[str]:
    lines = [f"{label}: {len(breaks)}"]
    for b in breaks:
        used_by = ", ".join(b.used_by[:3])
        if len(b.used_by) > 3:
            used_by += f", +{len(b.used_by) - 3} more"
        line = f"  {b.value!r} (used by {used_by})"
        if b.candidates:
            line += f" -- possible rename: {b.candidates[0]!r}?"
        lines.append(line)
    return lines


def render_drift_text(report: DriftReport) -> str:
    lines = [f"tods-validate drift: {report.old_source} -> {report.new_source}", ""]
    if not report.has_breaks:
        lines.append("No referenced trip_id/stop_id broke; no block_id changes found.")
        return "\n".join(lines)
    lines += _render_break_lines("broken trip_id references", report.broken_trip_ids)
    lines.append("")
    lines += _render_break_lines(
        "broken stop_id references (start/end location)", report.broken_stop_ids
    )
    lines.append("")
    lines.append(f"trips whose block_id changed: {len(report.changed_blocks)}")
    for c in report.changed_blocks:
        used_by = ", ".join(c.used_by[:3])
        if len(c.used_by) > 3:
            used_by += f", +{len(c.used_by) - 3} more"
        lines.append(
            f"  trip_id {c.trip_id!r}: block {c.old_block!r} -> {c.new_block!r} (used by {used_by})"
        )
    return "\n".join(lines)


def render_drift_markdown(report: DriftReport) -> str:
    lines = [f"# GTFS drift: `{report.old_source}` -> `{report.new_source}`", ""]
    if not report.has_breaks:
        lines.append("No referenced `trip_id`/`stop_id` broke; no `block_id` changes found.")
        return "\n".join(lines)

    if report.broken_trip_ids:
        lines += [
            "## Broken `trip_id` references",
            "",
            "| trip_id | used by | possible rename |",
            "| --- | --- | --- |",
        ]
        for b in report.broken_trip_ids:
            used_by = "; ".join(b.used_by)
            rename = f"`{b.candidates[0]}`?" if b.candidates else "--"
            lines.append(f"| `{b.value}` | {used_by} | {rename} |")
        lines.append("")

    if report.broken_stop_ids:
        lines += [
            "## Broken `stop_id` references (start/end location)",
            "",
            "| stop_id | used by | possible rename |",
            "| --- | --- | --- |",
        ]
        for b in report.broken_stop_ids:
            used_by = "; ".join(b.used_by)
            rename = f"`{b.candidates[0]}`?" if b.candidates else "--"
            lines.append(f"| `{b.value}` | {used_by} | {rename} |")
        lines.append("")

    if report.changed_blocks:
        lines += [
            "## Trips whose `block_id` changed",
            "",
            "| trip_id | old block | new block | used by |",
            "| --- | --- | --- | --- |",
        ]
        for c in report.changed_blocks:
            used_by = "; ".join(c.used_by)
            lines.append(f"| `{c.trip_id}` | `{c.old_block}` | `{c.new_block}` | {used_by} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def drift_to_dict(report: DriftReport) -> dict[str, object]:
    return {
        "oldSource": report.old_source,
        "newSource": report.new_source,
        "brokenTripIds": [
            {"value": b.value, "usedBy": list(b.used_by), "candidates": list(b.candidates)}
            for b in report.broken_trip_ids
        ],
        "brokenStopIds": [
            {"value": b.value, "usedBy": list(b.used_by), "candidates": list(b.candidates)}
            for b in report.broken_stop_ids
        ],
        "changedBlocks": [
            {
                "tripId": c.trip_id,
                "oldBlock": c.old_block,
                "newBlock": c.new_block,
                "usedBy": list(c.used_by),
            }
            for c in report.changed_blocks
        ],
    }
