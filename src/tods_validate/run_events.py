"""Parsing for run_events.txt, shared across rules via ValidationContext.

This is deliberately *not* part of the ``rules`` package: ``ValidationContext``
(in ``rules/__init__.py``) needs it to build its cached derived views, and a
rule module (``rules/semantics.py``) used to own this parsing, which would
make ``rules.__init__`` -> ``run_events`` -> ``rules.fields`` -> ``rules``
a circular import. Living outside ``rules/`` also keeps this parsing loop out
of mutmut's mutated set (``[tool.mutmut] only_mutate = ["src/tods_validate/
rules/*"]``): it is exercised indirectly by every rule that reads run events,
so a mutant here would be *over*-killed rather than pointing at a specific
rule's test gap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .loader import Package, Row

# GTFS Time: H:MM:SS or HH:MM:SS; hours may exceed 24 for service past midnight
# and have no upper bound in the spec, so the hour field is not width-capped.
# Kept as a private copy of tods_validate.rules.fields.parse_time (which
# re-exports this one) rather than imported from it, to avoid the circular
# import described above.
_TIME_RE = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")


def parse_time(value: str) -> int | None:
    """Return seconds since noon-minus-12h, or None if not a valid GTFS time."""
    m = _TIME_RE.match(value)
    if m is None:
        return None
    hours, minutes, seconds = (int(g) for g in m.groups())
    return hours * 3600 + minutes * 60 + seconds


@dataclass(frozen=True)
class _Event:
    row: Row
    service_id: str
    run_id: str
    sequence: int | None
    trip_id: str
    start: int | None  # seconds
    end: int | None
    start_location: str
    end_location: str

    @property
    def run(self) -> tuple[str, str]:
        return (self.service_id, self.run_id)


def parse_events(package: Package) -> list[_Event]:
    """Parse every row of run_events.txt into ``_Event`` objects, once."""
    feed = package.get("run_events.txt")
    if feed is None:
        return []
    events = []
    for row in feed.rows:
        sequence_raw = row.values.get("event_sequence", "")
        events.append(
            _Event(
                row=row,
                service_id=row.values.get("service_id", ""),
                run_id=row.values.get("run_id", ""),
                sequence=int(sequence_raw) if sequence_raw.isdigit() else None,
                trip_id=row.values.get("trip_id", ""),
                start=parse_time(row.values.get("start_time", "")),
                end=parse_time(row.values.get("end_time", "")),
                start_location=row.values.get("start_location", ""),
                end_location=row.values.get("end_location", ""),
            )
        )
    return events


def events_by_run(events: list[_Event]) -> dict[tuple[str, str], list[_Event]]:
    """Group events by (service_id, run_id), dropping events missing either."""
    runs: dict[tuple[str, str], list[_Event]] = {}
    for event in events:
        if event.service_id and event.run_id:
            runs.setdefault(event.run, []).append(event)
    return runs
