"""Table and field definitions for TODS v2.1.0, plus the superseded v1.0.0.

v2.1.0 was transcribed by hand from the spec reference at
https://tods-transit.org/spec/ (source:
https://github.com/MobilityData/transit-operational-data-standard,
docs/en/spec/index.md, "last updated on 2025-04-16 (v2.1.0)").

The standard was known as the Operational Data Standard (ODS) before v2.0;
rule IDs in this validator keep the TODS- prefix.

v1.0.0 ("last updated on April 14, 2022 (v1.0)" per its own spec page) is no
longer published at a live URL -- the current site only hosts the current
spec text, and v1's files (deadheads.txt, ops_locations.txt,
deadhead_times.txt) were removed from the spec in v2.0.0-alpha.1 (2024-06-20,
per https://tods-transit.org/spec/revision-history/). Its field/file
inventory below is transcribed from the last commit before v2 work began on
the spec source, a reproducible historical snapshot:
https://github.com/MobilityData/transit-operational-data-standard/blob/27d3694c8f73cbcf0ee349d8a9155d9d115b278e/docs/spec/index.md
("rename duplicate `to_deadhead_id` field", 2022-10-18, the last commit
touching the spec text before the first v2-oriented commit on 2024-02-27).
v1.0.0 declares no "Primary Key" for any file (that convention appears only
starting with v2's field tables) and no Supplement-file mechanism (introduced
in v2.0.0-alpha.1) -- both are left as the spec leaves them, not guessed at.
The one stated exception is `runs_pieces.txt:piece_id`, whose field
description explicitly says "must be unique", so that is encoded as a
single-field primary key.

Each definition carries a citation to the spec section it came from. If the
spec and this file disagree, the spec wins; please open an issue (v2.1.0) or
see docs/spec-versions.md (v1.0.0, historical).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

SPEC_VERSION = "2.1.0"
SPEC_VERSION_V1 = "1.0.0"
# Spec versions this validator can be asked to target via --spec-version.
# 2.1.0 is the current spec and the default. 1.0.0 is the last spec version
# before the Supplement-file mechanism and the current TODS-specific files
# were introduced; see docs/spec-versions.md for the file/field deltas.
SUPPORTED_SPEC_VERSIONS = (SPEC_VERSION_V1, SPEC_VERSION)
SPEC_URL = "https://tods-transit.org/spec/"
# v1.0.0 has no live spec URL (see module docstring); cite the historical
# commit instead so every v1 finding still points at real spec text.
SPEC_URL_V1 = (
    "https://github.com/MobilityData/transit-operational-data-standard/blob/"
    "27d3694c8f73cbcf0ee349d8a9155d9d115b278e/docs/spec/index.md"
)


class FieldType(Enum):
    ID = "ID"
    TEXT = "Text"
    ENUM = "Enum"
    TIME = "Time"
    DATE = "Date"
    NON_NEGATIVE_INTEGER = "Non-negative integer"
    # v1.0.0 only (ops_locations.txt); no v2.1.0 field uses these.
    LATITUDE = "Latitude"
    LONGITUDE = "Longitude"
    NON_NEGATIVE_FLOAT = "Non-negative float"
    # GTFS's Color field type (six hex digits, no leading '#'; GTFS reference
    # spec, "Field Types"), carried into v2.1.0 supplement files via the
    # "fields match GTFS" rule (TODS spec, "Supplement Files > Structure").
    # routes.txt:route_color/route_text_color are the only Color-typed GTFS
    # fields a supplement file can carry today (see _supplement()'s
    # field_types override). See rule TODS-E207.
    COLOR = "Color"


class Presence(Enum):
    REQUIRED = "Required"
    OPTIONAL = "Optional"
    # Required under a condition stated in the spec; checked by a dedicated rule.
    CONDITIONAL = "Conditionally required"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: FieldType
    presence: Presence
    # Allowed values for ENUM fields. The empty string is always accepted for
    # optional enums (spec writes "(blank)").
    enum_values: tuple[str, ...] = ()
    # Where this ID points, as "file.field" (e.g. "trips.trip_id"). Reference
    # targets in GTFS files are resolved against the companion GTFS feed.
    references: str | None = None


@dataclass(frozen=True)
class TableSpec:
    filename: str
    kind: str  # "supplement" | "tods"
    # Spec section anchor. Under SPEC_URL for spec_version == SPEC_VERSION;
    # under SPEC_URL_V1 for spec_version == SPEC_VERSION_V1. See spec_link().
    spec_anchor: str
    # Primary key field names. None means the spec defines no uniqueness
    # constraint (all of v1.0.0 except runs_pieces.txt, which states "must be
    # unique" in prose).
    primary_key: tuple[str, ...] | None = None
    fields: tuple[FieldSpec, ...] = ()
    # For supplement files: the GTFS file this supplements.
    gtfs_base: str | None = None
    # Which --spec-version this table belongs to.
    spec_version: str = SPEC_VERSION


# ---------------------------------------------------------------------------
# GTFS base-file inventories, used to check supplement file headers.
#
# Supplement files carry "fields match those defined in the corresponding
# file's GTFS specification" (spec, "Supplement Files > Structure"), plus the
# TODS_-prefixed fields below. Field name lists transcribed from the GTFS
# reference, https://gtfs.org/documentation/schedule/reference/ (revised
# 2026-04-27, checked 2026-07-16) — names only; this validator does not
# otherwise re-validate GTFS semantics.
#
# Primary keys per https://gtfs.org/documentation/schedule/reference/#dataset-attributes,
# which the spec cites for supplement row matching.
# ---------------------------------------------------------------------------

GTFS_FIELDS: dict[str, tuple[str, ...]] = {
    "trips.txt": (
        "route_id",
        "service_id",
        "trip_id",
        "trip_headsign",
        "trip_short_name",
        "direction_id",
        "block_id",
        "shape_id",
        "wheelchair_accessible",
        "bikes_allowed",
        "cars_allowed",
        "safe_duration_factor",
        "safe_duration_offset",
    ),
    "stops.txt": (
        "stop_id",
        "stop_code",
        "stop_name",
        "tts_stop_name",
        "stop_desc",
        "stop_lat",
        "stop_lon",
        "zone_id",
        "stop_url",
        "location_type",
        "parent_station",
        "stop_timezone",
        "wheelchair_boarding",
        "level_id",
        "platform_code",
        "stop_access",
    ),
    "stop_times.txt": (
        "trip_id",
        "arrival_time",
        "departure_time",
        "stop_id",
        "location_group_id",
        "location_id",
        "stop_sequence",
        "stop_headsign",
        "start_pickup_drop_off_window",
        "end_pickup_drop_off_window",
        "pickup_type",
        "drop_off_type",
        "continuous_pickup",
        "continuous_drop_off",
        "shape_dist_traveled",
        "timepoint",
        "pickup_booking_rule_id",
        "drop_off_booking_rule_id",
    ),
    "routes.txt": (
        "route_id",
        "agency_id",
        "route_short_name",
        "route_long_name",
        "route_desc",
        "route_type",
        "route_url",
        "route_color",
        "route_text_color",
        "route_sort_order",
        "continuous_pickup",
        "continuous_drop_off",
        "network_id",
        "cemv_support",
    ),
    "calendar.txt": (
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ),
    "calendar_dates.txt": (
        "service_id",
        "date",
        "exception_type",
    ),
}

GTFS_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "trips.txt": ("trip_id",),
    "stops.txt": ("stop_id",),
    "stop_times.txt": ("trip_id", "stop_sequence"),
    "routes.txt": ("route_id",),
    "calendar.txt": ("service_id",),
    "calendar_dates.txt": ("service_id", "date"),
}

# The GTFS files TODS IDs actually resolve against -- the only ones the
# companion view models. A package carrying none of these cannot serve as its
# own companion feed, however many other GTFS files sit beside the TODS files:
# a stray agency.txt says nothing about whether a trip_id exists.
GTFS_COMPANION_FILENAMES: frozenset[str] = frozenset(GTFS_PRIMARY_KEYS)

# Fields whose Presence is exactly Required in the current GTFS Schedule
# reference. Conditionally Required fields are intentionally excluded: whether
# they apply depends on values and relationships outside this TODS clarification.
# The TODS supplement guidance requires these fields only when a supplement row
# adds a new GTFS row, not when it updates or deletes an existing one.
GTFS_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "trips.txt": ("route_id", "service_id", "trip_id"),
    "stops.txt": ("stop_id",),
    "stop_times.txt": ("trip_id", "stop_sequence"),
    "routes.txt": ("route_id", "route_type"),
    "calendar.txt": (
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ),
    "calendar_dates.txt": ("service_id", "date", "exception_type"),
}

# Spec, "Supplement Files > TODS-Specific Fields".
TODS_DELETE = FieldSpec("TODS_delete", FieldType.ENUM, Presence.OPTIONAL, enum_values=("", "1"))


def _supplement(
    filename: str,
    gtfs_base: str,
    extra: tuple[FieldSpec, ...] = (),
    field_types: dict[str, FieldType] | None = None,
) -> TableSpec:
    """Build a supplement TableSpec from the GTFS base file's field inventory.

    A supplement row need only carry the fields it changes ("As blank fields
    are ignored", spec "Supplement Files > Implications and Guidance"), so
    every non-key field defaults to Optional -- the base file's own Required
    fields, if any, are GTFS_REQUIRED_FIELDS' concern for an *added* row, not
    this table's static Presence. Fields default to FieldType.TEXT because
    the GTFS reference field-type inventory is not transcribed here in full;
    ``field_types`` overrides specific fields where a spec-cited check exists
    for them (see e.g. FieldType.COLOR, rule TODS-E207).
    """
    pk = GTFS_PRIMARY_KEYS[gtfs_base]
    field_types = field_types or {}
    key_fields = tuple(FieldSpec(name, FieldType.ID, Presence.REQUIRED) for name in pk)
    other_fields = tuple(
        FieldSpec(name, field_types.get(name, FieldType.TEXT), Presence.OPTIONAL)
        for name in GTFS_FIELDS[gtfs_base]
        if name not in pk
    )
    return TableSpec(
        filename=filename,
        kind="supplement",
        spec_anchor="#supplement-files",
        primary_key=pk,
        fields=key_fields + other_fields + extra + (TODS_DELETE,),
        gtfs_base=gtfs_base,
    )


# ---------------------------------------------------------------------------
# TODS-specific files. Spec, "TODS-Specific File Definitions".
# ---------------------------------------------------------------------------

RUN_EVENTS = TableSpec(
    filename="run_events.txt",
    kind="tods",
    spec_anchor="#run_eventstxt",
    primary_key=("service_id", "run_id", "event_sequence"),
    fields=(
        FieldSpec(
            "service_id",
            FieldType.ID,
            Presence.REQUIRED,
            references="calendar.service_id",
        ),
        FieldSpec("run_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("event_sequence", FieldType.NON_NEGATIVE_INTEGER, Presence.REQUIRED),
        FieldSpec("piece_id", FieldType.ID, Presence.OPTIONAL),
        FieldSpec("block_id", FieldType.ID, Presence.OPTIONAL, references="trips.block_id"),
        FieldSpec("job_type", FieldType.TEXT, Presence.OPTIONAL),
        FieldSpec("event_type", FieldType.TEXT, Presence.REQUIRED),
        FieldSpec("trip_id", FieldType.ID, Presence.OPTIONAL, references="trips.trip_id"),
        FieldSpec("start_location", FieldType.ID, Presence.REQUIRED, references="stops.stop_id"),
        FieldSpec("start_time", FieldType.TIME, Presence.REQUIRED),
        FieldSpec(
            "start_mid_trip", FieldType.ENUM, Presence.OPTIONAL, enum_values=("", "0", "1", "2")
        ),
        FieldSpec("end_location", FieldType.ID, Presence.REQUIRED, references="stops.stop_id"),
        FieldSpec("end_time", FieldType.TIME, Presence.REQUIRED),
        FieldSpec(
            "end_mid_trip", FieldType.ENUM, Presence.OPTIONAL, enum_values=("", "0", "1", "2")
        ),
    ),
)

EMPLOYEE_RUN_DATES = TableSpec(
    filename="employee_run_dates.txt",
    kind="tods",
    spec_anchor="#employee_run_datestxt",
    # Multiple employees may share a run and date; employee_id distinguishes
    # those assignments in the four-field primary key.
    primary_key=("date", "service_id", "run_id", "employee_id"),
    fields=(
        FieldSpec("date", FieldType.DATE, Presence.REQUIRED),
        FieldSpec(
            "service_id", FieldType.ID, Presence.REQUIRED, references="run_events.service_id"
        ),
        FieldSpec("run_id", FieldType.ID, Presence.REQUIRED, references="run_events.run_id"),
        FieldSpec("employee_id", FieldType.ID, Presence.REQUIRED),
    ),
)

VEHICLES = TableSpec(
    filename="vehicles.txt",
    kind="tods",
    spec_anchor="#vehiclestxt",
    primary_key=("vehicle_id",),
    fields=(
        FieldSpec("vehicle_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("vehicle_label", FieldType.TEXT, Presence.OPTIONAL),
        FieldSpec("license_plate", FieldType.TEXT, Presence.OPTIONAL),
    ),
)

VEHICLE_ASSIGNMENTS = TableSpec(
    filename="vehicle_assignments.txt",
    kind="tods",
    spec_anchor="#vehicle_assignmentstxt",
    primary_key=("date", "block_id", "service_id"),
    fields=(
        FieldSpec("date", FieldType.DATE, Presence.REQUIRED),
        # Spec: "Required if block_ids are repeated between different
        # service_ids." Checked by rule TODS-E205.
        FieldSpec(
            "service_id",
            FieldType.ID,
            Presence.CONDITIONAL,
            references="calendar.service_id",
        ),
        FieldSpec("block_id", FieldType.ID, Presence.REQUIRED, references="trips.block_id"),
        FieldSpec("vehicle_id", FieldType.ID, Presence.REQUIRED, references="vehicles.vehicle_id"),
    ),
)

TRIPS_SUPPLEMENT = _supplement(
    "trips_supplement.txt",
    "trips.txt",
    extra=(FieldSpec("TODS_trip_type", FieldType.TEXT, Presence.OPTIONAL),),
)
STOPS_SUPPLEMENT = _supplement(
    "stops_supplement.txt",
    "stops.txt",
    extra=(FieldSpec("TODS_location_type", FieldType.TEXT, Presence.OPTIONAL),),
)
STOP_TIMES_SUPPLEMENT = _supplement("stop_times_supplement.txt", "stop_times.txt")
ROUTES_SUPPLEMENT = _supplement(
    "routes_supplement.txt",
    "routes.txt",
    # GTFS reference, "Field Types > Color" and routes.txt's route_color/
    # route_text_color rows: "A color encoded as a six-digit hexadecimal
    # number" (no leading '#'). See rule TODS-E207.
    field_types={"route_color": FieldType.COLOR, "route_text_color": FieldType.COLOR},
)
CALENDAR_SUPPLEMENT = _supplement("calendar_supplement.txt", "calendar.txt")
CALENDAR_DATES_SUPPLEMENT = _supplement("calendar_dates_supplement.txt", "calendar_dates.txt")

# Spec, "Dataset Files > Files": all ten files, all optional.
TABLES: dict[str, TableSpec] = {
    t.filename: t
    for t in (
        TRIPS_SUPPLEMENT,
        STOPS_SUPPLEMENT,
        STOP_TIMES_SUPPLEMENT,
        ROUTES_SUPPLEMENT,
        CALENDAR_SUPPLEMENT,
        CALENDAR_DATES_SUPPLEMENT,
        RUN_EVENTS,
        EMPLOYEE_RUN_DATES,
        VEHICLES,
        VEHICLE_ASSIGNMENTS,
    )
}

# ---------------------------------------------------------------------------
# v1.0.0 files. See the module docstring for the source citation. v1 predates
# both the Supplement-file mechanism and the "Primary Key" convention, so
# every table below is kind="tods" and (except runs_pieces.txt) has no
# primary_key. "String"-typed fields are represented as FieldType.TEXT, the
# same free-text type v2.1.0 uses for its own "Text" fields -- the two names
# are synonymous, not a modeling difference.
# ---------------------------------------------------------------------------

DEADHEADS_V1 = TableSpec(
    filename="deadheads.txt",
    kind="tods",
    spec_anchor="#deadheadstxt",
    spec_version=SPEC_VERSION_V1,
    fields=(
        FieldSpec("deadhead_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("service_id", FieldType.ID, Presence.REQUIRED, references="calendar.service_id"),
        FieldSpec("block_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("shape_id", FieldType.ID, Presence.OPTIONAL, references="shapes.shape_id"),
        FieldSpec("to_trip_id", FieldType.ID, Presence.CONDITIONAL, references="trips.trip_id"),
        FieldSpec("from_trip_id", FieldType.ID, Presence.CONDITIONAL, references="trips.trip_id"),
        FieldSpec(
            "to_deadhead_id",
            FieldType.ID,
            Presence.CONDITIONAL,
            references="deadheads.deadhead_id",
        ),
        FieldSpec(
            "from_deadhead_id",
            FieldType.ID,
            Presence.CONDITIONAL,
            references="deadheads.deadhead_id",
        ),
    ),
)

OPS_LOCATIONS_V1 = TableSpec(
    filename="ops_locations.txt",
    kind="tods",
    spec_anchor="#ops_locationstxt",
    spec_version=SPEC_VERSION_V1,
    fields=(
        FieldSpec("ops_location_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("ops_location_code", FieldType.TEXT, Presence.OPTIONAL),
        FieldSpec("ops_location_name", FieldType.TEXT, Presence.REQUIRED),
        FieldSpec("ops_location_desc", FieldType.TEXT, Presence.OPTIONAL),
        FieldSpec("ops_location_lat", FieldType.LATITUDE, Presence.REQUIRED),
        FieldSpec("ops_location_lon", FieldType.LONGITUDE, Presence.REQUIRED),
    ),
)

DEADHEAD_TIMES_V1 = TableSpec(
    filename="deadhead_times.txt",
    kind="tods",
    spec_anchor="#deadhead_timestxt",
    spec_version=SPEC_VERSION_V1,
    fields=(
        FieldSpec(
            "deadhead_id",
            FieldType.ID,
            Presence.REQUIRED,
            references="deadheads.deadhead_id",
        ),
        FieldSpec("arrival_time", FieldType.TIME, Presence.REQUIRED),
        FieldSpec("departure_time", FieldType.TIME, Presence.REQUIRED),
        FieldSpec(
            "ops_location_id",
            FieldType.ID,
            Presence.CONDITIONAL,
            references="ops_locations.ops_location_id",
        ),
        FieldSpec("stop_id", FieldType.ID, Presence.CONDITIONAL, references="stops.stop_id"),
        FieldSpec("location_sequence", FieldType.NON_NEGATIVE_INTEGER, Presence.REQUIRED),
        FieldSpec("shape_dist_traveled", FieldType.NON_NEGATIVE_FLOAT, Presence.OPTIONAL),
    ),
)

RUNS_PIECES_V1 = TableSpec(
    filename="runs_pieces.txt",
    kind="tods",
    spec_anchor="#runs_piecestxt",
    spec_version=SPEC_VERSION_V1,
    # Spec: "The piece_id field must be unique." -- the only place a v1.0.0
    # field description states a uniqueness constraint in so many words.
    primary_key=("piece_id",),
    fields=(
        FieldSpec("run_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("piece_id", FieldType.ID, Presence.REQUIRED),
        # 0 Deadhead, 1 Trip, 2 Event.
        FieldSpec("start_type", FieldType.ENUM, Presence.REQUIRED, enum_values=("0", "1", "2")),
        # References deadheads.deadhead_id or trips.trip_id, per which start_type.
        FieldSpec("start_trip_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("start_trip_position", FieldType.NON_NEGATIVE_INTEGER, Presence.OPTIONAL),
        FieldSpec("end_type", FieldType.ENUM, Presence.REQUIRED, enum_values=("0", "1", "2")),
        FieldSpec("end_trip_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("end_trip_position", FieldType.NON_NEGATIVE_INTEGER, Presence.OPTIONAL),
    ),
)

RUN_EVENTS_V1 = TableSpec(
    filename="run_events.txt",
    kind="tods",
    spec_anchor="#run_eventstxt",
    spec_version=SPEC_VERSION_V1,
    fields=(
        FieldSpec("run_event_id", FieldType.ID, Presence.REQUIRED),
        FieldSpec("piece_id", FieldType.ID, Presence.REQUIRED, references="runs_pieces.piece_id"),
        # 0 Report Time, 1 Pre-Trip Activity, 2 Post-Trip Activity, 3 Fueling,
        # 4 Break, 5 Availability, 6 Activity, 7 Other.
        FieldSpec(
            "event_type",
            FieldType.ENUM,
            Presence.REQUIRED,
            enum_values=("0", "1", "2", "3", "4", "5", "6", "7"),
        ),
        FieldSpec("event_name", FieldType.TEXT, Presence.OPTIONAL),
        FieldSpec("event_time", FieldType.TIME, Presence.REQUIRED),
        FieldSpec("event_duration", FieldType.NON_NEGATIVE_INTEGER, Presence.REQUIRED),
        # 0 Operational Location, 1 Stop.
        FieldSpec(
            "event_from_location_type",
            FieldType.ENUM,
            Presence.OPTIONAL,
            enum_values=("", "0", "1"),
        ),
        # References ops_locations.ops_location_id or stops.stop_id.
        FieldSpec("event_from_location_id", FieldType.ID, Presence.OPTIONAL),
        FieldSpec(
            "event_to_location_type",
            FieldType.ENUM,
            Presence.OPTIONAL,
            enum_values=("", "0", "1"),
        ),
        FieldSpec("event_to_location_id", FieldType.ID, Presence.OPTIONAL),
    ),
)

# Spec (v1.0.0), "Dataset Files": all five files, all optional.
TABLES_V1: dict[str, TableSpec] = {
    t.filename: t
    for t in (
        DEADHEADS_V1,
        OPS_LOCATIONS_V1,
        DEADHEAD_TIMES_V1,
        RUNS_PIECES_V1,
        RUN_EVENTS_V1,
    )
}

# Selects the table inventory to validate against for a given --spec-version.
TABLES_BY_VERSION: dict[str, dict[str, TableSpec]] = {
    SPEC_VERSION_V1: TABLES_V1,
    SPEC_VERSION: TABLES,
}


def tables_for_version(spec_version: str) -> dict[str, TableSpec]:
    """The file/field inventory to validate against for ``spec_version``.

    Raises KeyError for an unsupported version; callers should validate
    against SUPPORTED_SPEC_VERSIONS first (the CLI does, in _check_spec_version).
    """
    return TABLES_BY_VERSION[spec_version]


# GTFS files that may sit alongside TODS files in the same package. Their
# presence is normal and they are never validated here.
GTFS_FILENAMES: frozenset[str] = frozenset(
    {
        "agency.txt",
        "stops.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
        "calendar.txt",
        "calendar_dates.txt",
        "fare_attributes.txt",
        "fare_rules.txt",
        "timeframes.txt",
        "rider_categories.txt",
        "fare_media.txt",
        "fare_products.txt",
        "fare_leg_rules.txt",
        "fare_leg_join_rules.txt",
        "fare_transfer_rules.txt",
        "areas.txt",
        "stop_areas.txt",
        "networks.txt",
        "route_networks.txt",
        "shapes.txt",
        "frequencies.txt",
        "transfers.txt",
        "pathways.txt",
        "levels.txt",
        "location_groups.txt",
        "location_group_stops.txt",
        "locations.geojson",
        "booking_rules.txt",
        "translations.txt",
        "feed_info.txt",
        "attributions.txt",
    }
)


def spec_link(table: TableSpec) -> str:
    base = SPEC_URL_V1 if table.spec_version == SPEC_VERSION_V1 else SPEC_URL
    return f"{base}{table.spec_anchor}"


__all__ = [
    "GTFS_COMPANION_FILENAMES",
    "GTFS_FIELDS",
    "GTFS_FILENAMES",
    "GTFS_PRIMARY_KEYS",
    "GTFS_REQUIRED_FIELDS",
    "SPEC_URL",
    "SPEC_URL_V1",
    "SPEC_VERSION",
    "SPEC_VERSION_V1",
    "SUPPORTED_SPEC_VERSIONS",
    "TABLES",
    "TABLES_BY_VERSION",
    "TABLES_V1",
    "FieldSpec",
    "FieldType",
    "Presence",
    "TableSpec",
    "spec_link",
    "tables_for_version",
]
