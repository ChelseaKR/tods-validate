"""Concrete fix suggestions for mechanically-fixable findings.

This is the advisory companion to :mod:`tods_validate.fix`. Where ``fix`` applies
a small set of unambiguous, meaning-preserving transforms across a whole package,
this module looks at individual findings and proposes a concrete replacement value
for each one it understands, classified by how safe applying it would be:

- ``auto``  — the change is unambiguous and meaning-preserving, so
  ``tods-validate fix`` already applies it unattended (a whitespace-padded value;
  a row that exactly duplicates an earlier one).
- ``review`` — the change is mechanically derivable but a person should confirm
  it, because the original value is malformed and only its likely intent can be
  recovered. A time written ``9:45`` is almost certainly ``09:45:00``, but only
  the author knows; a date written ``2026-03-15`` is almost certainly
  ``20260315``, but the validator will not rewrite a feed on a guess.

Nothing here changes a feed. Suggestions are surfaced by ``validate --suggest``
and through :func:`tods_validate.api.suggest_fixes` so a human (or, for the
``auto`` ones, the ``fix`` command) can act on them. A suggestion is only ever
emitted when its proposed value is one the validator itself would accept, and
when reaching it from the original needs nothing but adding leading zeros,
appending a zero seconds field, or removing date separators. No digit is ever
changed, so a suggestion never alters what the value means.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .findings import Finding
from .loader import Package
from .rules.fields import parse_time
from .schema import TABLES, FieldType

# How safe it is to apply a suggestion without a human looking at it.
AUTO = "auto"
REVIEW = "review"


@dataclass(frozen=True)
class Suggestion:
    """A concrete, mechanically-derived fix for one finding.

    ``kind`` is :data:`AUTO` (meaning-preserving; ``tods-validate fix`` applies it)
    or :data:`REVIEW` (derivable but worth a human's confirmation). When the fix is
    a value change, ``current`` and ``proposed`` carry the before and after; for a
    structural fix such as deleting a duplicate row, both are ``None`` and
    ``description`` says what to do.
    """

    rule_id: str
    kind: str
    description: str
    file: str | None = None
    row: int | None = None
    field: str | None = None
    current: str | None = None
    proposed: str | None = None

    def location(self) -> str:
        parts = []
        if self.file:
            parts.append(self.file)
        if self.row is not None:
            parts.append(f"row {self.row}")
        if self.field:
            parts.append(f"field {self.field!r}")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "kind": self.kind,
            "file": self.file,
            "row": self.row,
            "field": self.field,
            "current": self.current,
            "proposed": self.proposed,
            "description": self.description,
        }


def _cell(package: Package, file: str | None, row: int | None, field: str | None) -> str | None:
    """The raw value at ``file``/``row``/``field`` in ``package``, or None."""
    if file is None or row is None or field is None:
        return None
    feed = package.get(file)
    if feed is None:
        return None
    for r in feed.rows:
        if r.line == row:
            return r.values.get(field)
    return None


def _field_type(file: str, field: str) -> FieldType | None:
    table = TABLES.get(file)
    if table is None:
        return None
    for f in table.fields:
        if f.name == field:
            return f.type
    return None


def _normalize_time(value: str) -> str | None:
    """A valid HH:MM:SS time reached from ``value`` by zero-padding alone, or None.

    Handles a missing seconds field (``9:45`` -> ``09:45:00``) and unpadded
    components (``9:5:3`` -> ``09:05:03``). Every component must be all digits, and
    the result must parse as a GTFS time, so an out-of-range value such as ``9:75``
    yields no suggestion rather than a wrong one. Only leading zeros and a zero
    seconds field are ever added; the numeric value is preserved.
    """
    parts = value.split(":")
    if len(parts) == 2:
        hours, minutes, seconds = parts[0], parts[1], "00"
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        return None
    if not (hours.isdigit() and minutes.isdigit() and seconds.isdigit()):
        return None
    candidate = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    if parse_time(candidate) is None:
        return None
    return candidate


def _normalize_date(value: str) -> str | None:
    """A valid YYYYMMDD date reached from ``value`` by dropping separators, or None.

    ``2026-03-15`` and ``2026/03/15`` become ``20260315``. The cleaned value must
    be exactly eight digits and a real calendar date, so a US-ordered ``03/15/2026``
    (which cleans to a nonsense ``03152026``) yields no suggestion rather than a
    silently reordered one.
    """
    cleaned = value.replace("-", "").replace("/", "").replace(".", "")
    if len(cleaned) != 8 or not cleaned.isdigit():
        return None
    from .gtfs_companion import parse_gtfs_date

    if parse_gtfs_date(cleaned) is None:
        return None
    return cleaned


def _suggest_trim(finding: Finding, package: Package) -> Suggestion | None:
    value = _cell(package, finding.file, finding.row, finding.field)
    if value is None:
        return None
    trimmed = value.strip()
    if trimmed == value:
        return None
    return Suggestion(
        rule_id=finding.rule_id,
        kind=AUTO,
        description="Trim the surrounding spaces so the value matches exactly",
        file=finding.file,
        row=finding.row,
        field=finding.field,
        current=value,
        proposed=trimmed,
    )


def _suggest_delete_duplicate(finding: Finding, package: Package) -> Suggestion | None:
    return Suggestion(
        rule_id=finding.rule_id,
        kind=AUTO,
        description="Delete this row; it exactly duplicates an earlier one",
        file=finding.file,
        row=finding.row,
    )


def _suggest_format(finding: Finding, package: Package) -> Suggestion | None:
    if finding.file is None or finding.field is None:
        return None
    value = _cell(package, finding.file, finding.row, finding.field)
    if not value:
        return None
    field_type = _field_type(finding.file, finding.field)
    if field_type is FieldType.TIME:
        proposed = _normalize_time(value)
        description = "Write the time as HH:MM:SS"
    elif field_type is FieldType.DATE:
        proposed = _normalize_date(value)
        description = "Write the date as YYYYMMDD"
    else:
        return None
    if proposed is None or proposed == value:
        return None
    return Suggestion(
        rule_id=finding.rule_id,
        kind=REVIEW,
        description=description,
        file=finding.file,
        row=finding.row,
        field=finding.field,
        current=value,
        proposed=proposed,
    )


# Findings whose fix this module knows how to derive. A rule absent here simply
# gets no suggestion; the finding's own message still explains what good looks like.
_GENERATORS: dict[str, Callable[[Finding, Package], Suggestion | None]] = {
    "TODS-W206": _suggest_trim,
    "TODS-W408": _suggest_delete_duplicate,
    "TODS-E203": _suggest_format,
}

SUGGESTIBLE = frozenset(_GENERATORS)


def suggest_for_findings(findings: list[Finding], package: Package) -> list[Suggestion]:
    """Concrete fix suggestions for the findings this module understands.

    Findings keep their input order, so suggestions read top-to-bottom through the
    feed the same way the report does. A finding whose rule has no generator, or
    whose value turns out not to be mechanically fixable, contributes nothing.
    """
    suggestions: list[Suggestion] = []
    for finding in findings:
        generator = _GENERATORS.get(finding.rule_id)
        if generator is None:
            continue
        suggestion = generator(finding, package)
        if suggestion is not None:
            suggestions.append(suggestion)
    return suggestions


def _change(suggestion: Suggestion) -> str:
    """The human description of one suggestion, with its value change if it has one."""
    if suggestion.current is not None and suggestion.proposed is not None:
        return f"{suggestion.description}: {suggestion.current!r} -> {suggestion.proposed!r}"
    return suggestion.description


def render_suggestions(suggestions: list[Suggestion], output_format: str = "text") -> str:
    """A human-readable suggestions block for ``text`` or ``markdown`` output."""
    if output_format == "markdown":
        return _render_markdown(suggestions)
    return _render_text(suggestions)


def _counts(suggestions: list[Suggestion]) -> tuple[int, int]:
    auto = sum(1 for s in suggestions if s.kind == AUTO)
    return auto, len(suggestions) - auto


def _render_text(suggestions: list[Suggestion]) -> str:
    if not suggestions:
        return "No mechanical fix suggestions."
    auto, review = _counts(suggestions)
    lines = [f"Suggestions ({auto} auto, {review} to review):"]
    for s in suggestions:
        location = s.location()
        prefix = f"  [{s.kind}] {location}: " if location else f"  [{s.kind}] "
        lines.append(f"{prefix}{_change(s)}")
    if auto:
        lines.append("Apply the auto fixes with: tods-validate fix PATH -o OUTPUT")
    return "\n".join(lines)


def _render_markdown(suggestions: list[Suggestion]) -> str:
    if not suggestions:
        return "## Fix suggestions\n\nNo mechanical fix suggestions."
    auto, review = _counts(suggestions)
    lines = ["## Fix suggestions", "", f"{auto} auto, {review} to review.", ""]
    for s in suggestions:
        location = s.location()
        where = f" ({location})" if location else ""
        lines.append(f"- **{s.kind}**{where}: {_change(s)}")
    if auto:
        lines.append("")
        lines.append("Apply the auto fixes with `tods-validate fix PATH -o OUTPUT`.")
    return "\n".join(lines)
