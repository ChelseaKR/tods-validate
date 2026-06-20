"""Finding and severity types shared by rules and reporting."""

from __future__ import annotations

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
        }
