"""Currency stamps are checked, not just written (DOC-15).

A `Last verified:` line is a claim about the outside world. These pin that the
claim is falsifiable: edit the page without re-verifying it and the check fails.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_doc_currency.py"


def _checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_doc_currency", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Derived from the checker rather than restated. The list was written out by
# hand here, so adding docs/read-api.md to STAMPED would have left the new page
# with a gate in `make docs-check` and no test proving that gate can fail.
_STAMPED = tuple(_checker().STAMPED)


def test_the_stamped_set_is_not_empty() -> None:
    """A parametrize over an empty list reports success without running."""
    assert len(_STAMPED) >= 3, f"only {_STAMPED} are stamped; the parser or the list moved"


def test_the_committed_stamps_are_current() -> None:
    assert _checker().main() == 0


@pytest.mark.parametrize("relative", _STAMPED)
def test_editing_a_stamped_page_fails_until_it_is_re_verified(
    relative: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checker = _checker()
    staged = tmp_path / relative
    staged.parent.mkdir(parents=True, exist_ok=True)
    original = (ROOT / relative).read_text(encoding="utf-8")
    staged.write_text(original, encoding="utf-8")
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    assert checker.check(relative) == []

    staged.write_text(original + "\nA claim nobody verified.\n", encoding="utf-8")
    problems = checker.check(relative)
    assert problems, "an edited page must not stay stamped as verified"
    assert "changed since it was last verified" in problems[0]


def test_a_missing_stamp_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    checker = _checker()
    relative = "docs/api.md"
    staged = tmp_path / relative
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("# Python API\n\nNo stamp here.\n", encoding="utf-8")
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    problems = checker.check(relative)
    assert any("Last verified" in problem for problem in problems)
    assert any("Recheck cadence" in problem for problem in problems)
    assert any("no fingerprint" in problem for problem in problems)


def test_the_fingerprint_a_first_run_prints_is_the_one_that_verifies(tmp_path: Path) -> None:
    # The hash covers the page but not the line holding the hash, so writing it
    # down must not change it. Otherwise recording a stamp is unresolvable.
    checker = _checker()
    page = "# Doc\n\nLast verified: 2026-08-14\nRecheck cadence: every release\n\n"
    unstamped = page + "<!-- doc-currency: sha256=PLACEHOLDER -->\n"
    computed = checker.fingerprint(unstamped)
    stamped = page + f"<!-- doc-currency: sha256={computed} -->\n"
    assert checker.fingerprint(stamped) == computed


def test_a_future_verified_date_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checker = _checker()
    relative = "docs/api.md"
    staged = tmp_path / relative
    staged.parent.mkdir(parents=True, exist_ok=True)
    body = "# Doc\n\nLast verified: 2999-01-01\nRecheck cadence: every release\n\n"
    staged.write_text(
        body + f"<!-- doc-currency: sha256={checker.fingerprint(body)} -->\n", encoding="utf-8"
    )
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    assert any("in the future" in problem for problem in checker.check(relative))
