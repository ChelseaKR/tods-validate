"""Glue between the loader, the companion GTFS feed, and the rules.

Used by both the CLI and the test suite so they exercise identical behavior.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .findings import Finding
from .gtfs_companion import build_companion
from .loader import Package, load_package
from .rules import ValidationContext, validate
from .schema import GTFS_FILENAMES

# Rule ID that marks a structural "root cause" row, and the rule IDs whose
# findings on that same row are downstream echoes of it rather than
# independent data problems. A ragged row (TODS-E104) can leave trailing
# required fields blank simply because the short row has nothing to put
# there, which also trips TODS-E201 on that row -- a real finding, but not
# separate news. See _link_causality.
_CASCADE_ROOT_RULE = "TODS-E104"
_CASCADE_ECHO_RULES = frozenset({"TODS-E201"})


def run(
    path: str | Path,
    gtfs_path: str | Path | None = None,
    *,
    enabled: frozenset[str] = frozenset(),
    encoding: str | None = None,
) -> tuple[Package, list[Finding]]:
    """Load and validate the TODS package at ``path``.

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
    findings = validate(context, enabled)
    return package, _link_causality(findings)


def _link_causality(findings: list[Finding]) -> list[Finding]:
    """Tag findings that are structural echoes of a ragged row with its pointer.

    This never removes or reorders a finding -- every rule still fires exactly
    as it did before, so each fixture keeps tripping its own rule and machine
    formats keep every finding. It only sets ``caused_by`` so renderers can
    choose to collapse the echo under its root for a human reading the report.

    Deliberately decoupled from the rule modules: rules stay focused on what
    is wrong, not on what else that implies, and this pass runs once findings
    from every rule are known.
    """
    roots: dict[tuple[str | None, int | None], str] = {}
    for f in findings:
        if f.rule_id == _CASCADE_ROOT_RULE:
            pointer = f.pointer()
            if pointer is not None:
                roots.setdefault((f.file, f.row), pointer)
    if not roots:
        return findings
    return [
        replace(f, caused_by=roots[(f.file, f.row)])
        if f.rule_id in _CASCADE_ECHO_RULES and (f.file, f.row) in roots
        else f
        for f in findings
    ]
