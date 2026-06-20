"""Table and field definitions for TODS v2.1.0.

Transcribed by hand from the spec reference at https://tods-transit.org/spec/
(source: https://github.com/MobilityData/transit-operational-data-standard,
docs/en/spec/index.md, "last updated on 2025-04-16 (v2.1.0)").

The standard was known as the Operational Data Standard (ODS) before v2.0;
rule IDs in this validator keep the TODS- prefix.

Each definition carries a citation to the spec section it came from. If the
spec and this file disagree, the spec wins; please open an issue.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

SPEC_VERSION = "2.1.0"
# Spec versions this validator can be asked to target via --spec-version. Only
# 2.1.0 is implemented today; the flag exists so feeds and CI can be explicit
# and so a mismatch fails loudly rather than validating against the wrong text.
SUPPORTED_SPEC_VERSIONS = ("2.1.0",)
SPEC_URL = "https://tods-transit.org/spec/"


class FieldType(Enum):
    ID = "ID"
    TEXT = "Text"
    ENUM = "Enum"
    TIME = "Time"
    DATE = "Date"
    NON_NEGATIVE_INTEGER = "Non-negative integer"


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
    # Spec section anchor under SPEC_URL.
    spec_anchor: str
    # Primary key field names. None means the spec defines no uniqueness
    # constraint (spec: employee_run_dates.txt "Primary Key: *").
    primary_key: tuple[str, ...] | None = None
    fields: tuple[FieldSpec, ...] = ()
    # For supplement files: the GTFS file this supplements.
    gtfs_base: str | None = None


# ---------------------------------------------------------------------------
# GTFS base-file inventories, used to check supplement file headers.
#
# Supplement files carry "fields match those defined in the corresponding
# file's GTFS specification" (spec, "Supplement Files > Structure"), plus the
# TODS_-prefixed fields below. Field name lists transcribed from the GTFS
# reference, https://gtfs.org/documentation/schedule/reference/ — names only;
# this validator does not re-validate GTFS semantics.
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

# Spec, "Supplement Files > TODS-Specific Fields".
TODS_DELETE = FieldSpec("TODS_delete", FieldType.ENUM, Presence.OPTIONAL, enum_values=("", "1"))


def _supplement(filename: str, gtfs_base: str, extra: tuple[FieldSpec, ...] = ()) -> TableSpec:
    pk = GTFS_PRIMARY_KEYS[gtfs_base]
    key_fields = tuple(FieldSpec(name, FieldType.ID, Presence.REQUIRED) for name in pk)
    other_fields = tuple(
        FieldSpec(name, FieldType.TEXT, Presence.OPTIONAL)
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
    # Spec: "Primary Key: *" — runs may legitimately appear multiple times
    # (multiple employees on the same run on the same date).
    primary_key=None,
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
ROUTES_SUPPLEMENT = _supplement("routes_supplement.txt", "routes.txt")
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
    return f"{SPEC_URL}{table.spec_anchor}"


__all__ = [
    "GTFS_FIELDS",
    "GTFS_FILENAMES",
    "GTFS_PRIMARY_KEYS",
    "SPEC_URL",
    "SPEC_VERSION",
    "SUPPORTED_SPEC_VERSIONS",
    "TABLES",
    "FieldSpec",
    "FieldType",
    "Presence",
    "TableSpec",
    "spec_link",
]
