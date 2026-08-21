"""Render findings as text, JSON, Markdown, GitHub annotations, SARIF, or HTML.

Accessibility note: severity is always carried by a word (ERROR, WARNING,
INFO), never by color alone, so reports stay readable when piped to a file or
read by a screen reader. None of these renderers emit ANSI color, so output is
identical with or without ``NO_COLOR`` set.

Finding ordering is a stability contract: findings arrive sorted by file, then
row, then rule ID (see ``rules.validate``), and every renderer preserves that
order. Golden-file consumers can rely on it.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from . import __version__
from .findings import Finding, Severity
from .loader import Package
from .rules import REGISTRY, RunCoverage
from .run_events import _Event, events_by_run, parse_events
from .schema import SPEC_VERSION
from .suggest import Suggestion

# Bumped when the JSON report shape changes. Fields are only ever added, never
# removed or renamed, within a major version; this lets consumers branch on
# shape if they need to.
#
# 1.3.0 keeps the additive ``coverage`` manifest and per-finding ``data``,
# and adds ``fingerprint`` (content-anchored identity for --baseline), the
# top-level ``suggestions`` array (machine-form ``--suggest`` output), and
# findings[].severity_original for local severity remaps.
REPORT_SCHEMA_VERSION = "1.3.0"

# Base URL for the per-rule pages published by scripts/generate_rules_doc.py
# (see web/rules/) and deployed by .github/workflows/pages.yml. SARIF's
# helpUri wants a stable, permanent link per rule -- a spec section anchor can
# move if the spec is reorganized, but ``<RULE_PAGE_BASE><rule id>.html``
# never does: rule IDs are never renumbered once released (see
# ``tods_validate.rules``). Update this alongside the Pages deployment if the
# hosting domain ever changes.
RULE_PAGE_BASE = "https://chelseakr.github.io/tods-validate/rules/"

# Rule metadata by ID, for enriching SARIF descriptors below. Built once from
# the registry, which is populated at import time.
_REGISTRY_BY_ID = {r.id: r for r in REGISTRY}

# When a single rule fires at least this many times, reports add a one-line
# root-cause hint so a wall of identical findings reads as one likely cause.
_CLUSTER_THRESHOLD = 5

# Heuristic root-cause hints keyed by rule ID, shown when a rule clusters.
_ROOT_CAUSE_HINTS = {
    "TODS-E307": (
        "many missing trips usually mean the companion GTFS export is stale or the "
        "trip_ids were renamed."
    ),
    "TODS-E308": (
        "many missing services usually mean the GTFS calendars were regenerated with "
        "new service_ids."
    ),
    "TODS-E309": (
        "many missing stops usually mean the GTFS stops.txt changed or stop_ids were renumbered."
    ),
    "TODS-E314": (
        "many dangling references usually mean a supplement was written against a "
        "different GTFS version."
    ),
    "TODS-W206": (
        "padded values across a file usually come from a fixed-width export; trim values on export."
    ),
    "TODS-W302": (
        "many unchecked references usually mean the companion GTFS moved out from under "
        "your TODS package; re-export both together so referenced files line up."
    ),
    "TODS-W313": (
        "many no-op deletes usually mean your GTFS was regenerated and the supplemented "
        "rows were already removed; regenerate the supplement against the current GTFS."
    ),
}


def summarize(findings: list[Finding]) -> Counter[Severity]:
    return Counter(f.severity for f in findings)


def _remapped(findings: list[Finding]) -> list[Finding]:
    """Findings whose severity was changed by local policy (config.py's
    ``[severity]`` table). Every renderer below must disclose these; this is
    the single query point so no output path can accidentally skip it."""
    return [f for f in findings if f.severity_original is not None]


def _remap_note(finding: Finding) -> str:
    """ "(spec: ORIGINAL)" per-finding annotation; empty string when unremapped."""
    if finding.severity_original is None:
        return ""
    return f" (spec: {finding.severity_original.name})"


def _disclosure_lines(findings: list[Finding]) -> list[str]:
    """Plain-text 'Local policy: N severit(y/ies) remapped' disclosure block.

    Listed as rule_id: ORIGINAL -> NEW, with "(acknowledged)" appended for
    remaps that downgraded an ERROR-band rule (config.py only permits those
    with an explicit acknowledgment, so any downgrade from ERROR reaching
    this point was acknowledged by construction). One line per remapped rule,
    not per finding — a rule that fires thousands of times must not turn the
    disclosure block (or the GitHub-annotation stream built from it) into
    thousands of identical lines — with a ``×N`` count when N > 1.
    """
    remapped = _remapped(findings)
    if not remapped:
        return []
    grouped: dict[tuple[str, Severity, Severity], int] = {}
    for f in remapped:
        original = f.severity_original
        if original is None:
            continue
        key = (f.rule_id, original, f.severity)
        grouped[key] = grouped.get(key, 0) + 1
    plural = "y" if len(remapped) == 1 else "ies"
    lines = [f"Local policy: {len(remapped)} severit{plural} remapped:"]
    for (rule_id, original, new), count in grouped.items():
        is_downgrade = original is Severity.ERROR and new < Severity.ERROR
        note = " (acknowledged)" if is_downgrade else ""
        times = f" ×{count}" if count > 1 else ""
        lines.append(f"  {rule_id}: {original.name} -> {new.name}{note}{times}")
    return lines


def by_rule(findings: list[Finding]) -> Counter[str]:
    """Count findings per rule ID, most frequent first when iterated."""
    return Counter(f.rule_id for f in findings)


def _distinct_error_rules(findings: list[Finding]) -> int:
    return len({f.rule_id for f in findings if f.severity == Severity.ERROR})


def _path_to_green(findings: list[Finding]) -> str | None:
    """One line describing the shortest path to a clean run, or None."""
    distinct = _distinct_error_rules(findings)
    if distinct == 0:
        return None
    return (
        f"You are {distinct} distinct error rule(s) away from a clean run; "
        "fixing each rule's root cause usually clears its whole cluster."
    )


def _cluster_hints(findings: list[Finding]) -> list[str]:
    counts = by_rule(findings)
    hints = []
    for rule_id, count in counts.most_common():
        if count >= _CLUSTER_THRESHOLD and rule_id in _ROOT_CAUSE_HINTS:
            hint = f"{rule_id} ({count}×): {_ROOT_CAUSE_HINTS[rule_id]}"
            rule_def = _REGISTRY_BY_ID.get(rule_id)
            if rule_def is not None and rule_def.example:
                hint = f"{hint} {rule_def.example}"
            hints.append(hint)
    return hints


def _max_findings(findings: list[Finding], limit: int | None) -> tuple[list[Finding], int]:
    """Apply a display cap, returning the kept findings and how many were hidden."""
    if limit is None or limit < 0 or len(findings) <= limit:
        return findings, 0
    return findings[:limit], len(findings) - limit


def _coverage_lines(coverage: RunCoverage | None, indent: str = "") -> list[str]:
    """The run's scope statement, plus one line per skip reason naming its rules.

    Emitted by every report format, on every run. The scope statement is always
    present, so "no coverage line" never has to be read as either "nothing was
    skipped" or "this format does not say"; the detail lines name the rules,
    because a bare count of skipped checks cannot be acted on.
    """
    if coverage is None:
        return []
    return [
        f"Rule-set coverage: {coverage.scope_line()}",
        *(f"{indent}{line}" for line in coverage.skipped_detail_lines()),
    ]


def render_text(  # noqa: C901 - causality grouping and severity disclosure add display branches
    findings: list[Finding],
    source: str,
    *,
    max_findings: int | None = None,
    quiet: bool = False,
    coverage: RunCoverage | None = None,
    spec_version: str = SPEC_VERSION,
) -> str:
    lines: list[str] = [f"tods-validate: {source} (TODS v{spec_version})", ""]
    if not findings:
        lines.append("No problems found.")
        lines.extend(_coverage_lines(coverage, indent="  "))
        return "\n".join(lines)

    counts = summarize(findings)
    if not quiet:
        shown, hidden = _max_findings(findings, max_findings)
        follow_on_counts = Counter(f.caused_by for f in shown if f.caused_by is not None)
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            group = [f for f in shown if f.severity == severity]
            roots = [f for f in group if f.caused_by is None]
            if not roots:
                continue
            # Findings with caused_by are downstream echoes of a root finding
            # on the same row (e.g. TODS-E201 fired only because a TODS-E104
            # ragged row left the field blank). Nothing is dropped -- every
            # rule still fired -- but here, for a human reading the terminal,
            # each echo collapses into a single "and N follow-on finding(s)"
            # line right after its root instead of repeating the same row.
            full_group = [f for f in findings if f.severity == severity]
            displayed_count = len([f for f in full_group if f.caused_by is None])
            plural = "s" if displayed_count != 1 else ""
            lines.append(f"{displayed_count} {severity.name.lower()}{plural}:")
            for f in roots:
                location = f.location()
                prefix = f"  {severity.name} {f.rule_id}{_remap_note(f)}"
                lines.append(f"{prefix} [{location}]" if location else prefix)
                lines.append(f"    {f.message}")
                if f.suggestion:
                    lines.append(f"    Fix: {f.suggestion}")
                pointer = f.pointer()
                n_follow_on = follow_on_counts.get(pointer, 0) if pointer else 0
                if n_follow_on:
                    fplural = "s" if n_follow_on != 1 else ""
                    lines.append(f"    and {n_follow_on} follow-on finding{fplural}")
            lines.append("")
        if hidden:
            lines.append(f"... and {hidden} more finding(s) not shown (--max-findings).")
            lines.append("")

    # By-rule breakdown groups a wall of findings into a few lines.
    breakdown = ", ".join(
        f"{rule_id} ×{count}" for rule_id, count in by_rule(findings).most_common()
    )
    lines.append(f"By rule: {breakdown}")
    for hint in _cluster_hints(findings):
        lines.append(f"  hint: {hint}")
    path = _path_to_green(findings)
    if path:
        lines.append(path)
    disclosure = _disclosure_lines(findings)
    if disclosure:
        lines.append("")
        lines.extend(disclosure)
    lines.append(
        "Summary: "
        f"{counts[Severity.ERROR]} error(s), "
        f"{counts[Severity.WARNING]} warning(s), "
        f"{counts[Severity.INFO]} info."
    )
    lines.extend(_coverage_lines(coverage, indent="  "))
    return "\n".join(lines)


def render_json(
    findings: list[Finding],
    source: str,
    *,
    coverage: RunCoverage | None = None,
    suggestions: list[Suggestion] | None = None,
    spec_version: str = SPEC_VERSION,
) -> str:
    counts = summarize(findings)
    payload: dict[str, object] = {
        "validator": "tods-validate",
        "toolVersion": __version__,
        "reportVersion": REPORT_SCHEMA_VERSION,
        "specVersion": spec_version,
        "source": source,
        "summary": {
            "errors": counts[Severity.ERROR],
            "warnings": counts[Severity.WARNING],
            "infos": counts[Severity.INFO],
            "byRule": dict(by_rule(findings).most_common()),
        },
        "findings": [f.to_dict() for f in findings],
    }
    if coverage is not None:
        # Additive assurance manifest: which rules ran vs. were skipped and why,
        # so a clean report is qualified by its own scope. Schema 1.2.0.
        payload["coverage"] = coverage.to_dict()
    if suggestions is not None:
        # Machine-form companion to --suggest's text/Markdown block, so a
        # dashboard can read structured current/proposed values instead of
        # parsing prose. Schema 1.3.0.
        payload["suggestions"] = [s.to_dict() for s in suggestions]
    return json.dumps(payload, indent=2)


def _stamp_footer(spec_version: str = SPEC_VERSION) -> str:
    """A provenance footer (tool version, spec version, UTC timestamp)."""
    return (
        "---\n"
        f"_Generated by tods-validate {__version__} against TODS v{spec_version} at "
        f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}._"
    )


def render_markdown(  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    findings: list[Finding],
    source: str,
    *,
    stamp: bool = False,
    coverage: RunCoverage | None = None,
    spec_version: str = SPEC_VERSION,
) -> str:
    """A report suitable for pasting into an issue or working-group thread.

    With ``stamp=True`` the report carries a provenance footer (tool version,
    spec version, UTC timestamp) for use as a citable compliance artifact. The
    stamp is opt-in because the timestamp makes output non-reproducible.

    The rule-set coverage block is *not* opt-in. It used to be printed only
    under ``stamp``, which tied a statement of what the run checked to a
    statement of when it ran; an unstamped report -- the default, and the one
    people paste into issues -- disclosed nothing.
    """
    counts = summarize(findings)
    scope_lines = _coverage_lines(coverage)
    lines = [
        "# TODS validation report",
        "",
        f"Source: `{source}`, validated against TODS v{spec_version} by tods-validate.",
        "",
    ]
    if not findings:
        lines.append("No problems found.")
        if scope_lines:
            lines.append("")
            lines.append(scope_lines[0])
            lines.extend(f"- {line}" for line in scope_lines[1:])
    else:
        lines.append(
            f"**{counts[Severity.ERROR]} error(s), {counts[Severity.WARNING]} warning(s), "
            f"{counts[Severity.INFO]} info.**"
        )
        breakdown = ", ".join(
            f"`{rule_id}` ×{count}" for rule_id, count in by_rule(findings).most_common()
        )
        lines.append("")
        lines.append(f"By rule: {breakdown}")
        for hint in _cluster_hints(findings):
            lines.append(f"> hint: {hint}")
        if scope_lines:
            lines.append("")
            lines.append(scope_lines[0])
            lines.extend(f"- {line}" for line in scope_lines[1:])
        disclosure = _disclosure_lines(findings)
        if disclosure:
            lines.append("")
            lines.append(f"> {disclosure[0]}")
            for line in disclosure[1:]:
                lines.append(f"> {line.strip()}")
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            group = [f for f in findings if f.severity == severity]
            if not group:
                continue
            lines.append("")
            lines.append(f"## {severity.name.title()}s ({len(group)})")
            lines.append("")
            for f in group:
                location = f.location()
                where = f" ({location})" if location else ""
                lines.append(f"- **{f.rule_id}**{where}: {f.message}{_remap_note(f)}")
                if f.suggestion:
                    lines.append(f"  - Fix: {f.suggestion}")
                if f.caused_by:
                    # Every finding is kept in Markdown (unlike the terminal
                    # renderer, which collapses this line into its root's
                    # follow-on count); the link just says why it's downstream.
                    lines.append(f"  - Caused by: {f.caused_by}")
    if stamp:
        lines.append("")
        lines.append(_stamp_footer(spec_version))
    return "\n".join(lines)


def _combined_batch_coverage(coverages: list[RunCoverage | None]) -> RunCoverage | None:
    """Pool every feed's per-rule outcomes into one fleet-wide RunCoverage.

    Reuses RunCoverage's own ``scope_line``/``skipped_detail_lines`` to state
    the batch's aggregate scope instead of re-deriving that logic here: the
    "42 checks" a single feed states become "42 x N feeds attempted" for the
    fleet, and the same disclosure machinery names which rules and how many
    of each severity did not run, batch-wide. None for an all-error batch (no
    feed loaded far enough to have a manifest).
    """
    outcomes = tuple(o for c in coverages if c is not None for o in c.outcomes)
    return RunCoverage(outcomes) if outcomes else None


def render_batch_markdown(
    rows: list[dict[str, object]],
    coverages: list[RunCoverage | None] | None = None,
    *,
    stamp: bool = False,
) -> str:
    """A single stamped multi-agency (fleet) compliance report.

    ``rows`` mirrors the structure ``cli.batch`` already builds: one dict per
    feed with either ``{"source", "errors", "warnings", "infos", "status"}``
    for a feed that was read successfully, or ``{"source", "error"}`` for one
    that raised ``PackageNotFoundError`` — those render with an "error"
    status distinct from "pass"/"fail". ``coverages`` is parallel to ``rows``
    (one ``RunCoverage`` per feed that loaded, ``None`` for one that did not);
    it adds a "checks not run" column so ``status: pass`` is never left to
    stand alone as "everything was checked" (#127), plus a fleet-wide
    Rule-set coverage line in the roll-up, the same disclosure every
    single-feed format already carries.

    With ``stamp=True`` the report carries the same provenance footer as
    ``render_markdown``, making it a citable artifact for a whole fleet/
    portfolio of agencies in one document instead of a per-feed report.
    """
    coverages = coverages if coverages is not None else [None] * len(rows)
    lines = [
        "# TODS fleet compliance report",
        "",
        f"{len(rows)} feed(s) validated against TODS v{SPEC_VERSION} by tods-validate.",
        "",
        "| source | errors | warnings | infos | checks not run | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    total_errors = total_warnings = total_infos = 0
    passed = failed = errored = 0
    for row, coverage in zip(rows, coverages, strict=True):
        if "error" in row:
            errored += 1
            lines.append(f"| `{row['source']}` | - | - | - | - | error |")
            continue
        status = row.get("status", "pass")
        if status == "fail":
            failed += 1
        else:
            passed += 1
        total_errors += cast(int, row["errors"])
        total_warnings += cast(int, row["warnings"])
        total_infos += cast(int, row["infos"])
        not_run = len(coverage.skipped) if coverage is not None else 0
        lines.append(
            f"| `{row['source']}` | {row['errors']} | {row['warnings']} | "
            f"{row['infos']} | {not_run} | {status} |"
        )
    lines.append("")
    lines.append(
        f"**Fleet totals: {total_errors} error(s), {total_warnings} warning(s), "
        f"{total_infos} info across {len(rows)} feed(s) "
        f"({passed} pass, {failed} fail, {errored} error).**"
    )
    combined = _combined_batch_coverage(coverages)
    if combined is not None:
        lines.append("")
        lines.append(f"Rule-set coverage: {combined.scope_line()}")
        lines.extend(combined.skipped_detail_lines())
    if stamp:
        lines.append("")
        lines.append(_stamp_footer())
    return "\n".join(lines)


def render_batch_text(
    rows: list[dict[str, object]], coverages: list[RunCoverage | None] | None = None
) -> str:
    """The ``batch`` command's default terminal roll-up table.

    See ``render_batch_markdown`` for what ``rows``/``coverages`` carry; this
    is the same disclosure (a "not run" column plus a fleet-wide Rule-set
    coverage line) in fixed-width form.
    """
    coverages = coverages if coverages is not None else [None] * len(rows)
    lines = [f"{'errors':>7} {'warnings':>9} {'infos':>6} {'not run':>8}  source"]
    for row, coverage in zip(rows, coverages, strict=True):
        if "error" in row:
            lines.append(f"{'-':>7} {'-':>9} {'-':>6} {'-':>8}  {row['source']} ({row['error']})")
            continue
        not_run = len(coverage.skipped) if coverage is not None else 0
        lines.append(
            f"{row['errors']:>7} {row['warnings']:>9} {row['infos']:>6} "
            f"{not_run:>8}  {row['source']}"
        )
    combined = _combined_batch_coverage(coverages)
    if combined is not None:
        lines.append("")
        lines.append(f"Rule-set coverage: {combined.scope_line()}")
        lines.extend(f"  {line}" for line in combined.skipped_detail_lines())
    return "\n".join(lines)


_GITHUB_COMMANDS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "notice",
}


def _escape_annotation(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_annotation_property(text: str) -> str:
    """Escape a workflow-command *property value* (e.g. ``file=``).

    Per GitHub's workflow-command spec, property values need two extra
    escapes beyond the message escaping in :func:`_escape_annotation`: ``,``
    (the property separator) and ``:`` (the key/value separator). Without
    this, a feed file whose name is attacker-chosen (surfaced verbatim by,
    e.g., TODS-I102 for any unrecognized file in the package) can inject
    extra ``file=``/``line=``/``title=`` properties into the annotation.
    """
    return _escape_annotation(text).replace(",", "%2C").replace(":", "%3A")


def render_github(
    findings: list[Finding], source: str, *, coverage: RunCoverage | None = None
) -> str:
    """Workflow command format; one annotation per finding.

    See https://docs.github.com/actions/reference/workflow-commands-for-github-actions

    This is the only format the composite action emits, so it is the format a
    transit agency or vendor actually reads. It took no ``coverage`` argument
    at all until 0.9.2: a feed validated without its companion GTFS feed
    printed "0 error(s), 0 warning(s), 0 info" and nothing else, while 16 of
    42 checks -- 9 of them ERROR-severity -- had not run. The summary line now
    always carries the run's scope, and each reason a check did not run
    becomes its own ``::notice`` annotation naming the rules, so the
    disclosure reaches the pull request's Checks tab and not only the log.
    """
    lines = []
    for f in findings:
        command = _GITHUB_COMMANDS[f.severity]
        properties = []
        if f.file:
            properties.append(f"file={_escape_annotation_property(f.file)}")
        if f.row is not None:
            properties.append(f"line={f.row}")
        properties.append(f"title={f.rule_id}")
        message = f.message if not f.suggestion else f"{f.message} Fix: {f.suggestion}"
        message += _remap_note(f)
        lines.append(f"::{command} {','.join(properties)}::{_escape_annotation(message)}")
    counts = summarize(findings)
    summary = (
        f"tods-validate: {counts[Severity.ERROR]} error(s), "
        f"{counts[Severity.WARNING]} warning(s), {counts[Severity.INFO]} info "
        f"in {source}."
    )
    if coverage is not None:
        summary = f"{summary} {coverage.scope_line()}"
    lines.append(summary)
    if coverage is not None:
        for detail in coverage.skipped_detail_lines():
            lines.append(f"::notice title=Checks that did not run::{_escape_annotation(detail)}")
    for line in _disclosure_lines(findings):
        lines.append(f"::notice::{_escape_annotation(line.strip())}")
    return "\n".join(lines)


_SARIF_LEVELS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}


def _sarif_descriptor(rule_id: str, level: str) -> dict[str, object]:
    """A SARIF reportingDescriptor, enriched from the rule registry.

    ``helpUri`` points at the rule's permanent page under ``web/rules/``
    (generated by scripts/generate_rules_doc.py and published via
    .github/workflows/pages.yml), not the spec citation directly, so it keeps
    resolving even if the spec text moves. The spec citation itself is not
    lost -- it is still surfaced via ``properties.specSection`` and on the
    rule page itself.
    """
    descriptor: dict[str, object] = {
        "id": rule_id,
        "name": rule_id,
        "defaultConfiguration": {"level": level},
    }
    rule = _REGISTRY_BY_ID.get(rule_id)
    if rule is not None:
        descriptor["name"] = rule.title
        descriptor["shortDescription"] = {"text": rule.title}
        descriptor["fullDescription"] = {"text": rule.description}
        descriptor["helpUri"] = f"{RULE_PAGE_BASE}{rule.id}.html"
        descriptor["properties"] = {
            "category": rule.category,
            "severity": rule.severity.name,
            "specSection": rule.spec_section,
        }
    return descriptor


def render_sarif(  # noqa: C901 - SARIF shape branches for locations, data, and disclosure
    findings: list[Finding], source: str, *, coverage: RunCoverage | None = None
) -> str:
    """SARIF 2.1.0, for GitHub code-scanning and security dashboards.

    Each distinct rule that fired becomes a reporting descriptor under the
    tool's ``rules`` array, enriched from the rule registry (title,
    description, and a permanent ``helpUri`` -- see ``_sarif_descriptor``);
    each finding becomes a ``result`` pointing at the file and 1-based line.
    When a coverage manifest is given, it is recorded under ``invocations`` so
    the run discloses which rules were skipped.
    """
    seen_rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    for f in findings:
        level = _SARIF_LEVELS[f.severity]
        if f.rule_id not in seen_rules:
            seen_rules[f.rule_id] = _sarif_descriptor(f.rule_id, level)
        text = f.message if not f.suggestion else f"{f.message} Fix: {f.suggestion}"
        text += _remap_note(f)
        result: dict[str, object] = {
            "ruleId": f.rule_id,
            "level": level,
            "message": {"text": text},
        }
        if f.file:
            region: dict[str, object] = {}
            if f.row is not None:
                region["startLine"] = f.row
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file},
                        **({"region": region} if region else {}),
                    }
                }
            ]
        properties: dict[str, object] = {}
        if f.severity_original is not None:
            # Disclosure for SARIF consumers: the finding's level above is the
            # remapped severity; properties.severityOriginal names the spec's
            # own severity so no SARIF consumer can miss the remap.
            properties["severityOriginal"] = f.severity_original.name
        if f.field:
            properties["field"] = f.field
        if f.data is not None:
            properties.update(f.data)
        if properties:
            result["properties"] = properties
        results.append(result)
    run: dict[str, object] = {
        "tool": {
            "driver": {
                "name": "tods-validate",
                "version": __version__,
                "informationUri": "https://github.com/ChelseaKR/tods-validate",
                "rules": list(seen_rules.values()),
            }
        },
        "results": results,
    }
    if coverage is not None:
        run["invocations"] = [
            {
                "executionSuccessful": True,
                "properties": {"coverage": coverage.to_dict()},
            }
        ]
    disclosure = _disclosure_lines(findings)
    if disclosure:
        run["properties"] = {"severityRemapDisclosure": disclosure}
    sarif = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [run],
    }
    return json.dumps(sarif, indent=2)


_HTML_SEVERITY_LABEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "info",
}


def _html_row(f: Finding, esc: Callable[[str], str]) -> str:
    return (
        "<tr"
        f" data-sev='{esc(f.severity.name)}' data-rule='{esc(f.rule_id)}'"
        f" data-file='{esc(f.file or '')}'>"
        f"<td class='sev sev-{_HTML_SEVERITY_LABEL[f.severity]}'>{f.severity.name}</td>"
        f"<td>{esc(f.rule_id)}</td>"
        f"<td>{esc(f.location() or '-')}</td>"
        f"<td>{esc(f.message)}{esc(_remap_note(f))}"
        + (f"<br><em>Fix: {esc(f.suggestion)}</em>" if f.suggestion else "")
        + "</td></tr>"
    )


def _timeline_time(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


def _timeline_event_label(event: _Event) -> str:
    values = event.row.values
    work = values.get("event_type", "")
    job = values.get("job_type", "")
    if job and work and job != work:
        return f"{job}: {work}"
    return work or job or event.trip_id or "Event"


def _timeline_svg(
    events: list[_Event],
    finding_rows: dict[int, list[Finding]],
    esc: Callable[[str], str],
) -> str:
    timed = [
        event
        for event in events
        if event.start is not None and event.end is not None and event.end >= event.start
    ]
    if not timed:
        return (
            "<p class='timeline-note'>No events with valid start and end times can be plotted. "
            "The event table still lists every row.</p>"
        )

    start = min(event.start for event in timed if event.start is not None)
    end = max(event.end for event in timed if event.end is not None)
    span = max(end - start, 1)
    width, label_width, right, top, row_height = 960, 124, 24, 42, 34
    plot_width = width - label_width - right
    height = top + len(timed) * row_height + 22

    ticks = []
    for index in range(5):
        ratio = index / 4
        x = label_width + ratio * plot_width
        seconds = round(start + ratio * span)
        ticks.append(
            f"<line class='timeline-grid' x1='{x:.1f}' y1='28' x2='{x:.1f}' "
            f"y2='{height - 14}'/>"
            f"<text class='timeline-tick' x='{x:.1f}' y='18' "
            f"text-anchor='middle'>{_timeline_time(seconds)}</text>"
        )

    bars = []
    for index, event in enumerate(timed):
        start_seconds, end_seconds = event.start, event.end
        if start_seconds is None or end_seconds is None:
            continue
        y = top + index * row_height
        x = label_width + (start_seconds - start) / span * plot_width
        bar_width = max((end_seconds - start_seconds) / span * plot_width, 4)
        event_findings = finding_rows.get(event.row.line, [])
        issue_class = " has-finding" if event_findings else ""
        sequence = str(event.sequence) if event.sequence is not None else "?"
        label = _timeline_event_label(event)
        visual_label = label if len(label) <= 12 else label[:11] + "…"
        bars.append(
            f"<text class='timeline-label' x='{label_width - 10}' y='{y + 16}' "
            f"text-anchor='end'>#{esc(sequence)} {esc(visual_label)}</text>"
            f"<rect class='event-bar{issue_class}' x='{x:.1f}' y='{y + 3}' "
            f"width='{bar_width:.1f}' height='18' rx='3'>"
            f"<title>{esc(label)}, {_timeline_time(start_seconds)} to "
            f"{_timeline_time(end_seconds)}</title></rect>"
            + (
                f"<text class='issue-marker' x='{min(x + bar_width + 9, width - 8):.1f}' "
                f"y='{y + 17}'>◆</text>"
                if event_findings
                else ""
            )
        )

    return (
        "<div class='timeline-scroll' tabindex='0' "
        "aria-label='Scrollable visual run timeline'>"
        f"<svg class='timeline-chart' aria-hidden='true' focusable='false' "
        f"viewBox='0 0 {width} {height}'>" + "".join(ticks) + "".join(bars) + "</svg></div>"
    )


def _timeline_table(
    events: list[_Event],
    finding_rows: dict[int, list[Finding]],
    esc: Callable[[str], str],
) -> str:
    rows = []
    ordered = sorted(
        events,
        key=lambda event: (
            event.sequence is None,
            event.sequence if event.sequence is not None else 0,
            event.row.line,
        ),
    )
    for event in ordered:
        values = event.row.values
        sequence = str(event.sequence) if event.sequence is not None else "-"
        start = values.get("start_time", "") or "-"
        end = values.get("end_time", "") or "-"
        movement = f"{event.start_location or '-'} → {event.end_location or '-'}"
        event_findings = finding_rows.get(event.row.line, [])
        finding_html = " ".join(
            f"<span class='finding-tag sev-{_HTML_SEVERITY_LABEL[f.severity]}'>"
            f"{f.severity.name} {esc(f.rule_id)}</span>"
            for f in event_findings
        )
        rows.append(
            "<tr>"
            f"<td>{esc(sequence)}</td>"
            f"<td><time>{esc(start)}</time>–<time>{esc(end)}</time></td>"
            f"<td>{esc(_timeline_event_label(event))}</td>"
            f"<td>{esc(movement)}</td>"
            f"<td>{finding_html or 'None'}</td>"
            "</tr>"
        )
    return (
        "<div class='table-scroll' role='region' tabindex='0' "
        "aria-label='Scrollable event table'>"
        "<table class='timeline-table'>"
        "<caption>Run events in sequence order. This table is the text equivalent "
        "of the visual timeline.</caption>"
        "<thead><tr><th scope='col'>Sequence</th><th scope='col'>Time</th>"
        "<th scope='col'>Work</th><th scope='col'>Movement</th>"
        "<th scope='col'>Findings on row</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _timelines_html(
    package: Package,
    findings: list[Finding],
    spec_version: str,
    esc: Callable[[str], str],
) -> str:
    intro = (
        "<section class='timelines' aria-labelledby='timelines-heading'>"
        "<h2 id='timelines-heading'>Run timelines</h2>"
        "<p>Each visual rail places run events on a time axis. A dashed bar and diamond "
        "mark an event row with findings. The table under each rail contains the same "
        "information in sequence order.</p>"
    )
    if spec_version != SPEC_VERSION:
        return (
            intro + f"<p>Timelines are not available for TODS v{esc(spec_version)} because that "
            "version models runs and events with a different file structure.</p></section>"
        )

    runs = events_by_run(parse_events(package))
    if not runs:
        return intro + "<p>No complete service_id/run_id pairs are available to plot.</p></section>"

    findings_by_row: dict[int, list[Finding]] = {}
    for finding in findings:
        if finding.file == "run_events.txt" and finding.row is not None:
            findings_by_row.setdefault(finding.row, []).append(finding)

    cards = []
    for (service_id, run_id), events in sorted(runs.items()):
        ordered = sorted(
            events,
            key=lambda event: (
                event.sequence is None,
                event.sequence if event.sequence is not None else 0,
                event.row.line,
            ),
        )
        finding_count = sum(len(findings_by_row.get(event.row.line, [])) for event in ordered)
        finding_label = f", {finding_count} finding{'s' if finding_count != 1 else ''}"
        cards.append(
            "<details class='run-timeline' open>"
            f"<summary>Service {esc(service_id)} · run {esc(run_id)} — "
            f"{len(ordered)} events{finding_label}</summary>"
            + _timeline_svg(ordered, findings_by_row, esc)
            + _timeline_table(ordered, findings_by_row, esc)
            + "</details>"
        )
    return intro + "".join(cards) + "</section>"


def render_html(
    findings: list[Finding],
    source: str,
    *,
    coverage: RunCoverage | None = None,
    spec_version: str = SPEC_VERSION,
    timeline_package: Package | None = None,
) -> str:
    """A self-contained, shareable HTML report. No external assets.

    Built to meet the same accessibility bar as the terminal output. Severity is
    carried by a word (ERROR/WARNING/INFO), never color alone; every per-rule
    findings table has a caption and column-scoped headers so a screen reader can
    navigate it; the page declares ``lang`` and a responsive viewport so it
    reflows on zoom; and the severity colors are chosen to clear WCAG AA contrast
    (4.5:1) in both light and dark color schemes (``prefers-color-scheme`` plus
    ``color-scheme: light dark`` on the root, so the report never renders light
    inside a dark host page). Landmarks (``header``/``main``) give assistive tech
    a document outline.

    At findings-report scale (thousands of rows), a single flat table stops
    being usable, so findings are grouped into one collapsible ``<details>``
    per rule ID (native, zero-JavaScript disclosure) ordered by
    ``by_rule(findings).most_common()`` — the same deterministic tie-break
    (first occurrence in the incoming file/row/rule-sorted list) used
    elsewhere in this module. Rows within a group keep that incoming order.
    An inline, dependency-free ``<script>`` adds severity/rule/file filtering
    that toggles row and group visibility client-side; every control is a
    plain ``<select>``/``<input>`` rendered in the DOM, and a "Showing N of M
    findings" counter is always present as real text (N == M with JS
    disabled), so the report is fully usable — all findings readable via
    ``<details>``/``<summary>`` — with JavaScript off.
    """
    counts = summarize(findings)
    esc = html.escape
    scope_lines = _coverage_lines(coverage)
    scope_html = ""
    if scope_lines:
        details = "".join(f"<li>{esc(line)}</li>" for line in scope_lines[1:])
        scope_html = f"<p class='scope'>{esc(scope_lines[0])}</p>" + (
            f"<ul class='scope-detail'>{details}</ul>" if details else ""
        )
    disclosure_lines = _disclosure_lines(findings)
    disclosure_html = (
        "<p class='disclosure'>" + "<br>".join(esc(line) for line in disclosure_lines) + "</p>"
        if disclosure_lines
        else ""
    )
    rule_counts = by_rule(findings).most_common()
    total = len(findings)
    timelines = (
        _timelines_html(timeline_package, findings, spec_version, esc)
        if timeline_package is not None
        else ""
    )

    breakdown = ", ".join(f"{esc(rule_id)} ×{count}" for rule_id, count in rule_counts)

    if not findings:
        body = "<p>No problems found.</p>" + scope_html
    else:
        groups = []
        for rule_id, count in rule_counts:
            rows = "".join(_html_row(f, esc) for f in findings if f.rule_id == rule_id)
            plural = "s" if count != 1 else ""
            groups.append(
                "<details class='rule-group' open>"
                f"<summary>{esc(rule_id)} - {count} finding{plural}</summary>"
                f"<div class='table-scroll' role='region' tabindex='0' "
                f"aria-label='Scrollable findings table for {esc(rule_id)}'>"
                "<table><caption>Findings, ordered by file, then row, then rule ID.</caption>"
                "<thead><tr><th scope='col'>Severity</th><th scope='col'>Rule</th>"
                "<th scope='col'>Location</th><th scope='col'>Message</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></div></details>"
            )
        rule_options = "".join(
            f"<option value='{esc(rule_id)}'>{esc(rule_id)} ({count})</option>"
            for rule_id, count in rule_counts
        )
        body = (
            "<p class='counts'>"
            f"<span class='sev-error'>{counts[Severity.ERROR]} error(s)</span>, "
            f"<span class='sev-warning'>{counts[Severity.WARNING]} warning(s)</span>, "
            f"<span class='sev-info'>{counts[Severity.INFO]} info</span></p>"
            f"<p class='breakdown'>By rule: {breakdown}</p>"
            + scope_html
            + disclosure_html
            + "<div class='filters'>"
            "<label>Severity<select id='sev-filter'>"
            "<option value=''>All severities</option>"
            "<option value='ERROR'>Error</option>"
            "<option value='WARNING'>Warning</option>"
            "<option value='INFO'>Info</option>"
            "</select></label>"
            "<label>Rule<select id='rule-filter'>"
            f"<option value=''>All rules</option>{rule_options}"
            "</select></label>"
            "<label>File<input type='text' id='file-filter' "
            "placeholder='Filter by file…'></label>"
            "</div>"
            f"<p id='shown-count' aria-live='polite'>Showing {total} of {total} findings</p>"
            + "".join(groups)
            + "<script>"
            "(function(){"
            "var rows=Array.prototype.slice.call(document.querySelectorAll('tr[data-sev]'));"
            "var groups=Array.prototype.slice.call("
            "document.querySelectorAll('details.rule-group'));"
            "var sevSel=document.getElementById('sev-filter');"
            "var ruleSel=document.getElementById('rule-filter');"
            "var fileInput=document.getElementById('file-filter');"
            "var countEl=document.getElementById('shown-count');"
            "var total=rows.length;"
            "function apply(){"
            "var sev=sevSel?sevSel.value:'';"
            "var rule=ruleSel?ruleSel.value:'';"
            "var file=fileInput?fileInput.value.trim().toLowerCase():'';"
            "var shown=0;"
            "groups.forEach(function(g){"
            "var anyVisible=false;"
            "var trs=Array.prototype.slice.call(g.querySelectorAll('tr[data-sev]'));"
            "trs.forEach(function(tr){"
            "var match=(!sev||tr.getAttribute('data-sev')===sev)"
            "&&(!rule||tr.getAttribute('data-rule')===rule)"
            "&&(!file||tr.getAttribute('data-file').toLowerCase().indexOf(file)!==-1);"
            "tr.style.display=match?'':'none';"
            "if(match){anyVisible=true;shown++;}"
            "});"
            "g.style.display=anyVisible?'':'none';"
            "});"
            "if(countEl){countEl.textContent='Showing '+shown+' of '+total+' findings';}"
            "}"
            "if(sevSel)sevSel.addEventListener('change',apply);"
            "if(ruleSel)ruleSel.addEventListener('change',apply);"
            "if(fileInput)fileInput.addEventListener('input',apply);"
            "})();"
            "</script>"
        )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>TODS validation report — {esc(source)}</title>"
        "<style>"
        ":root{color-scheme:light dark}"
        "body{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#1a1a1a;background:#fff}"
        "table{border-collapse:collapse;width:100%;margin-top:.5rem}"
        "caption{text-align:left;font-weight:600;padding:.4rem 0}"
        "th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;vertical-align:top}"
        "th{background:#f4f4f4}"
        ".sev{font-weight:600}.sev-error{color:#b00020}.sev-warning{color:#8a5a00}"
        ".sev-info{color:#0a7d3f}"
        ".counts span{font-weight:600}"
        "details.rule-group{border:1px solid #ddd;border-radius:6px;"
        "padding:.5rem .75rem;margin:.75rem 0}"
        "details.rule-group summary{cursor:pointer;font-weight:600}"
        ".filters{display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0}"
        ".filters label{display:flex;flex:1 1 10rem;min-width:0;flex-direction:column;"
        "gap:.25rem;font-size:.85rem}"
        ".filters select,.filters input{font:inherit;padding:.3rem .5rem;"
        "border:1px solid #bbb;border-radius:4px;box-sizing:border-box;max-width:100%;width:100%}"
        "#shown-count{font-weight:600}"
        ".timelines{margin-top:2.5rem;padding-top:1.25rem;border-top:3px solid #355c7d}"
        ".run-timeline{border:1px solid #c8d2dc;border-radius:6px;"
        "padding:.65rem .8rem;margin:1rem 0}"
        ".run-timeline summary{cursor:pointer;font-weight:700}"
        ".timeline-scroll,.table-scroll{max-width:100%;overflow-x:auto;margin-top:.75rem}"
        ".timeline-scroll:focus-visible,.table-scroll:focus-visible{"
        "outline:3px solid #355c7d;outline-offset:2px}"
        ".timeline-chart{display:block;width:100%;min-width:46rem;background:#f8fafc;"
        "border:1px solid #c8d2dc;border-radius:4px}"
        ".timeline-grid{stroke:#64748b;stroke-width:1}"
        ".timeline-tick,.timeline-label{fill:#1f2933;font-family:ui-monospace,monospace;"
        "font-size:11px}"
        ".event-bar{fill:#355c7d}"
        ".event-bar.has-finding{fill:#9a3412;stroke:#7c2d12;stroke-width:2;"
        "stroke-dasharray:5 3}"
        ".issue-marker{fill:#9a3412;font-size:13px}"
        ".timeline-table{min-width:44rem}"
        ".finding-tag{display:inline-block;border:1px solid currentColor;border-radius:3px;"
        "padding:.05rem .3rem;margin:.08rem;font-size:.78rem;font-weight:700}"
        ".timeline-note{font-style:italic}"
        "@media (prefers-color-scheme: dark){"
        "body{background:#121212;color:#e8e8e8}"
        "th,td{border-color:#444}"
        "th{background:#242424}"
        "details.rule-group{border-color:#444}"
        ".filters select,.filters input{border-color:#555;background:#1e1e1e;color:#e8e8e8}"
        ".sev-error{color:#ff6b6b}.sev-warning{color:#e0a530}.sev-info{color:#3ddc84}"
        ".timelines{border-top-color:#83b6dd}"
        ".run-timeline,.timeline-chart{border-color:#52606d}"
        ".timeline-chart{background:#18212b}"
        ".timeline-grid{stroke:#9fb3c8}"
        ".timeline-tick,.timeline-label{fill:#e8e8e8}"
        ".event-bar{fill:#83b6dd}"
        ".event-bar.has-finding{fill:#b4532a;stroke:#ffb07c}"
        ".issue-marker{fill:#ffb07c}"
        ".timeline-scroll:focus-visible,.table-scroll:focus-visible{outline-color:#83b6dd}"
        "}"
        "@media (max-width:600px){body{margin:1rem}.filters{gap:.65rem}}"
        "</style></head><body>"
        "<header>"
        "<h1>TODS validation report</h1>"
        f"<p>Source: <code>{esc(source)}</code> · TODS v{spec_version} · "
        f"tods-validate {__version__}</p>"
        "</header>"
        f"<main>{body}{timelines}</main>"
        "</body></html>"
    )


RENDERERS = {
    "text": render_text,
    "json": render_json,
    "markdown": render_markdown,
    "github": render_github,
    "sarif": render_sarif,
    "html": render_html,
}
