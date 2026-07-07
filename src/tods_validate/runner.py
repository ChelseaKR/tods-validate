"""Glue between the loader, the companion GTFS feed, and the rules.

Used by both the CLI and the test suite so they exercise identical behavior.
"""

from __future__ import annotations

from pathlib import Path

from .findings import Finding
from .gtfs_companion import build_companion
from .loader import Package, load_package
from .rules import RunCoverage, ValidationContext, validate
from .schema import GTFS_FILENAMES


def run_with_coverage(
    path: str | Path,
    gtfs_path: str | Path | None = None,
    *,
    enabled: frozenset[str] = frozenset(),
    encoding: str | None = None,
) -> tuple[Package, list[Finding], RunCoverage]:
    """Load and validate the TODS package at ``path``.

    Like :func:`run`, but also returns the :class:`RunCoverage` manifest that
    records which rules ran versus were skipped. Callers that surface a report
    use this so the report can state its own scope.

    When ``gtfs_path`` is given, references are resolved against that feed.
    Otherwise, if GTFS files sit next to the TODS files, the package is used
    as its own companion feed.

    ``enabled`` turns on opt-in rules (rule IDs or category names). ``encoding``
    overrides the default UTF-8 decoding for non-conforming exports.
    """
    package = load_package(path, encoding=encoding)
    gtfs = None
    gtfs_source = None
    if gtfs_path is not None:
        gtfs_package = load_package(gtfs_path, encoding=encoding)
        gtfs = build_companion(gtfs_package, package, source=str(gtfs_path))
        gtfs_source = "flag"
    elif any(name in GTFS_FILENAMES for name in package.files):
        gtfs = build_companion(package, package, source=package.source)
        gtfs_source = "package"
    context = ValidationContext(package=package, gtfs=gtfs, gtfs_source=gtfs_source)
    findings, coverage = validate(context, enabled)
    return package, findings, coverage


def run(
    path: str | Path,
    gtfs_path: str | Path | None = None,
    *,
    enabled: frozenset[str] = frozenset(),
    encoding: str | None = None,
) -> tuple[Package, list[Finding]]:
    """Load and validate the TODS package at ``path``; return package + findings.

    A thin wrapper over :func:`run_with_coverage` that drops the coverage
    manifest, for the many callers that only need the findings.
    """
    package, findings, _ = run_with_coverage(path, gtfs_path, enabled=enabled, encoding=encoding)
    return package, findings
