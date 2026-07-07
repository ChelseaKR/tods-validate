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

from collections.abc import Callable, Collection, Iterable, Iterator
from dataclasses import dataclass, field, replace

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


REGISTRY: list[Rule] = []


# Per-rule outcomes recorded for the validation-assurance manifest. A green run
# should be able to state its own scope: which rules actually ran, and which
# were skipped and why. See RunCoverage.
STATUS_RAN = "ran"
STATUS_SKIPPED_NEEDS_GTFS = "skipped:needs_gtfs"
STATUS_SKIPPED_DISABLED = "skipped:disabled"
STATUS_SKIPPED_IGNORED = "skipped:ignored"

# Human-readable reason per status, for the one-line disclosure in reports.
_STATUS_REASON = {
    STATUS_SKIPPED_NEEDS_GTFS: "no companion GTFS feed was provided",
    STATUS_SKIPPED_DISABLED: "opt-in rule not enabled (use --enable)",
    STATUS_SKIPPED_IGNORED: "suppressed by local policy (--ignore)",
}


@dataclass(frozen=True)
class RuleOutcome:
    """Whether one rule ran during a validation, and why not if it did not."""

    id: str
    severity: Severity
    category: str
    status: str

    @property
    def ran(self) -> bool:
        return self.status == STATUS_RAN

    @property
    def reason(self) -> str | None:
        return _STATUS_REASON.get(self.status)


@dataclass(frozen=True)
class RunCoverage:
    """A validation-assurance manifest: what did and did not run.

    Every report can carry this so that a clean result is qualified by its own
    scope. ``outcomes`` holds one :class:`RuleOutcome` per registered rule that
    was considered for the run, in registry order.
    """

    outcomes: tuple[RuleOutcome, ...]

    @property
    def ran(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.outcomes if o.ran)

    @property
    def skipped(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.ran)

    def skipped_by_reason(self) -> dict[str, list[RuleOutcome]]:
        """Skipped rules grouped by status, in a stable status order."""
        grouped: dict[str, list[RuleOutcome]] = {}
        for status in (
            STATUS_SKIPPED_NEEDS_GTFS,
            STATUS_SKIPPED_DISABLED,
            STATUS_SKIPPED_IGNORED,
        ):
            members = [o for o in self.outcomes if o.status == status]
            if members:
                grouped[status] = members
        return grouped

    def with_ignored(self, ignore: Collection[str]) -> RunCoverage:
        """Return a copy in which rules suppressed by ``--ignore`` are disclosed.

        A rule that ran but whose findings were then dropped by ``--ignore`` is
        reclassified ``skipped:ignored`` so the report still admits its findings
        were withheld. Rules skipped for other reasons keep that reason.
        """
        if not ignore:
            return self
        ignore = set(ignore)
        return RunCoverage(
            tuple(
                replace(o, status=STATUS_SKIPPED_IGNORED) if o.ran and o.id in ignore else o
                for o in self.outcomes
            )
        )

    def to_dict(self) -> dict[str, object]:
        """The additive ``coverage`` block emitted in the JSON report."""
        skipped = self.skipped
        return {
            "total": len(self.outcomes),
            "ran": len(self.ran),
            "skipped": len(skipped),
            "skippedByReason": {
                status: [o.id for o in members]
                for status, members in self.skipped_by_reason().items()
            },
            "rules": [
                {
                    "id": o.id,
                    "severity": o.severity.name,
                    "category": o.category,
                    "status": o.status,
                }
                for o in self.outcomes
            ],
        }

    def summary_line(self) -> str | None:
        """One line disclosing skipped checks, or None when everything ran."""
        groups = self.skipped_by_reason()
        if not groups:
            return None
        parts = [f"{len(members)} {_STATUS_REASON[status]}" for status, members in groups.items()]
        return "Checks skipped: " + "; ".join(parts) + "."


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
            )
        )
        return check

    return decorator


def _is_enabled(r: Rule, enabled: frozenset[str]) -> bool:
    if r.default_enabled:
        return True
    return r.id in enabled or r.category in enabled


def _rule_status(r: Rule, context: ValidationContext, enabled: frozenset[str]) -> str:
    if r.needs_gtfs and context.gtfs is None:
        return STATUS_SKIPPED_NEEDS_GTFS
    if not _is_enabled(r, enabled):
        return STATUS_SKIPPED_DISABLED
    return STATUS_RAN


def validate(
    context: ValidationContext, enabled: frozenset[str] = frozenset()
) -> tuple[list[Finding], RunCoverage]:
    """Run every applicable rule; return its findings and a coverage manifest.

    Findings come back in file/row order. The :class:`RunCoverage` records, for
    every registered rule, whether it ran or was skipped and why, so a report
    can state its own scope instead of implying a clean run checked everything.

    ``enabled`` additionally turns on opt-in rules: it may contain rule IDs or
    category names ("coverage", "advisory", "experimental").
    """
    findings: list[Finding] = []
    outcomes: list[RuleOutcome] = []
    for r in REGISTRY:
        status = _rule_status(r, context, enabled)
        outcomes.append(
            RuleOutcome(id=r.id, severity=r.severity, category=r.category, status=status)
        )
        if status == STATUS_RAN:
            findings.extend(r.check(context))
    findings.sort(key=lambda f: (f.file or "", f.row or 0, f.rule_id))
    return findings, RunCoverage(tuple(outcomes))


def all_rules() -> Iterable[Rule]:
    return tuple(REGISTRY)


# Importing the rule modules populates the registry.
from . import coverage, fields, references, semantics, structure  # noqa: E402,F401

__all__ = [
    "REGISTRY",
    "Rule",
    "RuleOutcome",
    "RunCoverage",
    "ValidationContext",
    "all_rules",
    "rule",
    "validate",
]
