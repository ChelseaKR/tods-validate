"""Glue between the loader, the companion GTFS feed, and the rules.

Used by both the CLI and the test suite so they exercise identical behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from .findings import Finding, Severity
from .gtfs_companion import build_companion
from .loader import Package, load_package
from .rules import RunCoverage, ValidationContext, validate
from .schema import GTFS_FILENAMES, SPEC_VERSION

# Root rule IDs and the rule IDs whose findings on that same row are downstream
# echoes rather than independent data problems. A ragged row (TODS-E104) can
# leave required fields blank and also trip TODS-E201; an exact employee
# assignment duplicate now trips E204 while retaining W408 for compatibility.
# See _link_causality.
_CASCADE_LINKS: dict[str, frozenset[str]] = {
    "TODS-E104": frozenset({"TODS-E201"}),
    # W408 is kept as a machine-compatible alias for the now-explicit E204
    # employee assignment primary-key violation. Human reports collapse it.
    "TODS-E204": frozenset({"TODS-W408"}),
}


def _apply_severity_remap(
    findings: list[Finding], severity_remap: Mapping[str, str]
) -> list[Finding]:
    """Apply a rule_id -> severity-name remap, recording each original severity.

    Kept as one place so every caller of ``run()`` (CLI, API, tests) inherits
    identical remap behavior, and so every downstream renderer sees
    ``severity_original`` set consistently for disclosure (see report.py).
    """
    if not severity_remap:
        return findings
    remapped: list[Finding] = []
    for finding in findings:
        new_level = severity_remap.get(finding.rule_id)
        if new_level is None:
            remapped.append(finding)
            continue
        new_severity = Severity[new_level.upper()] if isinstance(new_level, str) else new_level
        if new_severity == finding.severity:
            remapped.append(finding)
            continue
        remapped.append(replace(finding, severity=new_severity, severity_original=finding.severity))
    return remapped


def run_with_coverage(
    path: str | Path,
    gtfs_path: str | Path | None = None,
    *,
    enabled: frozenset[str] = frozenset(),
    encoding: str | None = None,
    severity_remap: Mapping[str, str] | None = None,
    spec_version: str = SPEC_VERSION,
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
    ``severity_remap`` maps rule ID -> severity name ("ERROR"/"WARNING"/"INFO"),
    applied to findings after validation; see ``config.py``'s ``[severity]``
    table for how it is populated and disclosed. ``spec_version`` selects the
    TODS spec version to validate against (schema.SUPPORTED_SPEC_VERSIONS);
    see docs/spec-versions.md for what changes between versions.
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
    context = ValidationContext(
        package=package, gtfs=gtfs, gtfs_source=gtfs_source, spec_version=spec_version
    )
    findings, coverage = validate(context, enabled)
    findings = _apply_severity_remap(findings, severity_remap or {})
    return package, _link_causality(findings), coverage


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
    roots: dict[tuple[str | None, int | None, str], str] = {}
    for f in findings:
        if f.rule_id in _CASCADE_LINKS:
            pointer = f.pointer()
            if pointer is not None:
                for echo_rule in _CASCADE_LINKS[f.rule_id]:
                    roots.setdefault((f.file, f.row, echo_rule), pointer)
    if not roots:
        return findings
    return [
        replace(f, caused_by=roots[(f.file, f.row, f.rule_id)])
        if (f.file, f.row, f.rule_id) in roots
        else f
        for f in findings
    ]


def run(
    path: str | Path,
    gtfs_path: str | Path | None = None,
    *,
    enabled: frozenset[str] = frozenset(),
    encoding: str | None = None,
    severity_remap: Mapping[str, str] | None = None,
    spec_version: str = SPEC_VERSION,
) -> tuple[Package, list[Finding]]:
    """Load and validate the TODS package at ``path``; return package + findings.

    A thin wrapper over :func:`run_with_coverage` that drops the coverage
    manifest, for the many callers that only need the findings.
    """
    package, findings, _ = run_with_coverage(
        path,
        gtfs_path,
        enabled=enabled,
        encoding=encoding,
        severity_remap=severity_remap,
        spec_version=spec_version,
    )
    return package, findings
