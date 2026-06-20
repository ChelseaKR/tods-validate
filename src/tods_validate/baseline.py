"""Baseline and diff support.

A *baseline* is a previously captured set of findings (a JSON report written by
``--format json``). Comparing the current run against it answers "what changed?"
— which findings are new, which were fixed, which persist — so CI can fail only
on newly introduced problems and a consultant can show a client their progress.

Findings are identified by (rule_id, location-pointer, message). Row numbers
shift as a file is edited, so the message is part of the identity to keep a
finding recognizable across small edits; this is a heuristic, not exact.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .findings import Finding


def finding_identity(finding: Finding) -> tuple[str, str, str]:
    return (finding.rule_id, finding.pointer() or "", finding.message)


def _identity_from_dict(d: dict[str, object]) -> tuple[str, str, str]:
    return (str(d.get("rule_id", "")), str(d.get("location") or ""), str(d.get("message", "")))


def load_baseline_identities(path: str | Path) -> set[tuple[str, str, str]]:
    """Read the finding identities from a JSON report file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {_identity_from_dict(f) for f in data.get("findings", [])}


def new_findings(findings: Iterable[Finding], baseline: set[tuple[str, str, str]]) -> list[Finding]:
    """Findings whose identity is not in the baseline."""
    return [f for f in findings if finding_identity(f) not in baseline]


@dataclass
class Diff:
    fixed: list[tuple[str, str, str]]
    introduced: list[Finding]
    persisting: list[Finding]


def diff_findings(old: list[Finding], new: list[Finding]) -> Diff:
    old_ids = {finding_identity(f): f for f in old}
    new_ids = {finding_identity(f): f for f in new}
    fixed = sorted(k for k in old_ids if k not in new_ids)
    introduced = [f for k, f in new_ids.items() if k not in old_ids]
    persisting = [f for k, f in new_ids.items() if k in old_ids]
    return Diff(fixed=fixed, introduced=introduced, persisting=persisting)
