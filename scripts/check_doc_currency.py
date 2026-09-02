#!/usr/bin/env python3
"""Fail when a currency-stamped document has changed since it was verified.

DOCUMENTATION-STANDARD §6.5: a document whose correctness depends on something
outside itself carries a ``Last verified: YYYY-MM-DD`` line and a
``Recheck cadence:`` line. ``docs/getting-started.md``, ``docs/api.md``,
``docs/read-api.md`` and ``docs/a11y/STATEMENT.md`` document commands and API
members that the code can move out from under, and had neither.

A date on its own is only a claim. This check makes the claim falsifiable: the
stamp records a fingerprint of the page as it was when someone verified it, and
this fails when the page has changed since. The date then means "this text was
checked", not "someone typed a date once". What it cannot check is whether the
verification was any good -- that part is a REVIEW gate, and the cadence line
says so.

Run by ``make docs-check`` (the ``docs-drift`` job in ci.yml).
"""

from __future__ import annotations

import hashlib
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# docs/read-api.md joined the list on 2026-08-28. It documents ten of the
# nineteen names the v1 contract freezes -- the whole `tods_validate.read`
# namespace -- against code that can move under it exactly as api.md's can,
# and it was the half of the published API surface with no stamp to fail on.
STAMPED = (
    "docs/getting-started.md",
    "docs/api.md",
    "docs/read-api.md",
    "docs/a11y/STATEMENT.md",
)

VERIFIED_RE = re.compile(r"^Last verified: (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
CADENCE_RE = re.compile(r"^Recheck cadence: \S", re.MULTILINE)
FINGERPRINT_RE = re.compile(r"^<!-- doc-currency: sha256=([0-9a-f]{12}) -->$", re.MULTILINE)
# Strips the fingerprint line whatever it currently says, so the hash a first
# run prints is the same one that then verifies -- a self-referential hash that
# changed when you wrote it down would be unusable.
FINGERPRINT_LINE_RE = re.compile(r"^<!-- doc-currency: sha256=\S* -->\n?", re.MULTILINE)


def fingerprint(text: str) -> str:
    """The page's content hash, with the fingerprint line itself removed.

    Excluding that one line is what lets the stamp live inside the file it
    describes; everything else on the page, including the verified date, is
    covered.
    """
    body = FINGERPRINT_LINE_RE.sub("", text)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def check(relative: str) -> list[str]:
    path = ROOT / relative
    if not path.exists():
        return [f"{relative}: does not exist"]
    text = path.read_text(encoding="utf-8")
    problems = []

    verified = VERIFIED_RE.search(text)
    if verified is None:
        problems.append(f"{relative}: no 'Last verified: YYYY-MM-DD' line")
    else:
        try:
            stamped = date.fromisoformat(verified.group(1))
        except ValueError:
            problems.append(f"{relative}: unparseable verified date {verified.group(1)!r}")
        else:
            if stamped > date.today():
                problems.append(f"{relative}: verified date {stamped} is in the future")

    if CADENCE_RE.search(text) is None:
        problems.append(f"{relative}: no 'Recheck cadence:' line")

    recorded = FINGERPRINT_RE.search(text)
    actual = fingerprint(text)
    if recorded is None:
        problems.append(
            f"{relative}: no fingerprint. After verifying the page, add:\n"
            f"    <!-- doc-currency: sha256={actual} -->"
        )
    elif recorded.group(1) != actual:
        problems.append(
            f"{relative}: changed since it was last verified "
            f"(recorded {recorded.group(1)}, now {actual}).\n"
            "    Re-check the commands and API members this page documents, then "
            f"record the new date, with sha256={actual}."
        )
    return problems


def main() -> int:
    problems = [problem for relative in STAMPED for problem in check(relative)]
    if problems:
        print("Currency stamps are out of date:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"currency stamps current: {', '.join(STAMPED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
