"""Curated read API: load TODS/GTFS packages without running the validator.

For callers who want the parsed feed data itself (a report generator, a
notebook, a data pipeline) rather than validation findings:

    from tods_validate.read import load_package, build_companion, to_rows

    tods = load_package("exports/tods")
    gtfs = load_package("exports/gtfs")
    companion = build_companion(gtfs, tods, source=tods.source)
    rows = to_rows(tods.get("vehicles.txt"))

This module re-exports the existing loader and GTFS-companion surface under
one namespace, plus a small pandas-free tabulation helper. It carries the
project's semantic-versioning promise: fields are only added within a major
version, never removed or renamed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .gtfs_companion import CompanionGTFS, build_companion, merge_supplement
from .loader import FeedFile, Package, PackageNotFoundError, Row, load_package

if TYPE_CHECKING:
    import pandas as pd


def to_rows(feed: FeedFile | None) -> list[dict[str, str]]:
    """Tabulate a :class:`FeedFile` as a list of plain dicts, one per row.

    A pandas-free view for callers who just want the values; returns ``[]``
    when ``feed`` is ``None`` (a file that was not present in the package).
    """
    if feed is None:
        return []
    return [dict(r.values) for r in feed.rows]


def to_dataframe(feed: FeedFile | None) -> pd.DataFrame:
    """Tabulate a :class:`FeedFile` as a pandas ``DataFrame``.

    Requires the ``dataframe`` extra (``pip install tods-validate[dataframe]``).
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "to_dataframe() requires pandas; install it with "
            "`pip install tods-validate[dataframe]`."
        ) from exc
    return pd.DataFrame(to_rows(feed))


__all__ = [
    "CompanionGTFS",
    "FeedFile",
    "Package",
    "PackageNotFoundError",
    "Row",
    "build_companion",
    "load_package",
    "merge_supplement",
    "to_dataframe",
    "to_rows",
]
