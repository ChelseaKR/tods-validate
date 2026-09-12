#!/usr/bin/env python3
"""Fail when a documented pin at this repository is a moving ref, or is stale.

`SECURITY.md`'s "Supply chain" section tells a consumer to "pin by commit SHA or
image digest rather than a moving tag", and
`docs/standards/RELEASE-AND-VERSIONING-STANDARD.md` records that pinning "to a
branch or moving tag is non-conformant". Nothing enforced either sentence
against this repository's own copy-and-paste examples, and both of them drifted:
the pre-commit example was bumped off a stale `v0.4.0` by hand in #137, and both
it and the GitHub Action example sat at `v0.10.0` after `v0.11.0` shipped.

The failure this exists to make impossible is not a typo, it is silence. A
moving ref this project once published, `ChelseaKR/tods-validate@v0`, was a
lightweight tag at the `v0.5.0` release commit. Measured against the same
TODS-only package, v0.5.0's `--format github` -- the only format the composite
action emits -- printed

    tods-validate: 0 error(s), 0 warning(s), 0 info in feed-tods-only.

and exited 0, while 16 of 43 checks had not run for want of a companion GTFS
feed, 9 of them ERROR-severity. v0.11.0 prints `26 of 43 checks ran` and two
`::notice` annotations naming every rule, and `--require-complete-run` (absent
from v0.5.0 entirely, CLI and `action.yml` alike) fails the run. A consumer who
followed the README's own remedy, `require-complete-run: "true"`, against a
moving ref that had fallen behind would be passing an input the pinned
`action.yml` does not declare: GitHub warns about an unexpected input and runs
the job anyway, so the remedy reads as applied and does nothing.

So two rules, both checked here:

* **A taught ref must be exact.** A major- or minor-only ref (`@v0`, `@v0.10`),
  a branch (`@main`), or anything else that is not `vX.Y.Z` or a 40-character
  commit SHA is refused, whatever it currently points at.
* **A taught ref must be current.** The version it names must equal
  `pyproject.toml`'s. That makes the release that bumps the version the release
  that bumps the examples, instead of leaving them to be noticed.

Scanning is limited to Markdown and YAML because those are what a consumer
copies. `src/tods_validate/init.py` also writes a `uses:` line, and is excluded
by that rule rather than by name: it does not hard-code a ref at all, it derives
one from `__version__`, and `tests/test_init.py` covers it.

Run by ``make docs-check`` (the ``docs-drift`` job in ci.yml).
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCANNED_SUFFIXES = (".md", ".yml", ".yaml")

# `uses: ChelseaKR/tods-validate@REF`, with the rest of the line kept so a
# `# vX.Y.Z` comment beside a SHA pin can be read and checked too.
ACTION_RE = re.compile(
    r"uses:[ \t]*ChelseaKR/tods-validate@(?P<ref>\S+)(?P<rest>[^\n]*)",
    re.IGNORECASE,
)
# pre-commit: `rev:` belongs to whichever `repo:` block it sits under, so the
# repo line opens a block and the next `- repo:` closes it. Matching `rev:`
# anywhere would bind this project's version to .pre-commit-config.yaml's pins
# for ruff and friends.
PRECOMMIT_REPO_RE = re.compile(
    r"repo:[ \t]*https://github\.com/ChelseaKR/tods-validate/?[ \t]*$",
    re.IGNORECASE,
)
PRECOMMIT_NEXT_REPO_RE = re.compile(r"^[#\s]*-[ \t]*repo:")
PRECOMMIT_REV_RE = re.compile(r"rev:[ \t]*(?P<ref>\S+)(?P<rest>[^\n]*)")

EXACT_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAJOR_OR_MINOR_RE = re.compile(r"^v\d+(\.\d+)?$")
# The `# vX.Y.Z` a SHA pin carries, in the style this repository's own workflows
# use for third-party actions (`actions/setup-python@5fda3b9... # v7`).
SHA_COMMENT_RE = re.compile(r"#[ \t]*v(?P<version>\d+\.\d+\.\d+)\b")


def declared_version(root: Path = ROOT) -> str:
    """The version in pyproject.toml -- on `main`, the current release."""
    with (root / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def tracked_files(root: Path = ROOT) -> list[str]:
    """Every tracked path with a scanned suffix, sorted.

    Reads the index rather than walking the tree, so a vendored or ignored copy
    of a doc cannot fail the gate and an untracked scratch file cannot pass it.
    """
    out = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        ["/usr/bin/env", "git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(p for p in out.split("\0") if p.endswith(SCANNED_SUFFIXES))


def _judge(ref: str, rest: str, current: str) -> str | None:
    """Return the problem with one taught ref, or None if it is exact and current."""
    exact = EXACT_TAG_RE.match(ref)
    if exact is not None:
        if exact.group("version") != current:
            return (
                f"pins v{exact.group('version')}, but the current release is "
                f"v{current}. Bump the example in the release that bumps "
                f"pyproject.toml."
            )
        return None

    if SHA_RE.match(ref) is not None:
        comment = SHA_COMMENT_RE.search(rest)
        if comment is not None and comment.group("version") != current:
            return (
                f"is a commit SHA labelled v{comment.group('version')}, but the "
                f"current release is v{current}. Either the SHA or its comment "
                f"is stale, and the comment is the half a reader trusts."
            )
        return None

    if MAJOR_OR_MINOR_RE.match(ref) is not None:
        return (
            f"pins {ref!r}, a major- or minor-only ref. Such a ref either moves "
            f"-- which SECURITY.md's supply-chain section tells consumers not to "
            f"rely on -- or silently does not, which is how @v0 came to resolve "
            f"to v0.5.0 six releases on. Pin v{current} or a 40-character SHA."
        )
    return f"pins {ref!r}, which is not a release. Pin v{current} or a 40-character commit SHA."


def scan_text(relative: str, text: str, current: str) -> tuple[list[str], int]:
    """Problems with the refs taught in one file, and how many refs were read.

    The second number is the point. A gate that reports only problems cannot
    tell "every example is current" apart from "the regex stopped matching", and
    both print nothing.
    """
    problems: list[str] = []
    found = 0

    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ACTION_RE.search(line)
        if match is None:
            continue
        found += 1
        problem = _judge(match.group("ref"), match.group("rest"), current)
        if problem is not None:
            problems.append(f"{relative}:{line_number}: the Action example {problem}")

    in_block = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if PRECOMMIT_REPO_RE.search(line):
            in_block = True
            continue
        if not in_block:
            continue
        if PRECOMMIT_NEXT_REPO_RE.match(line):
            in_block = False
            continue
        rev = PRECOMMIT_REV_RE.search(line)
        if rev is None:
            continue
        in_block = False
        found += 1
        problem = _judge(rev.group("ref"), rev.group("rest"), current)
        if problem is not None:
            problems.append(f"{relative}:{line_number}: the pre-commit example {problem}")

    return problems, found


def main() -> int:
    # ROOT is passed explicitly rather than left to the default argument, which
    # binds at import and would ignore a test that repoints the module at a
    # fixture tree -- a control that cannot move the root cannot fail.
    current = declared_version(ROOT)
    paths = tracked_files(ROOT)
    if not paths:
        print("check_action_refs: no tracked Markdown or YAML found -- refusing to pass.")
        return 1

    problems: list[str] = []
    found = 0
    for relative in paths:
        text = (ROOT / relative).read_text(encoding="utf-8", errors="replace")
        if "ChelseaKR/tods-validate" not in text:
            continue
        file_problems, file_found = scan_text(relative, text, current)
        problems.extend(file_problems)
        found += file_found

    if problems:
        print(f"Documented pins do not name the current release (v{current}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    if found == 0:
        print(
            "check_action_refs: no documented pin was found in any tracked "
            "Markdown or YAML file. README.md and .pre-commit-hooks.yaml both "
            "carry one, so this is the scanner failing, not the examples "
            "passing -- refusing to report a pass."
        )
        return 1

    print(f"action refs current: {found} documented pin(s), all naming v{current}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
