"""Rule registry.

Rules are data plus a small check function, not a plugin framework. Each rule
has a stable ID, a severity, a spec citation, and a check that yields
findings. IDs keep the historical TODS- prefix and are grouped in bands:

- TODS-x1xx: package and file structure
- TODS-x2xx: field values within one file
- TODS-x3xx: references between files (including the companion GTFS feed)
- TODS-x4xx: semantic checks across rows

The letter encodes severity (E error, W warning, I info). IDs are never
reused or renumbered once released.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Iterator
from dataclasses import dataclass, field, replace
from functools import cached_property

from .. import run_events
from ..findings import Finding, Severity
from ..gtfs_companion import CompanionGTFS
from ..loader import Package
from ..schema import GTFS_PRIMARY_KEYS, SPEC_VERSION, TableSpec, tables_for_version


@dataclass
class ValidationContext:
    package: Package
    gtfs: CompanionGTFS | None = None
    # "flag" if --gtfs was passed, "package" if GTFS files were found next to
    # the TODS files, None if no companion GTFS is available.
    gtfs_source: str | None = None
    # Which TODS spec version to validate against (schema.SUPPORTED_SPEC_VERSIONS).
    spec_version: str = SPEC_VERSION

    @property
    def tables(self) -> dict[str, TableSpec]:
        """The file/field inventory for this context's spec_version.

        Structure and field-value rules (TODS-x1xx, TODS-x2xx) read this
        instead of importing schema.TABLES directly, so the same rule logic
        validates whichever spec version was requested. See
        docs/spec-versions.md.
        """
        return tables_for_version(self.spec_version)

    # Derived views over run_events.txt, computed once per validation and
    # cached on this instance (it is created once per validate() call and
    # shared by every rule; see runner.run()). Parsing lives in
    # tods_validate.run_events, not here, so it stays outside mutmut's
    # rules/*-scoped mutated set — see that module's docstring.
    @cached_property
    def events(self) -> list[run_events._Event]:
        return run_events.parse_events(self.package)

    @cached_property
    def events_by_run(self) -> dict[tuple[str, str], list[run_events._Event]]:
        return run_events.events_by_run(self.events)

    @cached_property
    def run_pairs(self) -> set[tuple[str, str]]:
        return set(self.events_by_run.keys())


CheckFunction = Callable[[ValidationContext], Iterator[Finding]]


# Requirement groups for Rule.gtfs_tables, named once here so every rule module
# spells them the same way. Each is one group of alternatives: GTFS lets a feed
# define services in calendar.txt, calendar_dates.txt, or both, so either file
# satisfies GTFS_CALENDARS.
GTFS_TRIPS = ("trips.txt",)
GTFS_STOPS = ("stops.txt",)
GTFS_ROUTES = ("routes.txt",)
GTFS_STOP_TIMES = ("stop_times.txt",)
GTFS_CALENDARS = ("calendar.txt", "calendar_dates.txt")


# Categories group rules by how aggressively they fire. "core" rules check the
# spec and run by default. "coverage" and "advisory" rules are opt-in (see
# default_enabled) because they surface judgement calls, not spec violations,
# and would be noise in a default CI gate.
CATEGORIES = ("core", "coverage", "advisory", "experimental")


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    title: str
    # One- or two-sentence description for the rule catalog, written for feed
    # producers.
    description: str
    spec_section: str
    check: CheckFunction = field(compare=False)
    # Rules that resolve IDs into the companion GTFS feed are skipped when no
    # companion feed is available.
    needs_gtfs: bool = False
    # Which GTFS files this rule actually reads out of the companion feed.
    # Each inner tuple is a set of alternatives, and every group must be
    # satisfied: (("trips.txt",), ("stop_times.txt",)) needs both files, while
    # (("calendar.txt", "calendar_dates.txt"),) needs either one. A rule whose
    # requirement the companion feed cannot meet is skipped rather than run:
    # "the check function was invoked" is not the same claim as "the check had
    # anything to check", and only the second one earns a clean result. Every
    # needs_gtfs rule must declare this (enforced in rule()).
    gtfs_tables: tuple[tuple[str, ...], ...] = ()
    # See CATEGORIES.
    category: str = "core"
    # Opt-in rules (default_enabled=False) run only when their ID or category
    # is passed to validate()/--enable.
    default_enabled: bool = True
    # Where the spec is ambiguous, how this rule resolves it (e.g. "permissive:
    # accepts GTFS times beyond 24:00:00"). Surfaced in `rules --format json`
    # so consumers can audit interpretation choices. None when unambiguous.
    interpretation: str | None = None
    # A short "Before: ... / After: ..." worked fix example, written for feed
    # producers. Set on the highest-frequency rules; None elsewhere.
    example: str | None = None
    # Which --spec-version(s) this rule applies to. None (the default) means
    # every version in schema.SUPPORTED_SPEC_VERSIONS: true for every rule
    # written generically over ValidationContext.tables (TODS-x1xx, TODS-x2xx).
    # Rules that assume the v2.1.0-only Supplement/GTFS-merge mechanism, or
    # v2.1.0's specific run_events.txt/vehicle_assignments.txt field names
    # (TODS-x3xx, TODS-x4xx, coverage, advisory), set this explicitly. See
    # docs/spec-versions.md.
    spec_versions: tuple[str, ...] | None = None


@dataclass(frozen=True)
class RuleExample:
    """A minimal worked example for one rule: a line (or a few) that trips it,
    the same content fixed, and a short note connecting the two.

    Kept in :data:`EXAMPLES` below rather than on :class:`Rule` itself so one
    module stays the single source every renderer reads from: `explain`,
    ``hover_markdown``, and ``scripts/generate_rules_doc.py`` (docs/rules.md)
    all call :func:`render_rule_detail` / :func:`example_for`, so they cannot
    drift from each other.
    """

    file: str
    before: str
    after: str
    note: str = ""


# Worked examples, keyed by rule ID. Populated for every core-category rule
# first (core rules run by default, so they are what most users hit), then
# the opt-in coverage/advisory rules. See RuleExample for the rendering
# contract; see tests/fixtures/invalid/<rule id>/ for the fixtures these are
# distilled from.
EXAMPLES: dict[str, RuleExample] = {
    "TODS-W101": RuleExample(
        file="(package root)",
        before="agency.txt\nnotes.txt",
        after="agency.txt\nnotes.txt\nrun_events.txt\nvehicles.txt",
        note="Every TODS file is optional, but the package needs at least one to validate.",
    ),
    "TODS-I102": RuleExample(
        file="notes.txt",
        before="note\nremember to update this feed",
        after="(remove notes.txt, or rename it to a filename TODS or GTFS defines)",
        note=(
            "Not an error: the file is simply skipped. Fix the name if it was meant to be a TODS "
            "file."
        ),
    ),
    "TODS-E103": RuleExample(
        file="vehicles.txt",
        before="(empty file)",
        after="vehicle_id,vehicle_label\nbus-1,Old Reliable",
        note=(
            "An empty, non-UTF-8, or unparseable file cannot be read at all; write at least a "
            "header row in UTF-8."
        ),
    ),
    "TODS-E104": RuleExample(
        file="vehicles.txt",
        before="vehicle_id,vehicle_label\nbus-1,Old Reliable,extra-value",
        after="vehicle_id,vehicle_label\nbus-1,Old Reliable",
        note=(
            "The row has three values but the header declares two columns; drop the stray trailing "
            "value."
        ),
    ),
    "TODS-E105": RuleExample(
        file="vehicles.txt",
        before="vehicle_id,vehicle_id\nbus-1,bus-1",
        after="vehicle_id,vehicle_label\nbus-1,Old Reliable",
        note="Rename the duplicated header so every column name in the file is unique.",
    ),
    "TODS-E106": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,start_location,start_time,end_location,end_time\n"
            "daily,1,1,garage,08:00:00,garage,08:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,08:00:00,garage,08:00:00"
        ),
        note="event_type is Required; add the missing column.",
    ),
    "TODS-W107": RuleExample(
        file="vehicles.txt",
        before="vehicle_id,vehicle_nickname\nbus-1,Buster",
        after="vehicle_id,vehicle_label\nbus-1,Buster",
        note=(
            "vehicle_nickname is not a defined TODS field and consumers will ignore it; rename it "
            "to the field you meant (here, vehicle_label) or drop it."
        ),
    ),
    "TODS-I108": RuleExample(
        file="stops_supplement.txt",
        before="stop_id,my_custom_note\ngarage,internal only",
        after="stop_id,TODS_my_custom_note\ngarage,internal only",
        note=(
            "Not an error: the column is carried into the merged GTFS as an extension field. "
            "Prefix it TODS_ if it should stay TODS-only metadata instead."
        ),
    ),
    "TODS-E201": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,,garage,08:00:00,garage,08:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,08:00:00,garage,08:00:00"
        ),
        note="event_type is Required and cannot be blank; supply a value.",
    ),
    "TODS-E202": RuleExample(
        file="stops_supplement.txt",
        before="stop_id,TODS_delete\ngarage,yes",
        after="stop_id,TODS_delete\ngarage,1",
        note="TODS_delete only accepts 1 (or blank); 'yes' is not one of the allowed options.",
    ),
    "TODS-E203": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,9am,garage,08:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,09:00:00,garage,08:00:00"
        ),
        note=(
            "Times must be HH:MM:SS (values past 24:00:00 are allowed for post-midnight events); "
            "'9am' does not match the format."
        ),
    ),
    "TODS-E204": RuleExample(
        file="vehicles.txt",
        before="vehicle_id,vehicle_label\nbus-1,Old Reliable\nbus-1,Duplicate",
        after="vehicle_id,vehicle_label\nbus-1,Old Reliable\nbus-2,Duplicate",
        note="vehicle_id is the primary key; give the second row its own ID.",
    ),
    "TODS-E205": RuleExample(
        file="vehicle_assignments.txt",
        before="date,service_id,block_id,vehicle_id\n20260106,,B1,bus-1",
        after="date,service_id,block_id,vehicle_id\n20260106,weekday,B1,bus-1",
        note=(
            "trips.txt reuses block_id B1 across more than one service, so service_id must be "
            "filled in to say which one this assignment is for."
        ),
    ),
    "TODS-W206": RuleExample(
        file="vehicles.txt",
        before="vehicle_id,vehicle_label\nbus-1 ,Old Reliable",
        after="vehicle_id,vehicle_label\nbus-1,Old Reliable",
        note=(
            "Leading/trailing spaces are kept as part of the value by most parsers and silently "
            "break exact-match lookups elsewhere in the feed. `tods-validate fix` trims these "
            "automatically."
        ),
    ),
    "TODS-E207": RuleExample(
        file="routes_supplement.txt",
        before="route_id,route_color\nR1,red",
        after="route_id,route_color\nR1,FF0000",
        note=(
            "GTFS Color fields are six hex digits with no leading '#'; a named color "
            "like 'red' is not valid."
        ),
    ),
    "TODS-E301": RuleExample(
        file="employee_run_dates.txt",
        before="date,service_id,run_id,employee_id\n20260106,daily,2,emp-1",
        after="date,service_id,run_id,employee_id\n20260106,daily,1,emp-1",
        note=(
            "run_id 2 has no run_events.txt rows under service_id daily; point at a run that "
            "actually exists (here, 1)."
        ),
    ),
    "TODS-W302": RuleExample(
        file="employee_run_dates.txt",
        before=(
            "date,service_id,run_id,employee_id\n20260106,daily,1,emp-1  # run_events.txt is not "
            "in this package"
        ),
        after="(add run_events.txt to the package, or pass the correct --gtfs/path)",
        note=(
            "Without run_events.txt, run_id references cannot be checked at all; this is a warning "
            "because the file may simply be outside the current validation pass, not necessarily "
            "missing from the real feed."
        ),
    ),
    "TODS-E303": RuleExample(
        file="vehicle_assignments.txt",
        before="date,service_id,block_id,vehicle_id\n20260106,daily,B1,bus-9",
        after="date,service_id,block_id,vehicle_id\n20260106,daily,B1,bus-1",
        note="vehicle_id bus-9 is not defined in vehicles.txt; assign an existing vehicle.",
    ),
    "TODS-E304": RuleExample(
        file="stops_supplement.txt",
        before="stop_id,stop_name,TODS_delete\ns1,,1\ns1,Replacement Name,",
        after="stop_id,stop_name,TODS_delete\ns1,Replacement Name,",
        note=(
            "s1 appears twice: once deleted, once redefined, which is contradictory. Keep a single "
            "row per stop_id."
        ),
    ),
    "TODS-W305": RuleExample(
        file="stops_supplement.txt",
        before="stop_id,stop_name,TODS_delete\ns1,Name A,\ns1,Name B,",
        after="stop_id,stop_name,TODS_delete\ns1,Name B,",
        note=(
            "Two rows update the same stop_id; the merge applies them in file order, so the first "
            "update is silently overwritten. Keep one row per primary key."
        ),
    ),
    "TODS-W306": RuleExample(
        file="stops_supplement.txt",
        before="stop_id,stop_name,TODS_delete\ns1,New Name,1",
        after="stop_id,stop_name,TODS_delete\ns1,,1",
        note=(
            "A deleted row's other columns are never applied; clear them so the file doesn't imply "
            "the rename survives."
        ),
    ),
    "TODS-E307": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "daily,1,1,Operator,ghost-trip,s1,08:00:00,s2,09:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "daily,1,1,Operator,t1,s1,08:00:00,s2,09:00:00"
        ),
        note="trip_id ghost-trip is not defined in trips.txt; point at a real trip (here, t1).",
    ),
    "TODS-E308": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "ghost,1,1,Report,garage,08:00:00,garage,08:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,08:00:00,garage,08:00:00"
        ),
        note=(
            "service_id ghost is not defined in calendar.txt/calendar_dates.txt; use a service "
            "that exists (here, daily)."
        ),
    ),
    "TODS-E309": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,ghost-stop,08:00:00,s1,08:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,s1,08:00:00,s1,08:00:00"
        ),
        note="ghost-stop is not defined in stops.txt; use a stop_id that exists.",
    ),
    "TODS-E310": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,block_id,start_location,"
            "start_time,"
            "end_location,end_time\n"
            "daily,1,1,Operator,t1,B2,s1,08:00:00,s2,09:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,block_id,start_location,"
            "start_time,"
            "end_location,end_time\n"
            "daily,1,1,Operator,t1,B1,s1,08:00:00,s2,09:00:00"
        ),
        note=(
            "trips.txt says trip t1 belongs to block B1, but this event claims block_id B2; the "
            "two must agree."
        ),
    ),
    "TODS-E311": RuleExample(
        file="vehicle_assignments.txt",
        before="date,service_id,block_id,vehicle_id\n20260106,daily,B9,bus-1",
        after="date,service_id,block_id,vehicle_id\n20260106,daily,B1,bus-1",
        note=(
            "block_id B9 is not used by any trip in trips.txt; assign a block that is actually "
            "scheduled."
        ),
    ),
    "TODS-E312": RuleExample(
        file="vehicle_assignments.txt",
        before="date,service_id,block_id,vehicle_id\n20260106,ghost,B1,bus-1",
        after="date,service_id,block_id,vehicle_id\n20260106,daily,B1,bus-1",
        note="service_id ghost does not exist; use a defined service.",
    ),
    "TODS-W313": RuleExample(
        file="stops_supplement.txt",
        before="stop_id,TODS_delete\ns2,1",
        after="stop_id,TODS_delete\ns1,1",
        note=(
            "s2 is not in the companion GTFS stops.txt, so there is nothing for this delete to "
            "remove; check for a typo against the stop_id it should target (here, s1)."
        ),
    ),
    "TODS-E314": RuleExample(
        file="trips_supplement.txt",
        before="route_id,service_id,trip_id\nghost,daily,t9",
        after="route_id,service_id,trip_id\nr1,daily,t9",
        note=(
            "route_id ghost is not defined in the companion GTFS routes.txt; reference a route "
            "that exists."
        ),
    ),
    "TODS-W315": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "weekday,1,10,Operator,T1,S3,09:00:00,S2,10:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "weekday,1,10,Operator,T1,S1,09:00:00,S2,10:00:00"
        ),
        note=(
            "stop_times.txt says trip T1's first stop is S1, not S3; the run event's "
            "start_location should match."
        ),
    ),
    "TODS-W316": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "weekday,1,10,Operator,T1,S1,08:30:00,S2,10:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "weekday,1,10,Operator,T1,S1,09:00:00,S2,10:00:00"
        ),
        note=(
            "stop_times.txt schedules trip T1 to depart S1 at 09:00:00; the run event's start_time "
            "should match within tolerance."
        ),
    ),
    "TODS-E401": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,10:00:00,garage,09:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Report,garage,09:00:00,garage,10:00:00"
        ),
        note=(
            "end_time (09:00:00) is before start_time (10:00:00); an event cannot end before it "
            "starts."
        ),
    ),
    "TODS-E402": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "daily,1,1,Operator,t1,s1,10:00:00,s2,11:00:00\n"
            "daily,1,2,Operator,t2,s2,10:30:00,s3,11:30:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "daily,1,1,Operator,t1,s1,10:00:00,s2,11:00:00\n"
            "daily,1,2,Operator,t2,s2,11:00:00,s3,12:00:00"
        ),
        note=(
            "Event 2 starts (10:30:00) before event 1 ends (11:00:00); one run cannot be in two "
            "trips at once, so shift event 2 to start after event 1 ends."
        ),
    ),
    "TODS-W403": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,10,Report,garage,10:00:00,garage,10:05:00\n"
            "daily,1,20,Report,garage,09:00:00,garage,09:05:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,10,Report,garage,09:00:00,garage,09:05:00\n"
            "daily,1,20,Report,garage,10:00:00,garage,10:05:00"
        ),
        note=(
            "event_sequence 10 then 20 implies chronological order, but the times run backwards; "
            "reorder the rows (or the sequence numbers) to match the times."
        ),
    ),
    "TODS-W404": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Work,s1,08:00:00,s1,12:00:00\n"
            "daily,2,1,Work,s1,10:00:00,s1,14:00:00"
            "  # employee_run_dates.txt assigns emp-1 to both run 1 and run 2 on 20260106"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Work,s1,08:00:00,s1,12:00:00\n"
            "daily,2,1,Work,s1,10:00:00,s1,14:00:00"
            "  # employee_run_dates.txt assigns emp-1 to only one of run 1 / run 2 on 20260106"
        ),
        note=(
            "Run 1 (08:00-12:00) and run 2 (10:00-14:00) overlap; the same employee cannot work "
            "both on the same date."
        ),
    ),
    "TODS-E405": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "weekday,1,1,Operator,t1,s1,08:00:00,s2,09:00:00"
            "  # trips.txt: t1 belongs to service_id weekend"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "weekday,1,1,Operator,t1,s1,08:00:00,s2,09:00:00"
            "  # trips.txt: t1 belongs to service_id weekday"
        ),
        note=(
            "This run's service_id (weekday) does not match the service_id of the trip (t1) it "
            "references in trips.txt; a run and the trips it runs must share a service."
        ),
    ),
    "TODS-W406": RuleExample(
        file="employee_run_dates.txt",
        before=(
            "date,service_id,run_id,employee_id\n"
            "20260110,weekday,1,emp-1  # calendar.txt: weekday does not operate 2026-01-10 (Saturd"
            "ay)"
        ),
        after=(
            "date,service_id,run_id,employee_id\n"
            "20260112,weekday,1,emp-1  # 2026-01-12 is a Monday, when weekday service runs"
        ),
        note=(
            "The assignment date must be a date the run's service actually operates, per "
            "calendar.txt/calendar_dates.txt."
        ),
    ),
    "TODS-W407": RuleExample(
        file="vehicle_assignments.txt",
        before=(
            "date,service_id,block_id,vehicle_id\n"
            "20260110,weekday,B1,bus-1  # weekday service does not operate 2026-01-10 (Saturday)"
        ),
        after=(
            "date,service_id,block_id,vehicle_id\n"
            "20260112,weekday,B1,bus-1  # 2026-01-12 is a Monday, when weekday service runs"
        ),
        note=(
            "Same idea as TODS-W406, for vehicle assignments: the date must fall within the "
            "service's operating days."
        ),
    ),
    "TODS-W408": RuleExample(
        file="employee_run_dates.txt",
        before="date,service_id,run_id,employee_id\n20260106,daily,1,emp-1\n20260106,daily,1,emp-1",
        after="date,service_id,run_id,employee_id\n20260106,daily,1,emp-1",
        note=(
            "The two rows are identical; drop the duplicate (`tods-validate fix` does this "
            "automatically)."
        ),
    ),
    "TODS-W409": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Pullout,garage,08:00:00,stopA,08:30:00\n"
            "daily,1,2,Operate,stopB,08:30:00,garage,09:30:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,1,Pullout,garage,08:00:00,stopA,08:30:00\n"
            "daily,1,2,Operate,stopA,08:30:00,garage,09:30:00"
        ),
        note=(
            "Event 1 ends at stopA but event 2 starts at stopB; consecutive events in a run should "
            "connect at the same location unless a mid-trip flag explains the gap."
        ),
    ),
    "TODS-I501": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "daily,1,10,Operator,t1,s1,10:00:00,s2,10:30:00"
            "  # trips.txt also defines trip t2, with no run event referencing it"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,trip_id,start_location,start_time,"
            "end_location,"
            "end_time\n"
            "daily,1,10,Operator,t1,s1,10:00:00,s2,10:30:00\n"
            "daily,1,20,Operator,t2,s2,10:30:00,s3,11:00:00"
        ),
        note=(
            "t2 has no run event at all. Informational coverage check; opt in with --enable "
            "coverage or --enable TODS-I501."
        ),
    ),
    "TODS-I502": RuleExample(
        file="vehicle_assignments.txt",
        before=(
            "date,service_id,block_id,vehicle_id\n"
            "20260106,daily,B1,bus-1"
            "  # trips.txt also defines block B2, with no vehicle_assignments row"
        ),
        after=(
            "date,service_id,block_id,vehicle_id\n20260106,daily,B1,bus-1\n20260106,daily,B2,bus-2"
        ),
        note=(
            "Block B2 has no vehicle assignment. Informational coverage check; opt in with "
            "--enable coverage or --enable TODS-I502."
        ),
    ),
    "TODS-I601": RuleExample(
        file="run_events.txt",
        before=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,10,Operator,s1,06:00:00,s1,06:10:00\n"
            "daily,1,20,Operator,s1,06:10:00,s1,14:00:00"
        ),
        after=(
            "service_id,run_id,event_sequence,event_type,start_location,start_time,end_location,"
            "end_time\n"
            "daily,1,10,Operator,s1,06:00:00,s1,06:10:00\n"
            "daily,1,20,Operator,s1,06:10:00,s1,10:00:00\n"
            "daily,1,25,Break,s1,10:00:00,s1,10:30:00\n"
            "daily,1,30,Operator,s1,10:30:00,s1,14:00:00"
        ),
        note=(
            "Nearly 8 hours pass with no Break event. Advisory check; opt in with --enable "
            "advisory or --enable TODS-I601."
        ),
    ),
}


def example_for(rule_id: str) -> RuleExample | None:
    """The worked example for a rule, if one has been written."""
    return EXAMPLES.get(rule_id)


def render_example_markdown(example: RuleExample) -> list[str]:
    """Markdown lines rendering a worked example (no leading/trailing blanks).

    Shared by :func:`render_rule_detail` and ``scripts/generate_rules_doc.py``
    so the docs and the CLI/hover renderings cannot drift from each other.
    """
    lines = [
        f"Example (`{example.file}`):",
        "",
        "Before:",
        "```csv",
        example.before,
        "```",
        "",
        "After:",
        "```csv",
        example.after,
        "```",
    ]
    if example.note:
        lines += ["", example.note]
    return lines


def render_example_text(example: RuleExample) -> list[str]:
    """Plain-text lines rendering a worked example, for the terminal."""
    lines = [
        f"Example ({example.file}):",
        "  before:",
        *(f"    {line}" for line in example.before.splitlines() or [""]),
        "  after:",
        *(f"    {line}" for line in example.after.splitlines() or [""]),
    ]
    if example.note:
        lines += ["", f"  {example.note}"]
    return lines


def render_rule_detail(rule_def: Rule, fmt: str = "text") -> str:
    """Full rule detail — id, severity, title, description, spec citation,
    interpretation note, and a worked example — as plain text or Markdown.

    The single renderer behind ``tods-validate explain``, LSP hovers
    (:func:`tods_validate.lsp.hover_markdown`), and (for the example fields)
    ``scripts/generate_rules_doc.py``, so all three describe a rule
    identically.
    """
    example = EXAMPLES.get(rule_def.id)
    if fmt == "markdown":
        lines = [
            f"**{rule_def.id}** — {rule_def.title}  ({rule_def.severity.name})",
            "",
            rule_def.description,
        ]
        if rule_def.interpretation:
            lines += ["", f"_Interpretation:_ {rule_def.interpretation}"]
        lines += ["", f"[TODS specification]({rule_def.spec_section})"]
        if example is not None:
            lines += ["", *render_example_markdown(example)]
        return "\n".join(lines)

    lines = [
        f"{rule_def.id}  {rule_def.severity.name:7}  {rule_def.title}",
        "",
        rule_def.description,
    ]
    if rule_def.interpretation:
        lines += ["", f"Interpretation: {rule_def.interpretation}"]
    lines += ["", f"Spec: {rule_def.spec_section}"]
    if example is not None:
        lines += ["", *render_example_text(example)]
    return "\n".join(lines)


REGISTRY: list[Rule] = []


# Per-rule outcomes recorded for the validation-assurance manifest. A green run
# should be able to state its own scope: which rules actually ran, and which
# were skipped and why. See RunCoverage.
STATUS_RAN = "ran"
STATUS_SKIPPED_NEEDS_GTFS = "skipped:needs_gtfs"
STATUS_SKIPPED_NEEDS_GTFS_TABLE = "skipped:needs_gtfs_table"
STATUS_SKIPPED_DISABLED = "skipped:disabled"
STATUS_SKIPPED_IGNORED = "skipped:ignored"
STATUS_SKIPPED_SPEC_VERSION = "skipped:spec_version"

# Human-readable reason per status, for the one-line disclosure in reports.
# This mapping is the single source of the skipped statuses: RunCoverage groups
# by its keys, so a status added here is disclosed everywhere, and a status
# added *without* an entry here would be counted as skipped but never explained
# -- which is the failure this manifest exists to prevent.
_STATUS_REASON = {
    STATUS_SKIPPED_NEEDS_GTFS: "no companion GTFS feed was provided",
    STATUS_SKIPPED_NEEDS_GTFS_TABLE: (
        "the companion GTFS feed has none of the files the check reads"
    ),
    STATUS_SKIPPED_DISABLED: "opt-in rule not enabled (use --enable)",
    STATUS_SKIPPED_IGNORED: "suppressed by local policy (--ignore)",
    STATUS_SKIPPED_SPEC_VERSION: "not defined by the requested --spec-version",
}

# What a report says when nothing was skipped. A run that discloses skips only
# when there are some cannot be told apart from a run whose report format never
# discloses anything, so the complete case states itself rather than staying
# silent.
ALL_CHECKS_RAN = "Every applicable check ran"

# The skips the invocation did not ask for. --ignore, opt-in rules left off,
# and --spec-version scoping are all choices the caller made; a missing (or
# unusable) companion GTFS feed is not, so these two are the statuses that mean
# "this run wanted to check something and could not". --require-complete-run
# gates on exactly this set; see RunCoverage.unrequested_skips.
UNREQUESTED_SKIP_STATUSES = frozenset({STATUS_SKIPPED_NEEDS_GTFS, STATUS_SKIPPED_NEEDS_GTFS_TABLE})


@dataclass(frozen=True)
class RuleOutcome:
    """Whether one rule ran during a validation, and why not if it did not."""

    id: str
    severity: Severity
    category: str
    status: str

    @property
    def ran(self) -> bool:
        return self.status == STATUS_RAN

    @property
    def reason(self) -> str | None:
        return _STATUS_REASON.get(self.status)


@dataclass(frozen=True)
class RunCoverage:
    """A validation-assurance manifest: what did and did not run.

    Every report can carry this so that a clean result is qualified by its own
    scope. ``outcomes`` holds one :class:`RuleOutcome` per registered rule that
    was considered for the run, in registry order.
    """

    outcomes: tuple[RuleOutcome, ...]

    @property
    def ran(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.outcomes if o.ran)

    @property
    def skipped(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.ran)

    @property
    def unrequested_skips(self) -> tuple[RuleOutcome, ...]:
        """Rules that could not run because an input was missing.

        Distinct from :attr:`skipped`, which also counts the skips the caller
        asked for. See UNREQUESTED_SKIP_STATUSES.
        """
        return tuple(o for o in self.outcomes if o.status in UNREQUESTED_SKIP_STATUSES)

    def skipped_by_reason(self) -> dict[str, list[RuleOutcome]]:
        """Skipped rules grouped by status, in a stable status order.

        Iterates _STATUS_REASON rather than its own list of statuses, so every
        skipped rule lands in exactly one group and no skip can go undisclosed.
        """
        grouped: dict[str, list[RuleOutcome]] = {}
        for status in _STATUS_REASON:
            members = [o for o in self.outcomes if o.status == status]
            if members:
                grouped[status] = members
        return grouped

    def with_ignored(self, ignore: Collection[str]) -> RunCoverage:
        """Return a copy in which rules suppressed by ``--ignore`` are disclosed.

        A rule that ran but whose findings were then dropped by ``--ignore`` is
        reclassified ``skipped:ignored`` so the report still admits its findings
        were withheld. Rules skipped for other reasons keep that reason.
        """
        if not ignore:
            return self
        ignore = set(ignore)
        return RunCoverage(
            tuple(
                replace(o, status=STATUS_SKIPPED_IGNORED) if o.ran and o.id in ignore else o
                for o in self.outcomes
            )
        )

    def to_dict(self) -> dict[str, object]:
        """The additive ``coverage`` block emitted in the JSON report."""
        skipped = self.skipped
        return {
            "total": len(self.outcomes),
            "ran": len(self.ran),
            "skipped": len(skipped),
            "skippedByReason": {
                status: [o.id for o in members]
                for status, members in self.skipped_by_reason().items()
            },
            "rules": [
                {
                    "id": o.id,
                    "severity": o.severity.name,
                    "category": o.category,
                    "status": o.status,
                }
                for o in self.outcomes
            ],
        }

    def summary_line(self) -> str | None:
        """One line disclosing skipped checks, or None when everything ran."""
        groups = self.skipped_by_reason()
        if not groups:
            return None
        parts = [f"{len(members)} {_STATUS_REASON[status]}" for status, members in groups.items()]
        return "Checks skipped: " + "; ".join(parts) + "."

    def scope_line(self) -> str:
        """One line stating what the run covered. Never empty.

        Where :meth:`summary_line` returns None on a complete run, this states
        the complete case positively. That difference is the point: a reader who
        sees no coverage line cannot tell "nothing was skipped" from "this
        format does not disclose skips", and the second is exactly how a feed
        validated without its companion GTFS feed came to read as fully checked.
        """
        skipped = self.summary_line()
        ran, total = len(self.ran), len(self.outcomes)
        if skipped is None:
            return f"{ALL_CHECKS_RAN} ({ran} of {total})."
        return f"{ran} of {total} checks ran. {skipped}"

    def skipped_detail_lines(self) -> list[str]:
        """One line per skip reason, naming every rule it covers.

        A count cannot be acted on. Deciding whether a clean report means
        anything takes the rule IDs, and above all how many of them are
        ERROR-severity: those are the checks a green result is being read as
        having passed.
        """
        lines = []
        for status, members in self.skipped_by_reason().items():
            severities = ", ".join(
                f"{count} {name}"
                for name, count in (
                    (severity.name, sum(1 for o in members if o.severity is severity))
                    for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO)
                )
                if count
            )
            ids = ", ".join(o.id for o in members)
            lines.append(f"Not run, {_STATUS_REASON[status]} ({severities}): {ids}")
        return lines


def rule(
    id: str,
    severity: Severity,
    title: str,
    description: str,
    spec_section: str,
    needs_gtfs: bool = False,
    gtfs_tables: tuple[tuple[str, ...], ...] = (),
    category: str = "core",
    default_enabled: bool = True,
    interpretation: str | None = None,
    example: str | None = None,
    spec_versions: tuple[str, ...] | None = None,
) -> Callable[[CheckFunction], CheckFunction]:
    """Register a check function. Used as a decorator in the rule modules."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown rule category {category!r}")
    if needs_gtfs and not gtfs_tables:
        raise ValueError(
            f"rule {id} needs the companion GTFS feed but does not declare which "
            "files it reads (gtfs_tables); without that it would be reported as "
            "having run against a companion that cannot answer it"
        )
    if gtfs_tables and not needs_gtfs:
        raise ValueError(f"rule {id} declares gtfs_tables but does not set needs_gtfs")
    unknown = {name for group in gtfs_tables for name in group} - set(GTFS_PRIMARY_KEYS)
    if unknown:
        raise ValueError(
            f"rule {id} declares GTFS file(s) the companion feed does not model: "
            f"{', '.join(sorted(unknown))}"
        )

    def decorator(check: CheckFunction) -> CheckFunction:
        if any(r.id == id for r in REGISTRY):
            raise ValueError(f"duplicate rule id {id}")
        REGISTRY.append(
            Rule(
                id=id,
                severity=severity,
                title=title,
                description=description,
                spec_section=spec_section,
                check=check,
                needs_gtfs=needs_gtfs,
                gtfs_tables=gtfs_tables,
                category=category,
                default_enabled=default_enabled,
                interpretation=interpretation,
                example=example,
                spec_versions=spec_versions,
            )
        )
        return check

    return decorator


