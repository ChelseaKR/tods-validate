"""Differential property test: the two supplement call sites must agree.

`gtfs_companion.merge_supplement` (feeds `build_companion`, the validation
view) and `merge._merge_file` (the materialized "TODS-Supplemented GTFS")
both consume the shared engine in `supplement.py`. This test generates
random base + supplement feeds and asserts the two call sites can never
disagree about which primary keys survive or what their values are.

CI intent is >=10k cases; `max_examples` here is sized down for a fast
committed test run.
"""

from __future__ import annotations

import csv
import io
import itertools

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tods_validate.gtfs_companion import merge_supplement
from tods_validate.loader import FeedFile, Package, Row
from tods_validate.merge import MergeStats, _merge_file
from tods_validate.schema import GTFS_PRIMARY_KEYS

_DATA_FIELDS = ("field_a", "field_b")
_VALUE_POOL = ("", "a", "b", "x1")


def _key_pool(pk_len: int) -> list[tuple[str, ...]]:
    values = ("k0", "k1", "k2", "")  # "" produces a blank-PK case (skip/drop)
    return list(itertools.product(values, repeat=pk_len))


def _row_values(pk: tuple[str, ...], key: tuple[str, ...], data: tuple[str, ...]) -> dict[str, str]:
    values = dict(zip(pk, key, strict=True))
    values.update(zip(_DATA_FIELDS, data, strict=True))
    return values


@st.composite
def _worlds(draw: st.DrawFn) -> tuple[str, tuple[str, ...], FeedFile | None, FeedFile]:
    base_name = draw(st.sampled_from(sorted(GTFS_PRIMARY_KEYS)))
    pk = GTFS_PRIMARY_KEYS[base_name]
    keys = _key_pool(len(pk))
    headers = pk + _DATA_FIELDS

    row_strategy = st.tuples(
        st.sampled_from(keys), st.tuples(*(st.sampled_from(_VALUE_POOL) for _ in _DATA_FIELDS))
    )

    include_base = draw(st.booleans())
    base: FeedFile | None = None
    if include_base:
        base_rows_raw = draw(st.lists(row_strategy, max_size=5))
        base = FeedFile(
            name=base_name,
            headers=headers,
            rows=[
                Row(line=i + 2, values=_row_values(pk, key, data))
                for i, (key, data) in enumerate(base_rows_raw)
            ],
        )

    supp_row_strategy = st.tuples(
        st.sampled_from(keys),
        st.tuples(*(st.sampled_from(_VALUE_POOL) for _ in _DATA_FIELDS)),
        st.sampled_from(("", "1")),  # TODS_delete
    )
    supp_rows_raw = draw(st.lists(supp_row_strategy, max_size=5))
    supplement_name = base_name.removesuffix(".txt") + "_supplement.txt"
    supplement_rows = []
    for i, (key, data, delete) in enumerate(supp_rows_raw):
        values = _row_values(pk, key, data)
        values["TODS_delete"] = delete
        supplement_rows.append(Row(line=i + 2, values=values))
    supplement = FeedFile(
        name=supplement_name,
        headers=headers + ("TODS_delete",),
        rows=supplement_rows,
    )

    return base_name, pk, base, supplement


@settings(max_examples=750, suppress_health_check=[HealthCheck.too_slow])
@given(_worlds())
def test_companion_and_merge_paths_agree(
    world: tuple[str, tuple[str, ...], FeedFile | None, FeedFile],
) -> None:
    base_name, pk, base, supplement = world

    # Path 1: the validation view (build_companion delegates to this).
    companion_effective = merge_supplement(base, supplement, pk)

    # Path 2: the materialized merge.
    gtfs = Package(source="gtfs", files=({base_name: base} if base is not None else {}))
    tods = Package(source="tods", files={supplement.name: supplement})
    stats = MergeStats()
    merged_bytes = _merge_file(base_name, gtfs, tods, stats)
    assert merged_bytes is not None  # supplement is always present here

    reader = csv.reader(io.StringIO(merged_bytes.decode("utf-8")))
    header = next(reader)
    merged_effective: dict[tuple[str, ...], dict[str, str]] = {}
    for line in reader:
        values = dict(zip(header, line, strict=True))
        key = tuple(values.get(f, "") for f in pk)
        merged_effective[key] = values

    # The validation view and the materialized merge must never disagree on
    # which keys survive...
    assert set(companion_effective) == set(merged_effective)

    # ...nor on the value of any field common to both representations.
    for key, companion_row in companion_effective.items():
        merged_row = merged_effective[key]
        for field, value in companion_row.items():
            assert merged_row.get(field, "") == value
