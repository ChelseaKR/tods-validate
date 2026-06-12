"""Glue between the loader, the companion GTFS feed, and the rules.

Used by both the CLI and the test suite so they exercise identical behavior.
"""

from __future__ import annotations

from pathlib import Path

from .findings import Finding
from .gtfs_companion import build_companion
from .loader import Package, load_package
from .rules import ValidationContext, validate
from .schema import GTFS_FILENAMES


def run(path: str | Path, gtfs_path: str | Path | None = None) -> tuple[Package, list[Finding]]:
    """Load and validate the TODS package at ``path``.

    When ``gtfs_path`` is given, references are resolved against that feed.
    Otherwise, if GTFS files sit next to the TODS files, the package is used
    as its own companion feed.
    """
    package = load_package(path)
    gtfs = None
    gtfs_source = None
    if gtfs_path is not None:
        gtfs_package = load_package(gtfs_path)
        gtfs = build_companion(gtfs_package, package, source=str(gtfs_path))
        gtfs_source = "flag"
    elif any(name in GTFS_FILENAMES for name in package.files):
        gtfs = build_companion(package, package, source=package.source)
        gtfs_source = "package"
    context = ValidationContext(package=package, gtfs=gtfs, gtfs_source=gtfs_source)
    return package, validate(context)
