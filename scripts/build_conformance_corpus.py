#!/usr/bin/env python3
"""Build the downloadable TODS conformance corpus from tests/fixtures.

The corpus is a single zip containing every per-rule invalid fixture and the
valid feed, plus an ``expectations.json`` mapping each fixture to the rule IDs
it should produce. A TODS producer (or another validator author) can run the
fixtures through their tooling and check the rule IDs against expectations,
turning this project's test corpus into a shared, versioned conformance suite.

Usage: python scripts/build_conformance_corpus.py [OUTPUT.zip]
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from tods_validate.rules import CATEGORIES
from tods_validate.runner import run

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = _ROOT / "tests" / "fixtures"
_ALL_CATEGORIES = frozenset(CATEGORIES)


def _rule_ids(path: Path, gtfs: Path | None = None) -> list[str]:
    _, findings = run(path, gtfs, enabled=_ALL_CATEGORIES)
    return sorted({f.rule_id for f in findings})


def build(out: Path) -> dict[str, list[str]]:
    """Write the corpus zip to ``out`` and return the expectations mapping."""
    expectations: dict[str, list[str]] = {}
    members: list[tuple[str, Path]] = []

    for fixture in sorted((_FIXTURES / "invalid").iterdir()):
        if not fixture.is_dir():
            continue
        expectations[f"invalid/{fixture.name}"] = _rule_ids(fixture)
        for file in sorted(fixture.iterdir()):
            if file.is_file():
                members.append((f"invalid/{fixture.name}/{file.name}", file))

    valid_tods, valid_gtfs = _FIXTURES / "valid" / "tods", _FIXTURES / "valid" / "gtfs"
    expectations["valid"] = _rule_ids(valid_tods, valid_gtfs)
    for sub in ("tods", "gtfs"):
        for file in sorted((_FIXTURES / "valid" / sub).iterdir()):
            if file.is_file():
                members.append((f"valid/{sub}/{file.name}", file))

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, file in members:
            zf.write(file, arcname)
        zf.writestr("expectations.json", json.dumps(expectations, indent=2, sort_keys=True))
        zf.writestr(
            "README.md",
            "# TODS conformance corpus\n\n"
            "Each `invalid/<RULE-ID>/` directory is a minimal feed that should produce "
            "that rule; `valid/` should produce nothing. `expectations.json` maps each "
            "fixture to its expected rule IDs. Built from tods-validate with all opt-in "
            "categories enabled.\n",
        )
    return expectations


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else _ROOT / "dist" / "tods-conformance-corpus.zip"
    expectations = build(out)
    print(f"wrote {out} ({len(expectations)} fixtures)")


if __name__ == "__main__":
    main()
