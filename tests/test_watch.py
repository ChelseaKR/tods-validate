"""The --watch change detection and loop."""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

import tods_validate.watch as watch_mod
from tods_validate.cli import main
from tods_validate.watch import feed_signature


def test_feed_signature_detects_change_and_absence(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x")
    first = feed_signature(tmp_path)
    assert first  # non-empty for a populated directory
    os.utime(tmp_path / "a.txt", ns=(0, 0))  # change the mtime deterministically
    assert feed_signature(tmp_path) != first
    assert feed_signature(tmp_path / "missing") == frozenset()  # absence is empty


def test_watch_reruns_on_change_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # Signatures: unchanged, unchanged, changed, then stop.
    signatures = iter([frozenset({("f", 1)}), frozenset({("f", 1)}), frozenset({("f", 2)})])

    def fake_signature(_: object) -> watch_mod.Signature:
        try:
            return next(signatures)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(watch_mod, "feed_signature", fake_signature)
    monkeypatch.setattr(watch_mod.time, "sleep", lambda _seconds: None)

    calls: list[int] = []
    with pytest.raises(KeyboardInterrupt):
        watch_mod.watch("feed", lambda: calls.append(1), poll=0)
    assert len(calls) == 2  # once at start, once on the single change


def test_validate_help_lists_watch() -> None:
    result = CliRunner().invoke(main, ["validate", "--help"])
    assert result.exit_code == 0
    assert "--watch" in result.output
