#!/usr/bin/env python3
"""Fail when a declared data source has no card, or a card has no source (DG-01).

`docs/standards/DATA-GOVERNANCE-STANDARD.md` DG-01 asks for "one committed
`docs/data/<source>.md` per distinct source", checked by "file-presence check
in CI, enumerated against the repo's declared source list", and marks it
AUTO-GATE. The portfolio's definition of AUTO-GATE
(`QUALITY-AND-METRICS-STANDARD.md`) is merge-blocking with no `|| true` and no
`continue-on-error`, so this is a `make verify` gate rather than an advisory
report.

Three things are checked, and the third is the one a file-presence check alone
would miss:

* Every source declared in `docs/data/sources.json` has a card.
* Every card in `docs/data/` is a declared source, so a card cannot describe
  something the list has forgotten.
* Every card states its tier, and states the same tier the list does. A card
  and a list that disagree about whether data is L1 or L3 is worse than either
  alone, because each looks authoritative.

It also checks that each source's `paths` still exist. A card describing a
directory that was deleted is a card describing nothing, and file-presence
checks are exactly the kind that keep passing after their subject leaves.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "docs" / "data"
SOURCES = CARDS / "sources.json"
TIERS = ("L0", "L1", "L2", "L3")
TIER_RE = re.compile(r"^\*\*Tier:\*\*\s*(L[0-3])\b", re.MULTILINE)
# README.md indexes the directory; it is not a card.
NOT_A_CARD = frozenset({"README.md"})


def _declared() -> list[dict[str, object]]:
    document = json.loads(SOURCES.read_text(encoding="utf-8"))
    sources: list[dict[str, object]] = document["sources"]
    return sources


def check() -> list[str]:
    problems: list[str] = []
    if not SOURCES.exists():
        return [f"{SOURCES.relative_to(ROOT)} does not exist; there is no declared source list"]

    declared = _declared()
    if not declared:
        return [f"{SOURCES.relative_to(ROOT)} declares no sources; DG-01 has nothing to check"]

    declared_ids = {str(s["id"]) for s in declared}
    card_ids = {p.stem for p in CARDS.glob("*.md") if p.name not in NOT_A_CARD}

    for missing in sorted(declared_ids - card_ids):
        problems.append(f"source {missing!r} is declared but has no docs/data/{missing}.md (DG-01)")
    for orphan in sorted(card_ids - declared_ids):
        problems.append(
            f"docs/data/{orphan}.md describes a source that {SOURCES.name} does not declare"
        )

    for source in declared:
        problems += _check_source(source)
    return problems


def _check_source(source: dict[str, object]) -> list[str]:
    """One declared source against its card: tier stated, tier agreed, paths real."""
    problems: list[str] = []
    identifier = str(source["id"])
    tier = str(source.get("tier", ""))
    if tier not in TIERS:
        problems.append(f"source {identifier!r} has no valid tier (one of {', '.join(TIERS)})")
    card = CARDS / f"{identifier}.md"
    if card.exists():
        found = TIER_RE.search(card.read_text(encoding="utf-8"))
        if found is None:
            problems.append(f"docs/data/{identifier}.md states no '**Tier:** LN' line")
        elif found.group(1) != tier:
            problems.append(
                f"docs/data/{identifier}.md says tier {found.group(1)} but "
                f"{SOURCES.name} says {tier}"
            )
    declared_paths = source.get("paths") or []
    if not isinstance(declared_paths, list):
        problems.append(
            f"source {identifier!r} declares 'paths' as {type(declared_paths).__name__}, "
            "not a list; nothing about the card's coverage can be checked"
        )
        declared_paths = []
    for path in declared_paths:
        if not (ROOT / str(path)).exists():
            problems.append(
                f"source {identifier!r} points at {path}, which does not exist; the card "
                "describes something that is no longer here"
            )
    return problems


def main() -> int:
    declared = _declared() if SOURCES.exists() else []
    problems = check()
    print(f"declared sources: {len(declared)}")
    for source in declared:
        print(f"  {source['tier']:>2}  {source['id']}")
    if problems:
        for problem in problems:
            print(f"::error::{problem}")
        return 1
    print("every declared source has a card, and every card a source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
