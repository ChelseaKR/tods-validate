"""Baseline and diff support.

A *baseline* is a previously captured set of findings (a JSON report written by
``--format json``). Comparing the current run against it answers "what changed?"
— which findings are new, which were fixed, which persist — so CI can fail only
on newly introduced problems and a consultant can show a client their progress.

Findings are identified by content fingerprint (``Finding.fingerprint()``): a
SHA-256 hash of the rule ID, file, field, and the rule's structured machine
context (``data`` — offending value, referenced ID, etc., from FIX-05), with
row number and message text deliberately excluded. Regenerating a feed and
inserting one row no longer marks every subsequent finding "new" and every
baseline entry "fixed" — the failure mode this replaces.

Honesty note: this is a heuristic, not an exact match. Two things still churn
identity even though nothing "moved":

* **Renumbered rows on a rule without machine context.** A rule that has not
  been migrated to populate ``data`` fingerprints on (rule_id, file, field)
  alone; multiple findings from that rule in the same file/field can collide
  onto the same fingerprint. Populating ``data`` (FIX-05) is what makes a
  rule's findings distinguishable independent of row number.
* **Revalued rows.** If a row's *content* changes — not just its position —
  the offending value (part of ``data``) changes too, so the fingerprint
  changes even though the row number may not have moved. This is correct
  (it is a different problem now) but worth knowing: "moved" below only
  covers position churn, not content churn.

Reports written before the fingerprint field existed (``reportVersion`` <
1.3.0) are still readable: ``load_baseline_identities`` recomputes the
fingerprint from ``data``/``file``/``field``/``rule_id`` when the stored
``fingerprint`` is missing, and falls back further to the legacy
(rule_id, pointer, message) identity for reports that predate ``data``
entirely.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .findings import Finding, fingerprint_from_parts

# A finding's identity is either its content fingerprint (a hex SHA-256
# string) or, for baseline entries too old to carry a fingerprint or `data`,
# the legacy (rule_id, pointer, message) tuple.
Identity = str | tuple[str, str, str]


def finding_identity(finding: Finding) -> str:
    """The finding's content fingerprint — see module docstring."""
    return finding.fingerprint()


def _legacy_identity(finding: Finding) -> tuple[str, str, str]:
    """Pre-fingerprint identity: (rule_id, pointer, message).

    Kept as a fallback identity function for baseline reports that lack
    ``data``/``fingerprint`` entirely, so an old baseline doesn't
    false-positive every finding as newly introduced the first time it's
    diffed against a fingerprint-aware run.
    """
    return (finding.rule_id, finding.pointer() or "", finding.message)


def _identity_from_dict(d: dict[str, object]) -> Identity:
    """Recover a finding's identity from a JSON report's finding dict.

    Prefers a stored ``fingerprint``; falls back to recomputing one from
    ``data``/``file``/``field``/``rule_id`` if the report is new enough to
    carry ``data`` but old enough to predate the ``fingerprint`` field;
    falls back further to the legacy tuple identity for reports that predate
    structured data entirely.
    """
    fingerprint = d.get("fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return fingerprint
    if "data" in d:
        raw_data = d.get("data")
        data: Mapping[str, str] | None = raw_data if isinstance(raw_data, dict) else None
        raw_file = d.get("file")
        raw_field = d.get("field")
        return fingerprint_from_parts(
            str(d.get("rule_id", "")),
            raw_file if isinstance(raw_file, str) else None,
            raw_field if isinstance(raw_field, str) else None,
            data,
        )
    return (str(d.get("rule_id", "")), str(d.get("location") or ""), str(d.get("message", "")))


def load_baseline_identities(path: str | Path) -> set[Identity]:
    """Read the finding identities from a JSON report file.

    Raises ``ValueError`` (alongside the ``OSError``/``json.JSONDecodeError``
    a caller already expects from a missing file or invalid JSON) when the
    parsed JSON is not shaped like a report: a truncated or hand-edited
    ``--baseline`` file is plausible input, and it should fail with a clear
    message rather than an ``AttributeError``/``TypeError`` from treating a
    list, string, or malformed ``findings`` entry as a finding dict.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: expected a JSON object with a 'findings' array, got {type(data).__name__}."
        )
    findings = data.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError(f"{path}: 'findings' must be an array, got {type(findings).__name__}.")
    identities: set[Identity] = set()
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError(
                f"{path}: each entry in 'findings' must be an object, got {type(item).__name__}."
            )
        identities.add(_identity_from_dict(item))
    return identities


def new_findings(findings: Iterable[Finding], baseline: set[Identity]) -> list[Finding]:
    """Findings whose identity is not in the baseline.

    Checked against both the content fingerprint and the legacy tuple
    identity, so a baseline captured before fingerprints existed still
    suppresses the findings it already recorded.
    """
    return [
        f
        for f in findings
        if finding_identity(f) not in baseline and _legacy_identity(f) not in baseline
    ]


@dataclass
class Diff:
    fixed: list[Finding]
    introduced: list[Finding]
    persisting: list[Finding]
    # Findings whose fingerprint matches an old finding but whose
    # pointer (file/row/field) differs — the row shifted but it's the same
    # underlying problem. Reported separately from ``persisting`` so churn is
    # visible without being counted as ``introduced``.
    moved: list[Finding]


def diff_findings(old: list[Finding], new: list[Finding]) -> Diff:
    old_ids: dict[Identity, Finding] = {finding_identity(f): f for f in old}
    new_ids: dict[Identity, Finding] = {finding_identity(f): f for f in new}
    fixed = sorted(
        (old_ids[k] for k in old_ids if k not in new_ids),
        key=lambda f: (f.rule_id, f.pointer() or "", f.message),
    )
    introduced = [f for k, f in new_ids.items() if k not in old_ids]
    moved = [f for k, f in new_ids.items() if k in old_ids and f.pointer() != old_ids[k].pointer()]
    persisting = [
        f for k, f in new_ids.items() if k in old_ids and f.pointer() == old_ids[k].pointer()
    ]
    return Diff(fixed=fixed, introduced=introduced, persisting=persisting, moved=moved)
