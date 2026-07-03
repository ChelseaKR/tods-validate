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


def apply_supplement(
    base: FeedFile | None,
    supplement: FeedFile | None,
    primary_key: tuple[str, ...],
) -> SupplementResult:
    """Compute the effective rows of ``base`` with ``supplement`` applied."""
    result = SupplementResult()
    rows = result.rows

    if base is not None:
        for row in base.rows:
            key = tuple(row.values.get(f, "") for f in primary_key)
            if any(v == "" for v in key):
                continue
            rows[key] = dict(row.values)

    if supplement is not None:
        for row in supplement.rows:
            key = tuple(row.values.get(f, "") for f in primary_key)
            if any(v == "" for v in key):
                result.skipped += 1
                continue
            if row.values.get("TODS_delete", "") == "1":
                if rows.pop(key, None) is not None:
                    result.deleted += 1
                continue
            if key in rows:
                target = rows[key]
                for name, value in row.values.items():
                    if name == "TODS_delete" or value == "":
                        continue
                    target[name] = value
                result.updated += 1
            else:
                rows[key] = {k: v for k, v in row.values.items() if k != "TODS_delete"}
                result.added += 1

    return result
