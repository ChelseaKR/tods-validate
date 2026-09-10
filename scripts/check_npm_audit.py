#!/usr/bin/env python3
"""Adjudicate `npm audit` findings against the committed waiver registry.

The Node dependency audit (SEC-11) is merge-blocking: any HIGH or CRITICAL
advisory in the accessibility toolchain fails this gate. `npm audit` has no way
to accept one advisory, so the only lever it offers is `--audit-level`, which
is a blunt instrument: raising it hides every finding at that severity, not the
one that was actually reviewed.

This gate keeps the severity floor where it is and adjudicates advisory by
advisory against waivers.yml instead. An advisory passes only when a
non-expired waiver names that exact advisory id, that exact package, that
exact severity, and the npm project it was reported in. Everything else fails:

  * an advisory with no waiver (a new finding still breaks the build);
  * a waived advisory id reported against a different package;
  * a waived advisory whose severity has since been escalated;
  * a waived advisory reported in a different npm project;
  * a waiver that has expired, or is missing a required field;
  * an `npm audit` report this gate cannot parse, or a count of HIGH/CRITICAL
    findings that the parsed advisories do not account for.

Every npm project in the repository is audited, not just the one at the root.
`npm audit` reads the lockfile in its working directory and nothing else, so a
gate that runs it once at the root reports on one dependency tree and says
nothing about any other. This repository has two -- the accessibility toolchain
at the root and the VS Code extension under `editor/vscode/` -- and on
2026-09-10 the second carried a live HIGH advisory (GHSA-2883-xcg3-v3hh in
js-yaml) that this gate could not see. The extension had its own
`npm audit --audit-level=high` step in `.github/workflows/vscode-extension.yml`,
but that workflow is path-filtered to `editor/vscode/**`: it runs when the
lockfile changes, and an advisory is published against a lockfile that has not.

The project list is discovered by walking the tree for lockfiles rather than
being written down, so adding a third npm project puts it under the gate
without anyone remembering to. A walk that finds nothing is a broken reader,
not a repository with no dependencies, and fails.

Run it via `make npm-audit`. `--audit-json` reads a recorded report instead of
invoking npm, which is how tests/test_npm_audit_gate.py proves the waiver is
bounded without a network call.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WAIVERS_PATH = ROOT / "waivers.yml"

# Severities this gate blocks on. Matches the `npm audit --audit-level=high`
# floor this script replaces; lowering it would be a policy change, not a
# refactor.
BLOCKING = frozenset({"high", "critical"})

# Waiver fields the portfolio registry format requires of every entry, plus the
# three that make an npm-audit waiver specific enough to be safe.
REQUIRED_FIELDS = (
    "id",
    "control",
    "repo",
    "kind",
    "reason",
    "owner",
    "granted",
    "expires",
    "advisory",
    "package",
    "severity",
)

# The npm project a waiver applies to, as a repository-relative POSIX path.
# `tree` is optional because every waiver written before this gate audited more
# than one project meant the root, and defaulting keeps that meaning rather
# than silently widening it to every project: a waiver whose prose argues about
# the accessibility toolchain must not accept the same advisory in the VS Code
# extension's dependency tree. A waiver naming a directory that holds no
# lockfile is a problem, so a waiver does not outlive the project it describes.
ROOT_TREE = "."
WAIVER_TREE_FIELD = "tree"

# Directories the lockfile walk never descends into. `node_modules` is the one
# that matters -- an installed tree contains hundreds of `package-lock.json`
# files belonging to dependencies, none of which is a project of this
# repository -- and the rest are build, cache and worktree output that can hold
# a copy of a real one.
_PRUNED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".worktrees",
        "build",
        "dist",
        "htmlcov",
        "mutants",
        "node_modules",
        "sbom-env",
    }
)

# `  - key: value` opens a waiver; `    key: value` adds a field to it; a line
# indented further continues the field above it. Prose inside a folded `reason:`
# is therefore never mistaken for a field, however it is punctuated -- which
# matters, because the prose is the part a human reviews.
_ENTRY_RE = re.compile(r"^  - ([a-z_]+):[ \t]*(.*)$")
_FIELD_RE = re.compile(r"^    ([a-z_]+):[ \t]*(.*)$")
_FOLD_RE = re.compile(r"^ {6,}(\S.*)$")
_BLOCK_INDICATORS = frozenset({">", ">-", ">+", "|", "|-", "|+"})

_ADVISORY_URL_RE = re.compile(r"(GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})", re.IGNORECASE)


def parse_waivers(text: str) -> list[dict[str, str]]:
    """Return every waiver entry in the registry as a field mapping.

    A deliberately small YAML subset -- the same shape scripts/check_waivers.py
    reads elsewhere in the portfolio -- so a security gate needs no third-party
    parser to decide whether a finding has been accepted.
    """

    waivers: list[dict[str, str]] = []
    field_name = ""
    for line in text.splitlines():
        match = _ENTRY_RE.match(line) or _FIELD_RE.match(line)
        if match is not None:
            if _ENTRY_RE.match(line) is not None:
                waivers.append({})
            if not waivers:
                continue
            field_name = match.group(1)
            value = match.group(2).strip()
            waivers[-1][field_name] = "" if value in _BLOCK_INDICATORS else value
            continue
        folded = _FOLD_RE.match(line)
        if folded is not None and waivers and field_name:
            existing = waivers[-1].get(field_name, "")
            waivers[-1][field_name] = f"{existing} {folded.group(1).strip()}".strip()
            continue
        if not line.strip():
            continue
        field_name = ""
    return waivers


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def npm_projects(root: Path) -> list[str]:
    """Every npm project in the tree, as repository-relative POSIX paths.

    A project is a directory holding a `package-lock.json`, because that is the
    file `npm audit` reads: a `package.json` with no lock has no resolved
    versions to adjudicate, and npm refuses to audit it. Discovered rather than
    listed so a project added later is audited without an edit here, and sorted
    with the root first so the output is stable.

    The walk prunes `node_modules`, which is the difference between two
    projects and several hundred. A tree with no lockfile at all returns the
    empty list, and the caller fails on it -- see the note in `main`.
    """

    projects: list[str] = []
    for lockfile in root.rglob("package-lock.json"):
        relative = lockfile.relative_to(root)
        if any(part in _PRUNED_DIRECTORIES for part in relative.parts[:-1]):
            continue
        directory = relative.parent.as_posix()
        projects.append(ROOT_TREE if directory == "" else directory)
    return sorted(set(projects), key=lambda path: (path != ROOT_TREE, path))


def npm_audit_waivers(
    text: str, repo: str, today: date, projects: list[str] | None = None
) -> tuple[dict[tuple[str, str], dict[str, str]], list[str]]:
    """Usable npm-audit waivers keyed by (npm project, advisory id), and problems.

    A waiver that fails validation is not returned, so a malformed or expired
    entry cannot accept anything: the gate fails closed on both counts.

    `projects` is the list `npm_projects` found. When it is given, a waiver
    naming a directory that is not one of them is a problem rather than a
    waiver that quietly matches nothing -- a renamed or deleted npm project
    should surface the stale waiver, not hide it.
    """

    problems: list[str] = []
    usable: dict[tuple[str, str], dict[str, str]] = {}
    for waiver in parse_waivers(text):
        if waiver.get("kind") != "npm-audit":
            continue
        waiver_id = waiver.get("id") or "<missing id>"
        problem = _waiver_problem(waiver, repo, today, projects)
        if problem is not None:
            problems.append(f"{waiver_id}: {problem}")
            continue
        key = (waiver.get(WAIVER_TREE_FIELD) or ROOT_TREE, waiver["advisory"].upper())
        if key in usable:
            problems.append(f"{waiver_id}: duplicate waiver for {key[1]} in {key[0]}")
            continue
        usable[key] = waiver
    return usable, problems


def _waiver_problem(
    waiver: dict[str, str], repo: str, today: date, projects: list[str] | None
) -> str | None:
    """Why this npm-audit waiver cannot be used, or None if it can.

    Every branch returns a reason rather than raising, so a registry with two
    broken entries reports both -- a gate that stopped at the first one would
    have to be run once per problem.
    """

    missing = [field for field in REQUIRED_FIELDS if not waiver.get(field)]
    if missing:
        return f"missing required field(s): {', '.join(missing)}"
    if waiver["repo"] != repo:
        return f"repo is {waiver['repo']}, not {repo}"
    granted = _parse_date(waiver["granted"])
    expires = _parse_date(waiver["expires"])
    if granted is None or expires is None:
        return "granted and expires must be ISO dates"
    if expires < granted:
        return "expiry precedes granted date"
    if expires < today:
        return f"expired on {waiver['expires']}; re-review the advisory or let the gate block"
    if waiver["severity"] not in BLOCKING:
        return f"severity {waiver['severity']!r} is not one this gate blocks on"
    tree = waiver.get(WAIVER_TREE_FIELD) or ROOT_TREE
    if projects is not None and tree not in projects:
        return (
            f"{WAIVER_TREE_FIELD} is {tree!r}, which is not an npm project in this "
            f"repository ({', '.join(projects)})"
        )
    return None


def advisory_id(via: dict[str, Any]) -> str:
    """Return the GHSA id for an npm advisory object, or its numeric source."""

    match = _ADVISORY_URL_RE.search(str(via.get("url", "")))
    if match is not None:
        return match.group(1).upper()
    return f"npm-source-{via.get('source', 'unknown')}"


def report_advisories(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the distinct advisory objects an `npm audit --json` report names.

    npm reports one entry per affected package: the packages that carry the
    advisory itself have object-shaped `via` entries, and everything downstream
    just names the package it inherited the problem from. Adjudicating the
    advisory objects therefore covers the whole propagated set.
    """

    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    vulnerabilities = report.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict):
        return []
    for entry in vulnerabilities.values():
        if not isinstance(entry, dict):
            continue
        for via in entry.get("via", []):
            if not isinstance(via, dict):
                continue
            key = (
                advisory_id(via),
                str(via.get("name", "")),
                str(via.get("severity", "")).lower(),
            )
            seen.setdefault(key, via)
    return [
        {"id": key[0], "package": key[1], "severity": key[2], "via": via}
        for key, via in seen.items()
    ]


