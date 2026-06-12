"""Rule registry.

Rules are data plus a small check function, not a plugin framework. Each rule
has a stable ID, a severity, a spec citation, and a check that yields
findings. IDs keep the historical TODS- prefix and are grouped in bands:

- TODS-x1xx: package and file structure
- TODS-x2xx: field values within one file
- TODS-x3xx: references between files (including the companion GTFS feed)
- TODS-x4xx: semantic checks across rows

The letter encodes severity (E error, W warning, I info). IDs are never
reused or renumbered once released.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from ..findings import Finding, Severity
from ..gtfs_companion import CompanionGTFS
from ..loader import Package


@dataclass
class ValidationContext:
    package: Package
    gtfs: CompanionGTFS | None = None
    # "flag" if --gtfs was passed, "package" if GTFS files were found next to
    # the TODS files, None if no companion GTFS is available.
    gtfs_source: str | None = None


CheckFunction = Callable[[ValidationContext], Iterator[Finding]]


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    title: str
    # One- or two-sentence description for the rule catalog, written for feed
    # producers.
    description: str
    spec_section: str
    check: CheckFunction = field(compare=False)
    # Rules that resolve IDs into the companion GTFS feed are skipped when no
    # companion feed is available.
    needs_gtfs: bool = False


REGISTRY: list[Rule] = []


def rule(
    id: str,
    severity: Severity,
    title: str,
    description: str,
    spec_section: str,
    needs_gtfs: bool = False,
) -> Callable[[CheckFunction], CheckFunction]:
    """Register a check function. Used as a decorator in the rule modules."""

    def decorator(check: CheckFunction) -> CheckFunction:
        if any(r.id == id for r in REGISTRY):
            raise ValueError(f"duplicate rule id {id}")
        REGISTRY.append(
            Rule(
                id=id,
                severity=severity,
                title=title,
                description=description,
                spec_section=spec_section,
                check=check,
                needs_gtfs=needs_gtfs,
            )
        )
        return check

    return decorator


def validate(context: ValidationContext) -> list[Finding]:
    """Run every applicable rule and return findings in file/row order."""
    findings: list[Finding] = []
    for r in REGISTRY:
        if r.needs_gtfs and context.gtfs is None:
            continue
        findings.extend(r.check(context))
    findings.sort(key=lambda f: (f.file or "", f.row or 0, f.rule_id))
    return findings


def all_rules() -> Iterable[Rule]:
    return tuple(REGISTRY)


# Importing the rule modules populates the registry.
from . import fields, references, semantics, structure  # noqa: E402,F401

__all__ = [
    "REGISTRY",
    "Rule",
    "ValidationContext",
    "all_rules",
    "rule",
    "validate",
]
