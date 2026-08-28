#!/usr/bin/env python3
"""Fail when the incident-response contract is only prose (IR-05/07/15/16/17).

`docs/standards/INCIDENT-RESPONSE-STANDARD.md` asks for four things to be
mechanically checked rather than described: the label set exists, every
postmortem carries its required sections, no unattended automation stages files
with a wildcard, and no unattended automation commits without a secret scan
first. This is that check.

The last two are regression guards: both were already clean when this landed.
That is stated rather than implied, because a guard that has never had anything
to catch and a guard that is not looking render identically, and this
repository has shipped the second kind before. Each check reports what it
scanned, so a run that inspected nothing cannot read as a run that found
nothing.

Run by `make incident-check` (a `make verify` gate) and by
`tests/test_incident_contract.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / ".github" / "labels.yml"
INCIDENTS = ROOT / "docs" / "incidents"
TEMPLATE = INCIDENTS / "TEMPLATE.md"

# IR-02, IR-04, IR-17. The label a postmortem's timeline depends on existing.
REQUIRED_LABELS = frozenset({"incident", "sev1", "sev2", "sev3", "sev4", "deploy-caused"})

# IR-07, verbatim from the standard's required-section list. Rendered as `##`
# headings by the template, except Severity, which is a bold front field.
REQUIRED_SECTIONS = (
    "## Summary",
    "## Timeline (UTC)",
    "## Impact",
    "## Detection",
    "## Root cause",
    "## What went well",
    "## What went poorly",
    "## Action items",
    "## Related",
)
REQUIRED_FIELDS = ("**Severity:**",)

# IR-15. Anything unattended that stages by wildcard can stage a secret nobody
# named. Matches the three spellings the standard lists.
WILDCARD_ADD = re.compile(r"git\s+add\s+(-A|--all|\.)(\s|$)")
# IR-16. A scripted commit in unattended automation must be preceded by a scan.
SCRIPTED_COMMIT = re.compile(r"git\s+commit\b")
SECRET_SCAN = re.compile(r"gitleaks|trufflehog|detect-secrets")

# Where unattended automation lives. Documentation is excluded deliberately:
# this runbook and this standard both quote `git add -A` in order to forbid it,
# and a lint that cannot tell a prohibition from an instance is a lint that gets
# muted.
AUTOMATION_GLOBS = ("scripts/*.py", "scripts/*.sh", "scripts/*.cjs", ".github/workflows/*.yml")


def _automation_files() -> list[Path]:
    return sorted(path for glob in AUTOMATION_GLOBS for path in ROOT.glob(glob))


def check_labels() -> list[str]:
    """IR-17: the label convention is declared, and declares the whole set."""
    if not LABELS.exists():
        return [f"{LABELS.relative_to(ROOT)} does not exist; the label convention is prose only"]
    declared = set(re.findall(r"^\s*-\s*name:\s*(\S+)", LABELS.read_text(encoding="utf-8"), re.M))
    missing = REQUIRED_LABELS - declared
    problems = []
    if missing:
        names = ", ".join(sorted(missing))
        problems.append(f"{LABELS.relative_to(ROOT)} does not declare {names} (IR-02/IR-17)")
    return problems


def check_postmortems() -> tuple[list[str], int]:
    """IR-05/IR-07: every committed postmortem carries its required sections."""
    if not INCIDENTS.is_dir():
        return [f"{INCIDENTS.relative_to(ROOT)} does not exist (IR-05)"], 0
    problems: list[str] = []
    files = sorted(p for p in INCIDENTS.glob("*.md") if p.name != "README.md")
    if TEMPLATE not in files:
        problems.append(f"{TEMPLATE.relative_to(ROOT)} does not exist (IR-07 has no template)")
    for path in files:
        text = path.read_text(encoding="utf-8")
        missing = [s for s in (*REQUIRED_SECTIONS, *REQUIRED_FIELDS) if s not in text]
        if missing:
            problems.append(f"{path.relative_to(ROOT)}: missing {', '.join(missing)} (IR-07)")
    return problems, len(files)


def check_wildcard_add() -> tuple[list[str], int]:
    """IR-15: no wildcard staging in unattended automation."""
    problems = []
    files = _automation_files()
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if WILDCARD_ADD.search(line):
                problems.append(
                    f"{path.relative_to(ROOT)}:{number}: wildcard `git add` in unattended "
                    f"automation (IR-15): {line.strip()}"
                )
    return problems, len(files)


def check_commit_is_scanned() -> tuple[list[str], int]:
    """IR-16: a scripted commit is preceded by a secret scan in the same file."""
    problems = []
    sites = 0
    for path in _automation_files():
        text = path.read_text(encoding="utf-8")
        if not SCRIPTED_COMMIT.search(text):
            continue
        sites += 1
        if not SECRET_SCAN.search(text):
            problems.append(
                f"{path.relative_to(ROOT)}: commits without a secret scan in the same file (IR-16)"
            )
    return problems, sites


def main() -> int:
    problems = list(check_labels())
    postmortem_problems, postmortems = check_postmortems()
    wildcard_problems, scanned = check_wildcard_add()
    commit_problems, commit_sites = check_commit_is_scanned()
    problems += postmortem_problems + wildcard_problems + commit_problems

    print(f"labels declared:      {LABELS.relative_to(ROOT)} ({len(REQUIRED_LABELS)} required)")
    print(f"postmortems checked:  {postmortems} (template included)")
    print(f"automation scanned:   {scanned} file(s) for IR-15")
    print(f"commit sites found:   {commit_sites} (IR-16)")
    if commit_sites == 0:
        print("  none: no tracked automation in this repository commits unattended.")

    if problems:
        for problem in problems:
            print(f"::error::{problem}")
        return 1
    print("incident-response contract holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