def blocking_total(report: dict[str, Any]) -> int | None:
    """The HIGH + CRITICAL count npm itself reports, or None if it is unreadable.

    None is not zero, and the distinction is the whole point. This used to
    return 0 for a report whose `metadata.vulnerabilities` was missing, was
    not an object, or held a count that was not a number. Zero disarms the
    cross-check in `adjudicate` that exists to catch a report this gate has
    stopped understanding -- `blocking_total(report) > 0` is false, so the
    check never fires -- and the gate then prints "no unwaived HIGH/CRITICAL
    advisories" and exits 0. That is the exact failure the docstring at the
    top of this file promises against, so the unreadable case is reported as
    unreadable and the caller fails on it.
    """

    metadata = report.get("metadata")
    if not isinstance(metadata, dict):
        return None
    counts = metadata.get("vulnerabilities")
    if not isinstance(counts, dict):
        return None
    total = 0
    for severity in sorted(BLOCKING):
        value = counts.get(severity)
        # bool is an int subclass; `"high": true` is not a count.
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        total += value
    return total


def adjudicate(
    report: dict[str, Any],
    waivers: dict[tuple[str, str], dict[str, str]],
    tree: str = ROOT_TREE,
) -> tuple[list[str], list[str], set[tuple[str, str]]]:
    """Return (failures, accepted, matched waiver keys) for one audit report.

    `matched` comes back to the caller rather than being consumed here, because
    "this waiver matched nothing" is a statement about every project's report
    together: a waiver scoped to one project matches nothing in the others by
    construction, and reporting that per project would say a live waiver is
    retirable once per npm project in the repository.
    """

    failures: list[str] = []
    accepted: list[str] = []
    matched: set[tuple[str, str]] = set()

    advisories = report_advisories(report)
    blocking = [item for item in advisories if item["severity"] in BLOCKING]

    vulnerabilities = report.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict):
        # `report_advisories` returns [] for this, which is indistinguishable
        # from a clean tree. The --audit-json path never checked the shape at
        # all, and run_npm_audit only checked that the key was present.
        failures.append(
            "npm audit's report has no readable 'vulnerabilities' object; refusing to "
            "pass a report it does not understand"
        )

    reported_blocking = blocking_total(report)
    if reported_blocking is None:
        failures.append(
            "this gate could not read the HIGH/CRITICAL counts npm reported in "
            "metadata.vulnerabilities; refusing to pass a report it does not understand"
        )
    elif reported_blocking > 0 and not blocking:
        failures.append(
            "npm reports HIGH/CRITICAL findings but this gate parsed no advisory objects "
            "from the report; refusing to pass a report it does not understand"
        )

    for item in blocking:
        waiver = waivers.get((tree, item["id"]))
        if waiver is None:
            failures.append(
                f"{item['id']} ({item['severity']}) in {item['package']}: no waiver. "
                f"{item['via'].get('title', 'no title')}"
            )
            continue
        matched.add((tree, item["id"]))
        if waiver["package"] != item["package"]:
            failures.append(
                f"{item['id']}: waiver {waiver['id']} covers package {waiver['package']}, "
                f"but the advisory is reported against {item['package']}"
            )
            continue
        if waiver["severity"] != item["severity"]:
            failures.append(
                f"{item['id']}: waiver {waiver['id']} accepts severity {waiver['severity']}, "
                f"but npm now reports {item['severity']}"
            )
            continue
        accepted.append(
            f"{item['id']} ({item['severity']}) in {item['package']}: accepted by "
            f"{waiver['id']}, expires {waiver['expires']}"
        )

    return failures, accepted, matched


