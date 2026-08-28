#!/usr/bin/env python3
"""Adjudicate `npm audit` findings against the committed waiver registry.

The Node dependency audit (SEC-11) is merge-blocking: any HIGH or CRITICAL
advisory in the accessibility toolchain fails this gate. `npm audit` has no way
to accept one advisory, so the only lever it offers is `--audit-level`, which
is a blunt instrument: raising it hides every finding at that severity, not the
one that was actually reviewed.

This gate keeps the severity floor where it is and adjudicates advisory by
advisory against waivers.yml instead. An advisory passes only when a
non-expired waiver names that exact advisory id, that exact package, and that
exact severity. Everything else fails:

  * an advisory with no waiver (a new finding still breaks the build);
  * a waived advisory id reported against a different package;
  * a waived advisory whose severity has since been escalated;
  * a waiver that has expired, or is missing a required field;
  * an `npm audit` report this gate cannot parse, or a count of HIGH/CRITICAL
    findings that the parsed advisories do not account for.

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


def npm_audit_waivers(
    text: str, repo: str, today: date
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Return usable npm-audit waivers keyed by advisory id, plus any problems.

    A waiver that fails validation is not returned, so a malformed or expired
    entry cannot accept anything: the gate fails closed on both counts.
    """

    problems: list[str] = []
    usable: dict[str, dict[str, str]] = {}
    for waiver in parse_waivers(text):
        if waiver.get("kind") != "npm-audit":
            continue
        waiver_id = waiver.get("id") or "<missing id>"
        missing = [field for field in REQUIRED_FIELDS if not waiver.get(field)]
        if missing:
            problems.append(f"{waiver_id}: missing required field(s): {', '.join(missing)}")
            continue
        if waiver["repo"] != repo:
            problems.append(f"{waiver_id}: repo is {waiver['repo']}, not {repo}")
            continue
        granted = _parse_date(waiver["granted"])
        expires = _parse_date(waiver["expires"])
        if granted is None or expires is None:
            problems.append(f"{waiver_id}: granted and expires must be ISO dates")
            continue
        if expires < granted:
            problems.append(f"{waiver_id}: expiry precedes granted date")
            continue
        if expires < today:
            problems.append(
                f"{waiver_id}: expired on {waiver['expires']}; re-review the advisory "
                f"or let the gate block"
            )
            continue
        if waiver["severity"] not in BLOCKING:
            problems.append(
                f"{waiver_id}: severity {waiver['severity']!r} is not one this gate blocks on"
            )
            continue
        advisory = waiver["advisory"].upper()
        if advisory in usable:
            problems.append(f"{waiver_id}: duplicate waiver for {advisory}")
            continue
        usable[advisory] = waiver
    return usable, problems


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
    report: dict[str, Any], waivers: dict[str, dict[str, str]]
) -> tuple[list[str], list[str]]:
    """Return (failures, accepted) for one audit report."""

    failures: list[str] = []
    accepted: list[str] = []
    matched: set[str] = set()

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
        waiver = waivers.get(item["id"])
        if waiver is None:
            failures.append(
                f"{item['id']} ({item['severity']}) in {item['package']}: no waiver. "
                f"{item['via'].get('title', 'no title')}"
            )
            continue
        matched.add(item["id"])
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

    for advisory, waiver in sorted(waivers.items()):
        if advisory not in matched:
            print(
                f"note: waiver {waiver['id']} for {advisory} matched nothing in this report; "
                f"it can be retired",
                file=sys.stderr,
            )
    return failures, accepted


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
    waivers, waiver_problems = npm_audit_waivers(
        args.waivers.read_text(encoding="utf-8"), args.repo, today
    )

    if args.audit_json is not None:
        try:
            report = json.loads(args.audit_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"could not read {args.audit_json}: {exc}", file=sys.stderr)
            return 1
    else:
        report, error = run_npm_audit(ROOT)
        if report is None:
            print(error, file=sys.stderr)
            return 1

    failures, accepted = adjudicate(report, waivers)
    failures = waiver_problems + failures

    for line in accepted:
        print(f"npm audit: {line}")
    if failures:
        print("npm audit gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        print(
            "\nA HIGH or CRITICAL advisory blocks merge. Fix it, or record a dated,"
            "\nnarrowly scoped waiver in waivers.yml naming the advisory id, the"
            "\npackage, the severity, an owner, and an expiry.",
            file=sys.stderr,
        )
        return 1

    print(f"npm audit: no unwaived HIGH/CRITICAL advisories ({len(accepted)} waived)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
