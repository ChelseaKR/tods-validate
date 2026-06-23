"""Re-validate a feed when it changes, for `validate --watch`.

A small mtime-polling watcher with no third-party dependency. The signature
function is pure and unit-tested; the loop blocks until interrupted and is the
cheap interim before a full language-server integration.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

Signature = frozenset[tuple[str, int]]


def feed_signature(path: str | Path) -> Signature:
    """A change signature for the feed at ``path``.

    For a directory: ``(relative path, mtime_ns)`` for every file under it. For a
    single file (or a .zip): that one file. A path that does not exist yields an
    empty signature, so a feed appearing or disappearing counts as a change.
    """
    target = Path(path)
    if target.is_dir():
        return frozenset(
            (str(f.relative_to(target)), f.stat().st_mtime_ns)
            for f in target.rglob("*")
            if f.is_file()
        )
    if target.is_file():
        return frozenset({(target.name, target.stat().st_mtime_ns)})
    return frozenset()


def watch(path: str | Path, on_change: Callable[[], None], *, poll: float = 1.0) -> None:
    """Run ``on_change`` once, then again whenever the feed's signature changes.

    Blocks until ``KeyboardInterrupt``. ``poll`` is the interval in seconds.
    """
    on_change()
    last = feed_signature(path)
    while True:
        time.sleep(poll)
        current = feed_signature(path)
        if current != last:
            last = current
            on_change()
