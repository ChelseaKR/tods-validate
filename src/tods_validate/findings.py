"""Finding and severity types shared by rules and reporting."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    """Ordered so that max() picks the worst severity."""

    INFO = 0
    WARNING = 1
    ERROR = 2

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Finding:
    """One validation result.

    Messages are written for transit schedulers, not programmers: say what is
    wrong, where, and what good looks like.
    """

    rule_id: str
    severity: Severity
    message: str
    file: str | None = None
    # 1-based line number in the CSV file, counting the header as line 1.
    row: int | None = None
    field: str | None = None
    suggestion: str | None = None
    # Machine-readable context for downstream consumers that should not have to
    # parse the English message: the offending value, what was expected, the
    # referenced ID, and so on. Keys are stable per rule; see docs/rules.md.
    # Excluded from equality and hashing (it is derived from the other fields
    # and a Mapping is not hashable), so Finding stays hashable and comparable.
    #
    # NOTE: called as ``dataclasses.field(...)`` rather than a bare ``field``
    # import, because this dataclass already declares an attribute named
    # ``field`` (the CSV column name, above) which shadows a plain ``field``
    # name for the rest of this class body.
    data: Mapping[str, str] | None = dataclasses.field(default=None, compare=False)

    def location(self) -> str:
        parts = []
        if self.file:
            parts.append(self.file)
        if self.row is not None:
            parts.append(f"row {self.row}")
        if self.field:
            parts.append(f"field {self.field!r}")
        return ", ".join(parts)

    def pointer(self) -> str | None:
        """A stable, machine-parseable location identifier.

        Of the form ``file.txt#L4`` or ``file.txt#L4/field``, so consumers can
        deep-link a finding without parsing the human ``location()`` string.
        Returns None for findings not tied to a file.
        """
        if not self.file:
            return None
        ref = self.file
        if self.row is not None:
            ref += f"#L{self.row}"
        if self.field:
            ref += f"/{self.field}"
        return ref

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "severity": str(self.severity),
            "file": self.file,
            "row": self.row,
            "field": self.field,
            "location": self.pointer(),
            "message": self.message,
            "suggestion": self.suggestion,
            "data": dict(self.data) if self.data is not None else None,
        }
