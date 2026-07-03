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
from datetime import UTC, datetime
from typing import cast

from . import __version__
from .findings import Finding, Severity
from .rules import all_rules
from .schema import SPEC_VERSION

# Bumped when the JSON report shape changes. Fields are only ever added, never
# removed or renamed, within a major version; this lets consumers branch on
# shape if they need to.
REPORT_SCHEMA_VERSION = "1.1.0"

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

# Rule ID -> Rule, used to surface each rule's worked example alongside its
# root-cause hint when a rule clusters.
_REGISTRY_BY_ID = {r.id: r for r in all_rules()}


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


def render_text(
    findings: list[Finding],
    source: str,
    *,
    max_findings: int | None = None,
    quiet: bool = False,
) -> str:
    lines: list[str] = [f"tods-validate: {source} (TODS v{SPEC_VERSION})", ""]
    if not findings:
        lines.append("No problems found.")
        return "\n".join(lines)

    counts = summarize(findings)
    if not quiet:
        shown, hidden = _max_findings(findings, max_findings)
        for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            group = [f for f in shown if f.severity == severity]
            if not group:
                continue
            plural = "s" if len(group) != 1 else ""
            lines.append(
                f"{len([f for f in findings if f.severity == severity])} "
                f"{severity.name.lower()}{plural}:"
            )
            for f in group:
                location = f.location()
                prefix = f"  {severity.name} {f.rule_id}"
                lines.append(f"{prefix} [{location}]" if location else prefix)
                lines.append(f"    {f.message}")
                if f.suggestion:
                    lines.append(f"    Fix: {f.suggestion}")
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
    return "\n".join(lines)


def render_json(findings: list[Finding], source: str) -> str:
    counts = summarize(findings)
    payload = {
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
    return json.dumps(payload, indent=2)


def _stamp_footer() -> str:
    """A provenance footer (tool version, spec version, UTC timestamp).

    Shared by ``render_markdown`` and ``render_batch_markdown`` so a report is
    a citable compliance artifact: anyone reading it later knows exactly which
    tool version and spec it was validated against and when.
    """
    return (
        "---\n"
        f"_Generated by tods-validate {__version__} against TODS v{SPEC_VERSION} at "
        f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}._"
    )


def render_markdown(findings: list[Finding], source: str, *, stamp: bool = False) -> str:
    """A report suitable for pasting into an issue or working-group thread.

    With ``stamp=True`` the report carries a provenance footer (tool version,
    spec version, UTC timestamp) for use as a citable compliance artifact. The
    stamp is opt-in because the timestamp makes output non-reproducible.
    """
    counts = summarize(findings)
    lines = [
        "# TODS validation report",
        "",
        f"Source: `{source}`, validated against TODS v{SPEC_VERSION} by tods-validate.",
        "",
    ]
    if not findings:
        lines.append("No problems found.")
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


def render_sarif(findings: list[Finding], source: str) -> str:
    """SARIF 2.1.0, for GitHub code-scanning and security dashboards.

    Each distinct rule that fired becomes a reporting descriptor under the
    tool's ``rules`` array; each finding becomes a ``result`` pointing at the
    file and 1-based line.
    """
    seen_rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    for f in findings:
        seen_rules.setdefault(
            f.rule_id,
            {
                "id": f.rule_id,
                "name": f.rule_id,
                "defaultConfiguration": {"level": _SARIF_LEVELS[f.severity]},
            },
        )
        text = f.message if not f.suggestion else f"{f.message} Fix: {f.suggestion}"
        result: dict[str, object] = {
            "ruleId": f.rule_id,
            "level": _SARIF_LEVELS[f.severity],
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
        results.append(result)
    sarif = {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "runs": [
            {
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
        ],
    }
    return json.dumps(sarif, indent=2)


_HTML_SEVERITY_LABEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "info",
}


def render_html(findings: list[Finding], source: str) -> str:
    """A self-contained, shareable HTML report. No external assets.

    Built to meet the same accessibility bar as the terminal output. Severity is
    carried by a word (ERROR/WARNING/INFO), never color alone; the findings table
    has a caption and column-scoped headers so a screen reader can navigate it;
    the page declares ``lang`` and a responsive viewport so it reflows on zoom;
    and the severity colors are chosen to clear WCAG AA contrast (4.5:1) on the
    white background. Landmarks (``header``/``main``) give assistive tech a
    document outline.
    """
    counts = summarize(findings)
    esc = html.escape
    rows = []
    for f in findings:
        rows.append(
            "<tr>"
            f"<td class='sev sev-{_HTML_SEVERITY_LABEL[f.severity]}'>{f.severity.name}</td>"
            f"<td>{esc(f.rule_id)}</td>"
            f"<td>{esc(f.location() or '-')}</td>"
            f"<td>{esc(f.message)}"
            + (f"<br><em>Fix: {esc(f.suggestion)}</em>" if f.suggestion else "")
            + "</td></tr>"
        )
    breakdown = ", ".join(
        f"{esc(rule_id)} ×{count}" for rule_id, count in by_rule(findings).most_common()
    )
    body = (
        "<p>No problems found.</p>"
        if not findings
        else (
            "<p class='counts'>"
            f"<span class='sev-error'>{counts[Severity.ERROR]} error(s)</span>, "
            f"<span class='sev-warning'>{counts[Severity.WARNING]} warning(s)</span>, "
            f"<span class='sev-info'>{counts[Severity.INFO]} info</span></p>"
            f"<p class='breakdown'>By rule: {breakdown}</p>"
            "<table><caption>Findings, ordered by file, then row, then rule ID.</caption>"
            "<thead><tr><th scope='col'>Severity</th><th scope='col'>Rule</th>"
            "<th scope='col'>Location</th><th scope='col'>Message</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>TODS validation report — {esc(source)}</title>"
        "<style>"
        "body{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#1a1a1a}"
        "table{border-collapse:collapse;width:100%;margin-top:1rem}"
        "caption{text-align:left;font-weight:600;padding:.4rem 0}"
        "th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left;vertical-align:top}"
        "th{background:#f4f4f4}"
        ".sev{font-weight:600}.sev-error{color:#b00020}.sev-warning{color:#8a5a00}"
        ".sev-info{color:#0a7d3f}"
        ".counts span{font-weight:600}"
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
