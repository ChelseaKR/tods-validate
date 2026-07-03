"""Finding and severity types shared by rules and reporting."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import IntEnum


class Severity(IntEnum):
    """Ordered so that max() picks the worst severity."""

    INFO = 0
    WARNING = 1
    ERROR = 2

    def __str__(self) -> str:
        return self.name


def _fingerprint_payload(
    rule_id: str,
    file: str | None,
    field: str | None,
    data: Mapping[str, str] | None,
) -> str:
    """Canonical JSON payload for a content fingerprint.

    Built only from stable content: rule ID, file, field, and the rule's own
    structured machine context (``data`` — offending value, referenced ID, and
    other FIX-05 parameters). Row and message are deliberately excluded so
    inserting or removing an unrelated row elsewhere in the file does not
    change every subsequent finding's identity.
    """
    items = sorted((data or {}).items())
    value = (data or {}).get("value") if data else None
    canonical = {
        "rule_id": rule_id,
        "file": file,
        "field": field,
        "data": items,
        "value": value,
    }
    return json.dumps(canonical, sort_keys=True, default=str)


def fingerprint_from_parts(
    rule_id: str,
    file: str | None,
    field: str | None,
    data: Mapping[str, str] | None,
) -> str:
    """Content fingerprint computed from raw parts.

    Shared by ``Finding.fingerprint()`` and by ``baseline.py``, which
    recomputes a fingerprint from a stored baseline dict that predates the
    ``fingerprint`` field but already carries ``data``.
    """
    payload = _fingerprint_payload(rule_id, file, field, data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    # Structured machine context (FIX-05): offending value, expected/allowed
    # values, referenced ID, or other rule-specific key/value pairs. Additive
    # and optional — None for rules that have not been migrated to emit it
    # yet. This is what makes ``fingerprint()`` below distinguish findings
    # without relying on row number. Excluded from equality and hashing (a
    # Mapping is not hashable), so Finding stays hashable and comparable.
    data: Mapping[str, str] | None = dataclass_field(default=None, compare=False)
    # pointer() of the "root" finding that structurally caused this one (e.g. a
    # TODS-E201 fired only because a TODS-E104 ragged row left the field blank).
    # None for findings that are not a known downstream echo of another one.
    # Never used to drop a finding from machine-readable formats -- it only lets
    # renderers collapse an echo under its cause for humans.
    caused_by: str | None = None

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

    def fingerprint(self) -> str:
        """Content-anchored identity, stable across row renumbering.

        Excludes ``row`` and ``message`` on purpose: inserting a row earlier
        in the file, or a message wording tweak, must not change identity. It
        is a heuristic, not a guarantee — two distinct findings that share
        rule, file, field, and (if present) identical ``data`` will
        fingerprint identically, and a row whose *content* changes (not just
        its position) will still churn even though its row number may not.
        See ``baseline.py`` for the honesty note this implies for
        ``--baseline``.
        """
        return fingerprint_from_parts(self.rule_id, self.file, self.field, self.data)

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "severity": str(self.severity),
            "file": self.file,
            "row": self.row,
            "field": self.field,
            "location": self.pointer(),
            "data": dict(self.data) if self.data is not None else None,
            "message": self.message,
            "suggestion": self.suggestion,
            "caused_by": self.caused_by,
            "fingerprint": self.fingerprint(),
        }
