#!/usr/bin/env python3
"""Enforce the i18n N/A declaration.

Per STANDARDS/INTERNATIONALIZATION-STANDARD.md §1, a repo that declares i18n
N/A must ship docs/I18N.md carrying the marker `i18n status: N/A` and a
non-empty `Reason:` line. This gate fails (non-zero exit) if the file, the
marker, or the reason is missing, so the declaration cannot silently rot. CI
runs it alongside the other verify checks.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOC_PATH = Path(__file__).parent.parent / "docs" / "I18N.md"

STATUS_MARKER = "i18n status: N/A"
REASON_RE = re.compile(r"^Reason:[ \t]*(?P<reason>\S.*)$", re.MULTILINE)


def check() -> list[str]:
    problems: list[str] = []
    if not DOC_PATH.exists():
        return [f"{DOC_PATH} is missing; an i18n N/A declaration is required (see §1)."]
    text = DOC_PATH.read_text(encoding="utf-8")
    if STATUS_MARKER not in text:
        problems.append(f"{DOC_PATH}: missing the marker '{STATUS_MARKER}'.")
    match = REASON_RE.search(text)
    if match is None or not match.group("reason").strip():
        problems.append(f"{DOC_PATH}: no non-empty 'Reason:' line.")
    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print(f"{DOC_PATH.name}: i18n N/A declaration present and valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