def _is_enabled(r: Rule, enabled: frozenset[str]) -> bool:
    if r.default_enabled:
        return True
    return r.id in enabled or r.category in enabled


def missing_gtfs_tables(r: Rule, gtfs: CompanionGTFS) -> tuple[str, ...]:
    """Which of ``r``'s required GTFS files the companion feed does not have.

    A requirement group is met when any one of its alternatives is a *base*
    file of the companion feed. A TODS supplement file does not meet it: a
    supplement modifies a GTFS table, so without that table there is nothing to
    resolve a reference against, and every ID would look missing.
    """
    return tuple(" or ".join(group) for group in r.gtfs_tables if not set(group) & gtfs.present)


def _rule_status(r: Rule, context: ValidationContext, enabled: frozenset[str]) -> str:
    if r.spec_versions is not None and context.spec_version not in r.spec_versions:
        return STATUS_SKIPPED_SPEC_VERSION
    if r.needs_gtfs:
        if context.gtfs is None:
            return STATUS_SKIPPED_NEEDS_GTFS
        if missing_gtfs_tables(r, context.gtfs):
            return STATUS_SKIPPED_NEEDS_GTFS_TABLE
    if not _is_enabled(r, enabled):
        return STATUS_SKIPPED_DISABLED
    return STATUS_RAN


