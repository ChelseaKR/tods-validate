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

from tods_validate import __version__
from tods_validate.rules import CATEGORIES
from tods_validate.runner import run

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = _ROOT / "tests" / "fixtures"
_EXPECTATIONS = _FIXTURES / "expectations.json"
_ALL_CATEGORIES = frozenset(CATEGORIES)

# "core" runs by default, so the documented commands name only the opt-in
# categories.
_ENABLE_FLAGS = " ".join(f"--enable {c}" for c in CATEGORIES if c != "core")

_README = f"""\
# TODS conformance corpus

This archive contains:

- `valid/`: a complete TODS feed with its companion GTFS files in the same
  directory. Validating it should produce no findings.
- `invalid/<RULE-ID>/`: one minimal, self-contained feed per rule, each
  crafted to produce that rule.
- `expectations.json`: a map from each fixture path to the exact rule IDs it
  should produce (`[]` for `valid`). Expected outcomes are reviewed in source
  control, and the release build refuses to package fixtures whose current
  results differ from this oracle.

## Running the fixtures

The expected rule IDs assume every opt-in category is enabled:

```sh
tods-validate validate valid/ {_ENABLE_FLAGS}
tods-validate validate invalid/TODS-E307/ {_ENABLE_FLAGS}
```

Each fixture directory is self-contained; companion GTFS files sit alongside
the TODS files, so no `--gtfs` flag is needed. To check outcomes mechanically,
run with `--format json` and compare the reported rule IDs against that
fixture's entry in `expectations.json`.

Rule IDs and severities are defined by tods-validate, not by the TODS
specification. The rule catalog is at
<https://github.com/ChelseaKR/tods-validate/blob/main/docs/rules.md> and the
contract this archive is built under is described in
<https://github.com/ChelseaKR/tods-validate/blob/main/docs/conformance.md>.

Built by tods-validate {__version__} from `tests/fixtures/`.
"""

# Fixed timestamp for every archive member so rebuilding the same tree yields
# a byte-identical zip regardless of checkout mtimes or build time.
_EPOCH = (1980, 1, 1, 0, 0, 0)


def _add(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arcname, date_time=_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


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

    # The repo keeps the valid feed split into tods/ and gtfs/ subdirectories,
    # but the archive flattens them into one directory so that
    # `tods-validate validate valid/` works with no --gtfs flag.
    valid_files = sorted(
        [
            f
            for sub in (_FIXTURES / "valid" / "tods", _FIXTURES / "valid" / "gtfs")
            for f in sub.iterdir()
            if f.is_file()
        ],
        key=lambda f: f.name,
    )
    names = [f.name for f in valid_files]
    if len(set(names)) != len(names):
        raise RuntimeError("valid/tods and valid/gtfs contain colliding filenames")
    members.extend((f"valid/{f.name}", f) for f in valid_files)

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, file in members:
            _add(zf, arcname, file.read_bytes())
        _add(zf, "expectations.json", _EXPECTATIONS.read_bytes())
        _add(zf, "README.md", _README.encode())
    return expectations


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else _ROOT / "dist" / "tods-conformance-corpus.zip"
    expectations = build(out)
    print(f"wrote {out} ({len(expectations)} fixtures)")


if __name__ == "__main__":
    main()
