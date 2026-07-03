"""The curated read namespace (tods_validate.read)."""

from conftest import VALID_GTFS, VALID_TODS
from tods_validate.read import (
    CompanionGTFS,
    Package,
    build_companion,
    load_package,
    merge_supplement,
    to_rows,
)


def test_curated_names_import() -> None:
    # Import already succeeded above; assert the names are the same objects
    # the loader/gtfs_companion modules define (a thin re-export, not a copy).
    from tods_validate.gtfs_companion import CompanionGTFS as _CompanionGTFS
    from tods_validate.gtfs_companion import build_companion as _build_companion
    from tods_validate.gtfs_companion import merge_supplement as _merge_supplement
    from tods_validate.loader import Package as _Package
    from tods_validate.loader import load_package as _load_package

    assert CompanionGTFS is _CompanionGTFS
    assert Package is _Package
    assert build_companion is _build_companion
    assert load_package is _load_package
    assert merge_supplement is _merge_supplement


def test_to_rows_of_none_is_empty_list() -> None:
    assert to_rows(None) == []


def test_to_rows_tabulates_known_fixture_feed() -> None:
    tods = load_package(VALID_TODS)
    feed = tods.get("vehicles.txt")
    assert feed is not None
    rows = to_rows(feed)
    assert rows == [dict(r.values) for r in feed.rows]
    assert rows[0] == {
        "vehicle_id": "bus-1",
        "vehicle_label": "Old Reliable",
        "license_plate": "OR-E285104",
    }


def test_usage_example_runs_end_to_end_on_fixtures() -> None:
    tods = load_package(VALID_TODS)
    gtfs = load_package(VALID_GTFS)
    companion = build_companion(gtfs, tods, source=tods.source)
    assert isinstance(companion, CompanionGTFS)
    assert companion.stop_ids
    rows = to_rows(tods.get("vehicles.txt"))
    assert rows
