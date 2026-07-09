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
from functools import cached_property

from .. import run_events
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

    # Derived views over run_events.txt, computed once per validation and
    # cached on this instance (it is created once per validate() call and
    # shared by every rule; see runner.run()). Parsing lives in
    # tods_validate.run_events, not here, so it stays outside mutmut's
    # rules/*-scoped mutated set — see that module's docstring.
    @cached_property
    def events(self) -> list[run_events._Event]:
        return run_events.parse_events(self.package)

    @cached_property
    def events_by_run(self) -> dict[tuple[str, str], list[run_events._Event]]:
        return run_events.events_by_run(self.events)

    @cached_property
    def run_pairs(self) -> set[tuple[str, str]]:
        return set(self.events_by_run.keys())


CheckFunction = Callable[[ValidationContext], Iterator[Finding]]


# Categories group rules by how aggressively they fire. "core" rules check the
# spec and run by default. "coverage" and "advisory" rules are opt-in (see
# default_enabled) because they surface judgement calls, not spec violations,
# and would be noise in a default CI gate.
CATEGORIES = ("core", "coverage", "advisory", "experimental")


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
    # See CATEGORIES.
    category: str = "core"
    # Opt-in rules (default_enabled=False) run only when their ID or category
    # is passed to validate()/--enable.
    default_enabled: bool = True
    # Where the spec is ambiguous, how this rule resolves it (e.g. "permissive:
    # accepts GTFS times beyond 24:00:00"). Surfaced in `rules --format json`
    # so consumers can audit interpretation choices. None when unambiguous.
    interpretation: str | None = None
    # A short "Before: ... / After: ..." worked fix example, written for feed
    # producers. Set on the highest-frequency rules; None elsewhere.
    example: str | None = None


REGISTRY: list[Rule] = []


def rule(
    id: str,
    severity: Severity,
    title: str,
    description: str,
    spec_section: str,
    needs_gtfs: bool = False,
    category: str = "core",
    default_enabled: bool = True,
    interpretation: str | None = None,
    example: str | None = None,
) -> Callable[[CheckFunction], CheckFunction]:
    """Register a check function. Used as a decorator in the rule modules."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown rule category {category!r}")

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
                category=category,
                default_enabled=default_enabled,
                interpretation=interpretation,
                example=example,
            )
        )
        return check

    return decorator


def _is_enabled(r: Rule, enabled: frozenset[str]) -> bool:
    if r.default_enabled:
        return True
    return r.id in enabled or r.category in enabled


def validate(context: ValidationContext, enabled: frozenset[str] = frozenset()) -> list[Finding]:
    """Run every applicable rule and return findings in file/row order.

    ``enabled`` additionally turns on opt-in rules: it may contain rule IDs or
    category names ("coverage", "advisory", "experimental").
    """
    findings: list[Finding] = []
    for r in REGISTRY:
        if r.needs_gtfs and context.gtfs is None:
            continue
        if not _is_enabled(r, enabled):
            continue
        findings.extend(r.check(context))
    findings.sort(key=lambda f: (f.file or "", f.row or 0, f.rule_id))
    return findings


def all_rules() -> Iterable[Rule]:
    return tuple(REGISTRY)


# Importing the rule modules populates the registry.
from . import coverage, fields, references, semantics, structure  # noqa: E402,F401

__all__ = [
    "REGISTRY",
    "Rule",
    "ValidationContext",
    "all_rules",
    "rule",
    "validate",
]
