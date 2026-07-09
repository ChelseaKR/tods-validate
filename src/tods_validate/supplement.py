"""Shared supplement-evaluation engine.

Both the validator's companion GTFS view (`gtfs_companion.merge_supplement`)
and the materialized merge (`merge._merge_file`) need to answer the same
question: given a base GTFS file and its TODS supplement, what is the
effective set of rows? This module is the single implementation of the
spec's "Supplement Files > Evaluation" section so the two call sites can
never independently drift:

1. PK matches and TODS_delete == "1": remove the row.
2. PK matches otherwise: non-empty supplement values overwrite base values.
3. PK does not match: add the whole row (minus TODS_delete).

Rows (base or supplement) whose primary-key fields are blank or missing
cannot be addressed, so they are excluded from the effective set. Blank-PK
*base* rows are silently dropped (the field rules report those problems on
the base file itself); blank-PK *supplement* rows are counted in
``skipped`` (the field rules report those on the supplement file).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .loader import FeedFile

_DELETE_FIELD = "TODS_delete"


@dataclass
class SupplementResult:
    """Effective rows after applying a supplement, plus provenance counts."""

    # Keyed by primary key; base order first, then supplement-add order,
    # preserved via dict insertion order.
    rows: dict[tuple[str, ...], dict[str, str]] = field(default_factory=dict)
    updated: int = 0
    added: int = 0
    deleted: int = 0
    skipped: int = 0  # supplement rows with blank primary-key fields


def _primary_key(values: dict[str, str], primary_key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(values.get(field, "") for field in primary_key)


def _has_blank_key(key: tuple[str, ...]) -> bool:
    return any(value == "" for value in key)


def _load_base_rows(
    result: SupplementResult, base: FeedFile | None, primary_key: tuple[str, ...]
) -> None:
    if base is None:
        return

    for row in base.rows:
        key = _primary_key(row.values, primary_key)
        if _has_blank_key(key):
            continue
        result.rows[key] = dict(row.values)


def _overlay_non_empty_values(target: dict[str, str], values: dict[str, str]) -> None:
    for name, value in values.items():
        if name == _DELETE_FIELD or value == "":
            continue
        target[name] = value


def _apply_addressable_row(
    result: SupplementResult, key: tuple[str, ...], values: dict[str, str]
) -> None:
    if values.get(_DELETE_FIELD, "") == "1":
        if result.rows.pop(key, None) is not None:
            result.deleted += 1
        return

    if key in result.rows:
        _overlay_non_empty_values(result.rows[key], values)
        result.updated += 1
        return

    result.rows[key] = {name: value for name, value in values.items() if name != _DELETE_FIELD}
    result.added += 1


def apply_supplement(
    base: FeedFile | None,
    supplement: FeedFile | None,
    primary_key: tuple[str, ...],
) -> SupplementResult:
    """Compute the effective rows of ``base`` with ``supplement`` applied."""
    result = SupplementResult()
    _load_base_rows(result, base, primary_key)

    if supplement is not None:
        for row in supplement.rows:
            key = _primary_key(row.values, primary_key)
            if _has_blank_key(key):
                result.skipped += 1
                continue
            _apply_addressable_row(result, key, row.values)

    return result
