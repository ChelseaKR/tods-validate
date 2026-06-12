"""Render findings as human text, JSON, or GitHub Actions annotations.

Accessibility note: severity is always carried by a word (ERROR, WARNING,
INFO), never by color alone, so reports stay readable when piped to a file.
"""

from __future__ import annotations

import json
from collections import Counter

from .findings import Finding, Severity
from .schema import SPEC_VERSION


def summarize(findings: list[Finding]) -> Counter[Severity]:
    return Counter(f.severity for f in findings)


def render_text(findings: list[Finding], source: str) -> str:
    lines: list[str] = [f"tods-validate: {source} (TODS v{SPEC_VERSION})", ""]
    if not findings:
        lines.append("No problems found.")
        return "\n".join(lines)

    for severity in (Severity.ERROR, Severity.WARNING, Severity.INFO):
        group = [f for f in findings if f.severity == severity]
        if not group:
            continue
        plural = "s" if len(group) != 1 else ""
        lines.append(f"{len(group)} {severity.name.lower()}{plural}:")
        for f in group:
            location = f.location()
            prefix = f"  {severity.name} {f.rule_id}"
            lines.append(f"{prefix} [{location}]" if location else prefix)
            lines.append(f"    {f.message}")
            if f.suggestion:
                lines.append(f"    Fix: {f.suggestion}")
        lines.append("")

    counts = summarize(findings)
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
        "specVersion": SPEC_VERSION,
        "source": source,
        "summary": {
            "errors": counts[Severity.ERROR],
            "warnings": counts[Severity.WARNING],
            "infos": counts[Severity.INFO],
        },
        "findings": [f.to_dict() for f in findings],
    }
    return json.dumps(payload, indent=2)


def render_markdown(findings: list[Finding], source: str) -> str:
    """A report suitable for pasting into an issue or working-group thread."""
    counts = summarize(findings)
    lines = [
        "# TODS validation report",
        "",
        f"Source: `{source}`, validated against TODS v{SPEC_VERSION} by tods-validate.",
        "",
    ]
    if not findings:
        lines.append("No problems found.")
        return "\n".join(lines)

    lines.append(
        f"**{counts[Severity.ERROR]} error(s), {counts[Severity.WARNING]} warning(s), "
        f"{counts[Severity.INFO]} info.**"
    )
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


RENDERERS = {
    "text": render_text,
    "json": render_json,
    "markdown": render_markdown,
    "github": render_github,
}
