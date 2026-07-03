"""Workspace mode: a local, append-only run-history ledger.

``batch --history DIR`` and the ``[workspace]`` config table give ``batch``
and ``diff`` a memory across runs: a trend line per agency/feed answering
"which agency regressed" without a hosted service. Everything here is a plain
file in the repo the caller controls — an artifact, not a database.

Privacy constraint (load-bearing, do not relax): a history record stores only
**counts and rule IDs**, reusing the JSON report's summary block shape
(``errors``/``warnings``/``infos``/``byRule`` from :func:`report.summarize`
and :func:`report.by_rule`). It never stores :attr:`Finding.message` or
:attr:`Finding.suggestion` text, because those are free-form and can name a
stop, a run, or an employee/vehicle identifier — exactly the kind of detail
that turns a build artifact into a compliance/privacy liability once it
starts accumulating in CI history. If you extend :class:`HistoryRecord`,
keep this true: counts and rule IDs only, never finding text.

History record shape (JSON, one object per line in ``history.jsonl``)::

    {
      "schemaVersion": "1.0.0",
      "timestamp": "2026-07-02T18:04:11Z",
      "source": "feeds/agency-a",
      "toolVersion": "0.5.0",
      "specVersion": "2.1.0",
      "errors": 2,
      "warnings": 5,
      "infos": 1,
      "byRule": {"TODS-E307": 2, "TODS-W206": 5}
    }

``schemaVersion`` follows semver: fields are only ever added within a major
version, so old records stay loadable. :data:`HISTORY_SCHEMA_VERSION` is
bumped on a breaking shape change; :func:`load_history` skips records it
does not recognize rather than failing a whole ledger over one old or
foreign line.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .findings import Finding, Severity
from .report import by_rule, summarize

# Bumped on a breaking change to the record shape. Within a major version,
# fields are only ever added, never removed or renamed.
HISTORY_SCHEMA_VERSION = "1.0.0"

# Default location for the ledger, relative to the current working directory.
# A dot-prefixed directory keeps it out of the way of the feed files being
# validated while staying a plain, inspectable part of the repo/CI workspace.
DEFAULT_HISTORY_DIR = Path(".tods-history")

HISTORY_FILENAME = "history.jsonl"


class HistoryError(Exception):
    """A history file exists but a line could not be parsed at all."""


@dataclass(frozen=True)
class HistoryRecord:
    """One run's summary. Counts and rule IDs only — see module docstring."""

    schema_version: str
    timestamp: str
    source: str
    tool_version: str
    spec_version: str
    errors: int
    warnings: int
    infos: int
    by_rule: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "timestamp": self.timestamp,
            "source": self.source,
            "toolVersion": self.tool_version,
            "specVersion": self.spec_version,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
            "byRule": self.by_rule,
        }


def build_record(
    findings: list[Finding],
    source: str,
    *,
    tool_version: str,
    spec_version: str,
    timestamp: str | None = None,
) -> HistoryRecord:
    """Summarize ``findings`` into a :class:`HistoryRecord`.

    Reuses :func:`report.summarize` and :func:`report.by_rule` rather than
    re-deriving counts, so the ledger and the JSON report can never disagree
    about what a run found. Only counts and rule IDs cross into the record;
    ``findings`` themselves (and their message text) are never touched again.
    """
    counts = summarize(findings)
    return HistoryRecord(
        schema_version=HISTORY_SCHEMA_VERSION,
        timestamp=timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source=source,
        tool_version=tool_version,
        spec_version=spec_version,
        errors=counts[Severity.ERROR],
        warnings=counts[Severity.WARNING],
        infos=counts[Severity.INFO],
        by_rule=dict(by_rule(findings).most_common()),
    )


def append_record(history_dir: Path, record: HistoryRecord) -> None:
    """Append one JSON object line to ``history_dir/history.jsonl``.

    Creates ``history_dir`` if it does not exist yet. Append-only by design:
    a run's history is never rewritten in place, so the ledger is safe to
    accumulate across CI jobs without a lock.
    """
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / HISTORY_FILENAME
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), sort_keys=True))
        fh.write("\n")


def load_history(history_dir: Path) -> list[HistoryRecord]:
    """Read and parse ``history_dir/history.jsonl``.

    Missing file or directory is not an error: an empty ledger is a normal
    starting state, so this returns ``[]``. A line that is not valid JSON at
    all raises :class:`HistoryError` (the file is corrupt); a line that
    parses but carries a ``schemaVersion`` this build does not recognize is
    skipped rather than failing the whole load, so an old or newer record
    written by a different tool version does not block reading the rest of
    the ledger.
    """
    path = history_dir / HISTORY_FILENAME
    if not path.is_file():
        return []

    records: list[HistoryRecord] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HistoryError(f"{path}:{lineno}: not valid JSON: {exc}") from exc
        if not isinstance(data, dict) or data.get("schemaVersion") != HISTORY_SCHEMA_VERSION:
            continue  # unknown/foreign schema version: skip, don't fail the ledger
        try:
            records.append(
                HistoryRecord(
                    schema_version=str(data["schemaVersion"]),
                    timestamp=str(data["timestamp"]),
                    source=str(data["source"]),
                    tool_version=str(data["toolVersion"]),
                    spec_version=str(data["specVersion"]),
                    errors=int(data["errors"]),
                    warnings=int(data["warnings"]),
                    infos=int(data["infos"]),
                    by_rule={str(k): int(v) for k, v in dict(data["byRule"]).items()},
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HistoryError(f"{path}:{lineno}: malformed history record: {exc}") from exc
    return records


def render_trend(records: list[HistoryRecord]) -> str:
    """A text-first, accessible Markdown trend table: one row per run.

    Deliberately no sparklines — severity and change are carried by words and
    numbers so the table reads the same in a terminal, a pasted issue, or a
    screen reader. Grouped by source (one table per feed/agency) so "which
    agency regressed" is answerable at a glance; within a source, runs are
    ordered oldest first and each row's "Δ errors" and "New/worse rules"
    columns compare against that source's previous run.
    """
    if not records:
        return "No run history yet."

    by_source: dict[str, list[HistoryRecord]] = {}
    for record in records:
        by_source.setdefault(record.source, []).append(record)

    lines: list[str] = ["# Run history trend", ""]
    for source in sorted(by_source):
        runs = sorted(by_source[source], key=lambda r: r.timestamp)
        lines.append(f"## {source}")
        lines.append("")
        lines.append("| Timestamp (UTC) | Errors | Warnings | Infos | Δ errors | New/worse rules |")
        lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
        previous: HistoryRecord | None = None
        for run in runs:
            if previous is None:
                delta = "-"
                regressed = "-"
            else:
                diff = run.errors - previous.errors
                delta = f"{diff:+d}" if diff != 0 else "0"
                worse = [
                    rule_id
                    for rule_id, count in sorted(run.by_rule.items())
                    if count > previous.by_rule.get(rule_id, 0)
                ]
                regressed = ", ".join(worse) if worse else "-"
            lines.append(
                f"| {run.timestamp} | {run.errors} | {run.warnings} | {run.infos} | "
                f"{delta} | {regressed} |"
            )
            previous = run
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
