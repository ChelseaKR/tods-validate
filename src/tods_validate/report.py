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
from .rules import REGISTRY, RunCoverage
from .schema import SPEC_VERSION
from .suggest import Suggestion

# Bumped when the JSON report shape changes. Fields are only ever added, never
# removed or renamed, within a major version; this lets consumers branch on
# shape if they need to.
#
# 1.3.0 keeps the additive ``coverage`` manifest and per-finding ``data``,
# and adds ``fingerprint`` (content-anchored identity for --baseline) plus the
# top-level ``suggestions`` array (machine-form ``--suggest`` output).
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


def render_text(  # noqa: C901 - causality grouping adds display branches
    findings: list[Finding],
    source: str,
    *,
    max_findings: int | None = None,
    quiet: bool = False,
    coverage: RunCoverage | None = None,
) -> str:
    lines: list[str] = [f"tods-validate: {source} (TODS v{SPEC_VERSION})", ""]
    if not findings:
        lines.append("No problems found.")
        if coverage is not None and (scope := coverage.summary_line()) is not None:
            lines.append(f"Rule-set coverage: {scope}")
        return "\n".join(lines)

    counts = summarize(findings)
    if not quiet:
        shown, hidden = _max_findings(findings, max_findings)
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            group = [f for f in shown if f.severity == severity]
            if not group:
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
            follow_on_counts = Counter(f.caused_by for f in group if f.caused_by is not None)
            for f in group:
                if f.caused_by is not None:
                    continue  # rendered as its root's follow-on line, below
                location = f.location()
                prefix = f"  {severity.name} {f.rule_id}"
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
    lines.append(
        "Summary: "
        f"{counts[Severity.ERROR]} error(s), "
        f"{counts[Severity.WARNING]} warning(s), "
        f"{counts[Severity.INFO]} info."
    )
    if coverage is not None and (scope := coverage.summary_line()) is not None:
        lines.append(scope)
    return "\n".join(lines)


def render_json(
    findings: list[Finding],
    source: str,
    *,
    coverage: RunCoverage | None = None,
    suggestions: list[Suggestion] | None = None,
) -> str:
    counts = summarize(findings)
    payload: dict[str, object] = {
        "validator": "tods-validate",
        "toolVersion": __version__,
        "reportVersion": REPORT_SCHEMA_VERSION,
        "specVersion": SPEC_VERSION,
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


def _stamp_footer() -> str:
    """A provenance footer (tool version, spec version, UTC timestamp)."""
    return (
        "---\n"
        f"_Generated by tods-validate {__version__} against TODS v{SPEC_VERSION} at "
        f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}._"
    )


def render_markdown(  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    findings: list[Finding],
    source: str,
    *,
    stamp: bool = False,
    coverage: RunCoverage | None = None,
) -> str:
    """A report suitable for pasting into an issue or working-group thread.

    With ``stamp=True`` the report carries a provenance footer (tool version,
    spec version, UTC timestamp) for use as a citable compliance artifact. The
    stamp is opt-in because the timestamp makes output non-reproducible.
    """
    counts = summarize(findings)
    scope = coverage.summary_line() if stamp and coverage is not None else None
    lines = [
        "# TODS validation report",
        "",
        f"Source: `{source}`, validated against TODS v{SPEC_VERSION} by tods-validate.",
        "",
    ]
    if not findings:
        lines.append("No problems found.")
        if scope is not None:
            lines.append("")
            lines.append(f"Rule-set coverage: {scope}")
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
        if scope is not None:
            lines.append("")
            lines.append(scope)
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
                lines.append(f"- **{f.rule_id}**{where}: {f.message}")
                if f.suggestion:
                    lines.append(f"  - Fix: {f.suggestion}")
                if f.caused_by:
                    # Every finding is kept in Markdown (unlike the terminal
                    # renderer, which collapses this line into its root's
                    # follow-on count); the link just says why it's downstream.
                    lines.append(f"  - Caused by: {f.caused_by}")
    if stamp:
        lines.append("")
        lines.append(_stamp_footer())
    return "\n".join(lines)


