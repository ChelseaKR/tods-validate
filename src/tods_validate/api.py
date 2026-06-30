"""Public, stable Python API.

For callers who want to validate a feed in-process instead of shelling out to
the CLI (for example, a TODS exporter's test suite):

    from tods_validate import validate_feed

    result = validate_feed("exports/tods", gtfs="exports/gtfs.zip")
    if result.error_count:
        for finding in result.errors:
            print(finding.rule_id, finding.location(), finding.message)

The shapes here (``ValidationResult``, ``Finding``, ``Severity``) follow the
project's semantic-versioning promise: fields are only added within a major
version, never removed or renamed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .findings import Finding, Severity
from .runner import run
from .suggest import Suggestion, suggest_for_findings


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of validating one feed."""

    source: str
    findings: list[Finding]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.INFO]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def counts(self) -> Counter[Severity]:
        return Counter(f.severity for f in self.findings)

    @property
    def ok(self) -> bool:
        """True when no errors were found (warnings and info do not count)."""
        return self.error_count == 0


def validate_feed(
    path: str | Path,
    gtfs: str | Path | None = None,
    *,
    enable: Iterable[str] = (),
    encoding: str | None = None,
) -> ValidationResult:
    """Validate the TODS feed at ``path`` and return a :class:`ValidationResult`.

    ``gtfs`` resolves trip/stop/service/block references; omit it when the GTFS
    files sit alongside the TODS files. ``enable`` turns on opt-in rules by ID
    or category ("coverage", "advisory", "experimental"). ``encoding`` overrides
    UTF-8 decoding. Raises :class:`tods_validate.loader.PackageNotFoundError`
    when the package cannot be read at all.
    """
    package, findings = run(path, gtfs, enabled=frozenset(enable), encoding=encoding)
    return ValidationResult(source=package.source, findings=findings)


def suggest_fixes(
    path: str | Path,
    gtfs: str | Path | None = None,
    *,
    enable: Iterable[str] = (),
    encoding: str | None = None,
) -> list[Suggestion]:
    """Validate the feed at ``path`` and return concrete fix suggestions for it.

    Each :class:`tods_validate.suggest.Suggestion` names a finding the validator
    knows how to fix mechanically, classified ``auto`` (safe and meaning-preserving,
    the kind ``tods-validate fix`` applies) or ``review`` (derivable but worth a
    human's confirmation). Arguments mirror :func:`validate_feed`. Suggestions
    never change the feed; applying them is up to the caller.
    """
    package, findings = run(path, gtfs, enabled=frozenset(enable), encoding=encoding)
    return suggest_for_findings(findings, package)


__all__ = ["Suggestion", "ValidationResult", "suggest_fixes", "validate_feed"]
