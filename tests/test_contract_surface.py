"""Every name in the v1 public contract is exercised by a test.

`scripts/check_public_contract.py` proves the snapshot in
`docs/v1-contract-candidate.json` matches what the package exports. It says
nothing about whether any of those exports work, and two of them were reached
by no test at all before this file existed: `tods_validate.read.to_dataframe`
and `tods_validate.__version__`. Both are in the snapshot, so v1.0.0 would
have promised semantic-versioning stability for behaviour the suite had never
run.

`to_dataframe` is the sharper of the two. Its documented contract
(`docs/read-api.md`) is a specific ImportError with an install hint when the
`dataframe` extra is absent, and `pandas` is deliberately not in the
development dependencies -- so the path most users would hit first was the one
nothing checked.
"""

from __future__ import annotations

import json
import sys
import tomllib
import types
from pathlib import Path
from typing import Any

import pytest

import tods_validate
from tods_validate.loader import FeedFile, Row
from tods_validate.read import to_dataframe, to_rows

_ROOT = Path(__file__).resolve().parent.parent
_CONTRACT = _ROOT / "docs" / "v1-contract-candidate.json"
_TESTS = Path(__file__).resolve().parent


def _feed_file() -> FeedFile:
    return FeedFile(
        name="vehicles.txt",
        headers=("vehicle_id", "vehicle_label"),
        rows=[
            Row(line=2, values={"vehicle_id": "bus-1", "vehicle_label": "Old Reliable"}),
            Row(line=3, values={"vehicle_id": "bus-2", "vehicle_label": "Spare"}),
        ],
    )


# ---------------------------------------------------------------------------
# tods_validate.__version__
# ---------------------------------------------------------------------------


def test_version_is_the_version_the_project_declares() -> None:
    declared = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert tods_validate.__version__ == declared["project"]["version"]


def test_version_is_not_the_uninstalled_fallback() -> None:
    """The fallback is correct behaviour and a wrong answer to ship.

    `__init__` falls back to "0.0.0+unknown" when the distribution metadata is
    missing. A test run against an installed package that sees the fallback is
    testing something other than the package under test, and every report,
    SARIF document and `--stamp` footer would carry that string.
    """
    assert tods_validate.__version__ != "0.0.0+unknown"


# ---------------------------------------------------------------------------
# tods_validate.read.to_dataframe
# ---------------------------------------------------------------------------


def test_to_dataframe_without_pandas_raises_the_documented_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(ImportError) as excinfo:
        to_dataframe(_feed_file())
    assert "tods-validate[dataframe]" in str(excinfo.value), (
        "the error names no way to fix it; docs/read-api.md promises the extra"
    )


def test_to_dataframe_tabulates_the_same_rows_to_rows_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The happy path, without making pandas a development dependency.

    A stub stands in for pandas and records what it was handed. That is enough
    to pin the part this project owns -- which rows reach the DataFrame
    constructor -- and it deliberately does not try to test pandas.
    """
    captured: list[Any] = []

    stub = types.ModuleType("pandas")
    stub.DataFrame = lambda data: captured.append(data) or "dataframe"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pandas", stub)

    feed = _feed_file()
    result = to_dataframe(feed)

    assert result == "dataframe"
    assert captured == [to_rows(feed)]
    assert captured[0] == [
        {"vehicle_id": "bus-1", "vehicle_label": "Old Reliable"},
        {"vehicle_id": "bus-2", "vehicle_label": "Spare"},
    ]


def test_to_dataframe_of_a_missing_file_is_empty_rather_than_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Any] = []
    stub = types.ModuleType("pandas")
    stub.DataFrame = lambda data: captured.append(data) or "dataframe"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pandas", stub)

    to_dataframe(None)
    assert captured == [[]]


# ---------------------------------------------------------------------------
# The floor under both of the above
# ---------------------------------------------------------------------------


def unreferenced_contract_exports(modules: list[Path] | None = None) -> list[str]:
    """Contract exports named in none of ``modules`` (default: the whole suite).

    Exposed as a function so the check can be pointed at a subset -- which is
    how it was shown to fail: run against the test modules that existed before
    this file, it names `to_dataframe` and `__version__`.
    """
    contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    paths = sorted(_TESTS.glob("test_*.py")) if modules is None else modules
    sources = [path.read_text(encoding="utf-8") for path in paths]
    if not sources:
        raise AssertionError("no test modules to scan; the check would pass vacuously")
    return [
        f"{module}.{name}"
        for module, names in contract["pythonExports"].items()
        for name in names
        if not any(name in text for text in sources)
    ]


def test_every_v1_contract_export_is_named_somewhere_in_the_suite() -> None:
    """A coverage floor, not a proof of coverage.

    Being named in a test file is weak evidence that an export works. Being
    named in none of them is strong evidence that it does not: a 90% line
    coverage floor cannot see an export nothing imports, which is how
    `to_dataframe` and `__version__` reached a release candidate untouched.
    """
    assert not unreferenced_contract_exports(), (
        "public exports in the v1 contract that no test module mentions: "
        f"{', '.join(unreferenced_contract_exports())}. Freezing a compatibility "
        "promise around an export nothing exercises is the promise this project "
        "exists to refuse."
    )