def validate(
    context: ValidationContext, enabled: frozenset[str] = frozenset()
) -> tuple[list[Finding], RunCoverage]:
    """Run every applicable rule; return its findings and a coverage manifest.

    Findings come back in file/row order. The :class:`RunCoverage` records, for
    every registered rule, whether it ran or was skipped and why, so a report
    can state its own scope instead of implying a clean run checked everything.

    ``enabled`` additionally turns on opt-in rules: it may contain rule IDs or
    category names ("coverage", "advisory", "experimental").
    """
    findings: list[Finding] = []
    outcomes: list[RuleOutcome] = []
    for r in REGISTRY:
        status = _rule_status(r, context, enabled)
        outcomes.append(
            RuleOutcome(id=r.id, severity=r.severity, category=r.category, status=status)
        )
        if status == STATUS_RAN:
            findings.extend(r.check(context))
    findings.sort(key=lambda f: (f.file or "", f.row or 0, f.rule_id))
    return findings, RunCoverage(tuple(outcomes))


def all_rules() -> Iterable[Rule]:
    return tuple(REGISTRY)


# Importing the rule modules populates the registry.
from . import coverage, fields, references, semantics, structure  # noqa: E402,F401

__all__ = [
    "ALL_CHECKS_RAN",
    "EXAMPLES",
    "REGISTRY",
    "UNREQUESTED_SKIP_STATUSES",
    "Rule",
    "RuleOutcome",
    "RunCoverage",
    "RuleExample",
    "ValidationContext",
    "all_rules",
    "example_for",
    "render_example_markdown",
    "render_example_text",
    "render_rule_detail",
    "rule",
    "validate",
]
