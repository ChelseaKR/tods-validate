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
_EXPECTATIONS = _FIXTURES / "expectations.json"
_ALL_CATEGORIES = frozenset(CATEGORIES)


def _rule_ids(path: Path, gtfs: Path | None = None) -> list[str]:
    _, findings = run(path, gtfs, enabled=_ALL_CATEGORIES)
    return sorted({f.rule_id for f in findings})


def load_expectations() -> dict[str, list[str]]:
    """Load the reviewed conformance oracle committed with the fixtures."""
    raw = json.loads(_EXPECTATIONS.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(
        isinstance(key, str)
        and isinstance(value, list)
        and all(isinstance(rule_id, str) for rule_id in value)
        for key, value in raw.items()
    ):
        raise ValueError(f"invalid conformance expectations in {_EXPECTATIONS}")
    return raw


def actual_expectations() -> dict[str, list[str]]:
    """Run every fixture and return its current exact rule-ID set."""
    actual: dict[str, list[str]] = {}
    for fixture in sorted((_FIXTURES / "invalid").iterdir()):
        if fixture.is_dir():
            actual[f"invalid/{fixture.name}"] = _rule_ids(fixture)

    valid_tods, valid_gtfs = _FIXTURES / "valid" / "tods", _FIXTURES / "valid" / "gtfs"
    actual["valid"] = _rule_ids(valid_tods, valid_gtfs)
    return actual


def build(out: Path) -> dict[str, list[str]]:
    """Write the corpus zip after checking it against the committed oracle."""
    expectations = load_expectations()
    actual = actual_expectations()
    if actual != expectations:
        raise RuntimeError(
            "conformance results differ from tests/fixtures/expectations.json; "
            "review the behavior change and update the oracle explicitly"
        )

    members: list[tuple[str, Path]] = []

    for fixture in sorted((_FIXTURES / "invalid").iterdir()):
        if not fixture.is_dir():
            continue
        for file in sorted(fixture.iterdir()):
            if file.is_file():
                members.append((f"invalid/{fixture.name}/{file.name}", file))

    for sub in ("tods", "gtfs"):
        for file in sorted((_FIXTURES / "valid" / sub).iterdir()):
            if file.is_file():
                members.append((f"valid/{sub}/{file.name}", file))

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, file in members:
            zf.write(file, arcname)
        zf.write(_EXPECTATIONS, "expectations.json")
        zf.writestr(
            "README.md",
            "# TODS conformance corpus\n\n"
            "Each `invalid/<RULE-ID>/` directory is a minimal feed that should produce "
            "that rule; `valid/` should produce nothing. `expectations.json` maps each "
            "fixture to its reviewed exact rule-ID set. The release build checks the "
            "fixtures against this committed oracle with all opt-in categories enabled.\n",
        )
    return expectations


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else _ROOT / "dist" / "tods-conformance-corpus.zip"
    expectations = build(out)
    print(f"wrote {out} ({len(expectations)} fixtures)")


if __name__ == "__main__":
    main()