def run_npm_audit(prefix: Path) -> tuple[dict[str, Any] | None, str]:
    """Run `npm audit --json` and return the parsed report, or an error string."""

    npm = shutil.which("npm")
    if npm is None:
        return None, "npm is not on PATH; the Node dependency audit cannot run"
    proc = subprocess.run(  # noqa: S603 - fixed argv, resolved binary, no shell
        [npm, "audit", "--json"],
        capture_output=True,
        text=True,
        cwd=prefix,
        check=False,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, (
            "npm audit did not emit parseable JSON "
            f"(exit {proc.returncode}):\n{proc.stdout[:2000]}\n{proc.stderr[:2000]}"
        )
    if not isinstance(report, dict) or "vulnerabilities" not in report:
        return None, f"npm audit emitted no vulnerability report (exit {proc.returncode})"
    if report.get("error"):
        return None, f"npm audit reported an error: {report['error']}"
    return report, ""


def coverage_line(audited: list[str], projects: list[str]) -> str:
    """The two numbers, always both.

    `audited` counts the projects whose report this run actually adjudicated;
    `projects` counts the ones it found. They differ exactly when an audit
    could not be run or read, and that is the case where a single number lies:
    "no unwaived HIGH/CRITICAL advisories" over a project nobody managed to
    audit is the absence of a measurement printed as a clean result.
    """

    return (
        f"npm audit: adjudicated {len(audited)} of {len(projects)} npm project(s) "
        f"[{', '.join(audited) or 'none'}]"
    )


def _recorded_report(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Read a recorded `npm audit --json` report, mirroring run_npm_audit's shape."""

    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read {path}: {exc}"
    if not isinstance(report, dict):
        return None, f"{path} does not hold an npm audit report object"
    return report, ""


def _audit_projects(
    projects: list[str],
    waivers: dict[tuple[str, str], dict[str, str]],
    root: Path,
    audit_json: Path | None,
) -> tuple[list[str], list[str], set[tuple[str, str]], list[str]]:
    """Adjudicate every project, returning (failures, accepted, matched, audited).

    `audited` is deliberately a separate list from `projects`: a project whose
    audit could not be read is a failure *and* is absent from the coverage
    count, so the run cannot report having examined something it did not.
    """

    failures: list[str] = []
    accepted: list[str] = []
    matched: set[tuple[str, str]] = set()
    audited: list[str] = []

    for tree in projects:
        if audit_json is not None:
            report, error = _recorded_report(audit_json)
        else:
            report, error = run_npm_audit(root / tree)
        if report is None:
            failures.append(f"{tree}: {error}")
            continue

        tree_failures, tree_accepted, tree_matched = adjudicate(report, waivers, tree)
        failures.extend(f"{tree}: {failure}" for failure in tree_failures)
        accepted.extend(f"{tree}: {line}" for line in tree_accepted)
        matched |= tree_matched
        audited.append(tree)

    return failures, accepted, matched, audited


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-json",
        type=Path,
        default=None,
        help="read a recorded `npm audit --json` report instead of running npm",
    )
    parser.add_argument("--waivers", type=Path, default=WAIVERS_PATH)
    parser.add_argument("--repo", default="tods-validate")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--today",
        default=None,
        help="ISO date to evaluate waiver expiry against (tests only)",
    )
    args = parser.parse_args(argv)

    today = _parse_date(args.today) if args.today else date.today()
    if today is None:
        print(f"--today is not an ISO date: {args.today}", file=sys.stderr)
        return 2

    if not args.waivers.exists():
        print(f"waiver registry not found: {args.waivers}", file=sys.stderr)
        return 1

    # `--audit-json` supplies one recorded report, which stands for the root
    # project; discovery is only meaningful when npm is actually being run.
    projects = [ROOT_TREE] if args.audit_json is not None else npm_projects(args.root)
    if not projects:
        # Not "this repository has no npm dependencies": this file lives beside
        # a package-lock.json that has been committed since the accessibility
        # gate was written, so an empty walk is a reader that stopped working.
        print(
            f"found no npm project (no package-lock.json) under {args.root}; refusing to "
            "report a clean audit over nothing",
            file=sys.stderr,
        )
        return 1

    waivers, waiver_problems = npm_audit_waivers(
        args.waivers.read_text(encoding="utf-8"), args.repo, today, projects
    )

    failures, accepted, matched, audited = _audit_projects(
        projects, waivers, args.root, args.audit_json
    )
    failures = list(waiver_problems) + failures

    for key, waiver in sorted(waivers.items()):
        if key not in matched:
            tree, advisory = key
            print(
                f"note: waiver {waiver['id']} for {advisory} matched nothing in {tree}; "
                f"it can be retired",
                file=sys.stderr,
            )

    for line in accepted:
        print(f"npm audit: {line}")

    coverage = coverage_line(audited, projects)
    if failures:
        print(coverage, file=sys.stderr)
        print("npm audit gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        print(
            "\nA HIGH or CRITICAL advisory blocks merge. Fix it, or record a dated,"
            "\nnarrowly scoped waiver in waivers.yml naming the advisory id, the"
            "\npackage, the severity, an owner, an expiry, and -- for a project"
            "\nother than the repository root -- the `tree` it applies to.",
            file=sys.stderr,
        )
        return 1

    print(coverage)
    print(f"npm audit: no unwaived HIGH/CRITICAL advisories ({len(accepted)} waived)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
