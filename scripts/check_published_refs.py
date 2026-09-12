#!/usr/bin/env python3
"""Fail when this repository publishes a ref that is meant to move and does not.

`scripts/check_action_refs.py` gates what this repository *teaches*. This gates
what it *publishes*, which is the half a corrected README cannot reach: a
consumer who pinned a major-only ref years ago keeps resolving it whatever the
docs now say.

One such ref was published here. `v0` is a lightweight tag at `097427f`, the
`v0.5.0` release commit, recorded as a stray in `docs/CONFORMANCE-GAPS.md`. It
never moved, so six releases on `ChelseaKR/tods-validate@v0` still installs
v0.5.0 -- a build whose `--format github`, the only format the composite action
emits, prints `0 error(s), 0 warning(s), 0 info` and exits 0 for a feed in which
16 of 43 checks did not run for want of a companion GTFS feed, 9 of them
ERROR-severity, and which has neither `--require-complete-run` nor the
`require-complete-run` input to fail on it.

A major- or minor-only ref has only two possible failure modes and this project
has no appetite for either:

* it moves, and a consumer's pinned CI changes behaviour without a release they
  chose -- which is what `SECURITY.md`'s supply-chain section tells consumers to
  avoid by pinning "by commit SHA or image digest rather than a moving tag", and
  what `docs/standards/RELEASE-AND-VERSIONING-STANDARD.md` calls non-conformant;
* it stops moving, silently, which is what happened.

Under 0.x the first is worse than it sounds: minor releases here are allowed to
change behaviour, and between v0.5.0 and v0.11.0 the minimum Python rose from
3.11 to 3.12 and four rules were added. So no `vN` or `vN.N` ref is published,
and `v1` -- which `docs/plans/v1.0.0-readiness.md` warns "will invite exactly
the same pin" -- is refused in advance by the same rule.

Reads the remote, not the local tag list: a local clone can carry a tag origin
deleted, or miss one origin has. A remote that cannot be read is a failure and
never a skip, because "I could not look" and "there is nothing there" are the
same silence.

Run by the `published-refs` job in ci.yml, and by `make published-refs-check`.
"""

from __future__ import annotations

import re
import subprocess
import sys

MOVING_REF_RE = re.compile(r"^v\d+(\.\d+)?$")
TAG_LINE_RE = re.compile(r"^[0-9a-f]{40}\trefs/tags/(?P<tag>.+?)(?P<peeled>\^\{\})?$")


class Unreadable(Exception):
    """The remote could not be listed. Never converted into an empty result."""


def remote_tags(remote: str) -> dict[str, str]:
    """Every tag on ``remote``, mapped to the object it points at.

    Raises rather than returning an empty mapping, so a network failure cannot
    be mistaken for a repository with no moving refs.
    """
    try:
        out = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["/usr/bin/env", "git", "ls-remote", "--tags", remote],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise Unreadable(f"could not list tags on {remote!r}: {exc}") from exc

    tags: dict[str, str] = {}
    for line in out.stdout.splitlines():
        match = TAG_LINE_RE.match(line)
        if match is None:
            continue
        # `^{}` lines are the commit an annotated tag dereferences to; the tag
        # object line already recorded the name.
        if match.group("peeled"):
            continue
        tags[match.group("tag")] = line.split("\t", 1)[0]
    if not tags:
        raise Unreadable(
            f"{remote!r} reported no tags at all. This repository has published "
            f"releases since v0.1.0, so that is the listing failing, not the "
            f"remote being empty."
        )
    return tags


def moving_refs(tags: dict[str, str]) -> list[str]:
    return sorted(tag for tag in tags if MOVING_REF_RE.match(tag))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    remote = args[0] if args else "origin"

    try:
        tags = remote_tags(remote)
    except Unreadable as exc:
        print(f"check_published_refs: {exc}")
        return 1

    offenders = moving_refs(tags)
    if offenders:
        print(f"{remote} publishes a ref that is meant to move:")
        for tag in offenders:
            print(f"  - refs/tags/{tag} -> {tags[tag]}")
        print(
            "\nA major- or minor-only ref either moves under a consumer who "
            "pinned it, or\nsilently stops moving. SECURITY.md asks consumers to "
            "pin by commit SHA or\ndigest rather than a moving tag; this is that "
            "policy applied to what we\npublish. Remove it with:\n"
        )
        for tag in offenders:
            print(f"    git push origin :refs/tags/{tag}    # then: git tag -d {tag}")
        print(
            "\nDeleting a published ref is an owner action. Anyone pinned at it "
            "will get\n'Unable to resolve action' -- which is the point: a loud "
            "break beats a\nvalidator that quietly checks 26 of 43 rules."
        )
        return 1

    print(f"{remote}: {len(tags)} tags, none of them a major- or minor-only ref (no vN or vN.N)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
