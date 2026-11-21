"""A published moving ref is refused, and an unreadable remote is not a pass.

The live listing is the `published-refs` job's business; these cover the
decision and, more importantly, the two ways this check could have reported a
clean repository without having looked at one.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_published_refs.py"


def _checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_published_refs", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SHA = "0" * 40
# The real listing, as `git ls-remote --tags origin` printed it on 2026-09-12,
# trimmed to the shapes that matter: a lightweight release tag, an annotated one
# with its peeled line, and the stray `v0`.
REAL_LISTING = "\n".join(
    [
        f"{'0' * 40}\trefs/tags/v0",
        f"{'1' * 40}\trefs/tags/v0.5.0",
        f"{'2' * 40}\trefs/tags/v0.11.0",
        f"{'3' * 40}\trefs/tags/v0.11.0^{{}}",
    ]
)


@pytest.mark.parametrize("tag", ["v0", "v1", "v2", "v0.11", "v1.0", "v10"])
def test_a_major_or_minor_only_ref_is_refused(tag: str) -> None:
    assert _checker().moving_refs({tag: SHA}) == [tag]


@pytest.mark.parametrize("tag", ["v0.5.0", "v0.11.0", "v1.0.0", "v0.9.1"])
def test_an_exact_release_tag_is_not_a_moving_ref(tag: str) -> None:
    assert _checker().moving_refs({tag: SHA}) == []


def test_v1_is_refused_before_it_exists() -> None:
    """docs/plans/v1.0.0-readiness.md: `v1` "will invite exactly the same pin"."""
    assert _checker().moving_refs({"v1": SHA, "v1.0.0": SHA}) == ["v1"]


def test_the_stray_ref_is_picked_out_of_a_real_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _checker()
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, REAL_LISTING, ""),
    )
    tags = checker.remote_tags("origin")
    assert set(tags) == {"v0", "v0.5.0", "v0.11.0"}, "a peeled ^{} line became a tag"
    # The object an annotated tag's own line names, not the commit its `^{}`
    # line dereferences to. Both lines carry the same tag name, so a reader that
    # does not skip the peeled one reports the wrong object and says nothing
    # about it -- the diagnosis in the failure message is the whole output.
    assert tags["v0.11.0"] == "2" * 40
    assert checker.moving_refs(tags) == ["v0"]


def test_a_remote_that_cannot_be_listed_fails_rather_than_reporting_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "I could not look" and "there is nothing there" print the same silence."""
    checker = _checker()

    def boom(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(128, "git", stderr="Could not resolve host")

    monkeypatch.setattr(checker.subprocess, "run", boom)
    with pytest.raises(checker.Unreadable):
        checker.remote_tags("origin")
    assert checker.main(["origin"]) == 1


def test_a_listing_with_no_tags_at_all_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """This repository has published tags since v0.1.0; an empty answer is a bug."""
    checker = _checker()
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "", ""),
    )
    with pytest.raises(checker.Unreadable):
        checker.remote_tags("origin")
    assert checker.main(["origin"]) == 1


def test_a_clean_remote_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = _checker()
    clean = "\n".join([f"{'1' * 40}\trefs/tags/v0.5.0", f"{'2' * 40}\trefs/tags/v0.11.0"])
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, clean, ""),
    )
    assert checker.main(["origin"]) == 0


def test_a_remote_carrying_the_stray_ref_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = _checker()
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, REAL_LISTING, ""),
    )
    assert checker.main(["origin"]) == 1