def render_batch_markdown(rows: list[dict[str, object]], *, stamp: bool = False) -> str:
    """A single stamped multi-agency (fleet) compliance report.

    ``rows`` mirrors the structure ``cli.batch`` already builds: one dict per
    feed with either ``{"source", "errors", "warnings", "infos", "status"}``
    for a feed that was read successfully, or ``{"source", "error"}`` for one
    that raised ``PackageNotFoundError`` — those render with an "error"
    status distinct from "pass"/"fail".

    With ``stamp=True`` the report carries the same provenance footer as
    ``render_markdown``, making it a citable artifact for a whole fleet/
    portfolio of agencies in one document instead of a per-feed report.
    """
    lines = [
        "# TODS fleet compliance report",
        "",
        f"{len(rows)} feed(s) validated against TODS v{SPEC_VERSION} by tods-validate.",
        "",
        "| source | errors | warnings | infos | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    total_errors = total_warnings = total_infos = 0
    passed = failed = errored = 0
    for row in rows:
        if "error" in row:
            errored += 1
            lines.append(f"| `{row['source']}` | - | - | - | error |")
            continue
        status = row.get("status", "pass")
        if status == "fail":
            failed += 1
        else:
            passed += 1
        total_errors += cast(int, row["errors"])
        total_warnings += cast(int, row["warnings"])
        total_infos += cast(int, row["infos"])
        lines.append(
            f"| `{row['source']}` | {row['errors']} | {row['warnings']} | "
            f"{row['infos']} | {status} |"
        )
    lines.append("")
    lines.append(
        f"**Fleet totals: {total_errors} error(s), {total_warnings} warning(s), "
        f"{total_infos} info across {len(rows)} feed(s) "
        f"({passed} pass, {failed} fail, {errored} error).**"
    )
    if stamp:
        lines.append("")
        lines.append(_stamp_footer())
    return "\n".join(lines)


_GITHUB_COMMANDS = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "notice",
}


def _escape_annotation(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render_github(findings: list[Finding], source: str) -> str:
    """Workflow command format; one annotation per finding.

    See https://docs.github.com/actions/reference/workflow-commands-for-github-actions
    """
    lines = []
    for f in findings:
        command = _GITHUB_COMMANDS[f.severity]
        properties = []
        if f.file:
            properties.append(f"file={_escape_annotation(f.file)}")
        if f.row is not None:
            properties.append(f"line={f.row}")
        properties.append(f"title={f.rule_id}")
        message = f.message if not f.suggestion else f"{f.message} Fix: {f.suggestion}"
        lines.append(f"::{command} {','.join(properties)}::{_escape_annotation(message)}")
    counts = summarize(findings)
    lines.append(
        f"tods-validate: {counts[Severity.ERROR]} error(s), "
        f"{counts[Severity.WARNING]} warning(s), {counts[Severity.INFO]} info "
        f"in {source}."
    )
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


def render_sarif(
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
        f"<td>{esc(f.message)}"
        + (f"<br><em>Fix: {esc(f.suggestion)}</em>" if f.suggestion else "")
        + "</td></tr>"
    )


def render_html(
    findings: list[Finding], source: str, *, coverage: RunCoverage | None = None
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
    scope = coverage.summary_line() if coverage is not None else None
    scope_html = f"<p class='scope'>{esc(scope)}</p>" if scope is not None else ""
    rule_counts = by_rule(findings).most_common()
    total = len(findings)

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
                "<table><caption>Findings, ordered by file, then row, then rule ID.</caption>"
                "<thead><tr><th scope='col'>Severity</th><th scope='col'>Rule</th>"
                "<th scope='col'>Location</th><th scope='col'>Message</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></details>"
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
            f"<p class='breakdown'>By rule: {breakdown}</p>" + scope_html + "<div class='filters'>"
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
        ".filters label{display:flex;flex-direction:column;gap:.25rem;font-size:.85rem}"
        ".filters select,.filters input{font:inherit;padding:.3rem .5rem;"
        "border:1px solid #bbb;border-radius:4px}"
        "#shown-count{font-weight:600}"
        "@media (prefers-color-scheme: dark){"
        "body{background:#121212;color:#e8e8e8}"
        "th,td{border-color:#444}"
        "th{background:#242424}"
        "details.rule-group{border-color:#444}"
        ".filters select,.filters input{border-color:#555;background:#1e1e1e;color:#e8e8e8}"
        ".sev-error{color:#ff6b6b}.sev-warning{color:#e0a530}.sev-info{color:#3ddc84}"
        "}"
        "</style></head><body>"
        "<header>"
        "<h1>TODS validation report</h1>"
        f"<p>Source: <code>{esc(source)}</code> · TODS v{SPEC_VERSION} · "
        f"tods-validate {__version__}</p>"
        "</header>"
        f"<main>{body}</main>"
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
