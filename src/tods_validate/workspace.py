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

A record also carries the run's **coverage**: which rules ran, and which did
not and why. Rule IDs are already what this record is permitted to store, so
this does not touch the constraint above — and without it the ledger cannot
answer the only question it is read for. A rule that did not run contributes
nothing to ``byRule``, which is indistinguishable from a rule that ran and
found nothing, so a check being switched off used to read as a fix: errors
1 -> 0, "Δ errors -1", no new/worse rules, in a run where the rule that found
the error never executed and the bad data was still bad (#186).

History record shape (JSON, one object per line in ``history.jsonl``)::

    {
      "schemaVersion": "1.1.0",
      "timestamp": "2026-07-02T18:04:11Z",
      "source": "feeds/agency-a",
      "toolVersion": "0.5.0",
      "specVersion": "2.1.0",
      "errors": 2,
      "warnings": 5,
      "infos": 1,
      "byRule": {"TODS-E307": 2, "TODS-W206": 5},
      "coverage": {
        "ran": ["TODS-E101", "TODS-E307", "..."],
        "skippedByReason": {"skipped:needs_gtfs": ["TODS-E308", "..."]}
      }
    }

``schemaVersion`` follows semver: fields are only ever added within a major
version, so old records stay loadable. :func:`load_history` therefore accepts
any record sharing :data:`HISTORY_SCHEMA_VERSION`'s **major** version and
skips the rest, rather than failing a whole ledger over one old or foreign
line. It used to compare the full version string for equality, which would
have silently dropped every existing record the first time a field was added
-- the additive promise above, unimplemented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .findings import Finding, Severity
from .report import by_rule, summarize
from .rules import RunCoverage

# Bumped on a breaking change to the record shape. Within a major version,
# fields are only ever added, never removed or renamed, and `load_history`
# reads any record sharing this major version.
HISTORY_SCHEMA_VERSION = "1.1.0"

# Default location for the ledger, relative to the current working directory.
# A dot-prefixed directory keeps it out of the way of the feed files being
# validated while staying a plain, inspectable part of the repo/CI workspace.
DEFAULT_HISTORY_DIR = Path(".tods-history")

HISTORY_FILENAME = "history.jsonl"


class HistoryError(Exception):
    """A history file exists but a line could not be parsed at all."""


def _same_major(version: object) -> bool:
    """Is ``version`` a schema version this build can read?

    Within a major version fields are only ever added, so every field this
    build requires is present in any record sharing the major.
    """
    if not isinstance(version, str):
        return False
    return version.split(".", 1)[0] == HISTORY_SCHEMA_VERSION.split(".", 1)[0]


@dataclass(frozen=True)
class CoverageRecord:
    """One run's rule-set scope, as rule IDs.

    The durable half of :class:`rules.RunCoverage`. ``ran`` is stored rather
    than derived from a count, so "did rule X run in this run?" is a direct
    membership test with no inference: a stored total that disagrees with the
    list it summarizes is exactly the class of defect this record exists to
    close.
    """

    ran: tuple[str, ...]
    skipped_by_reason: dict[str, tuple[str, ...]]

    @property
    def skipped(self) -> tuple[str, ...]:
        return tuple(rid for ids in self.skipped_by_reason.values() for rid in ids)

    @property
    def total(self) -> int:
        return len(self.ran) + len(self.skipped)

    def ran_rule(self, rule_id: str) -> bool:
        return rule_id in self.ran

    def to_dict(self) -> dict[str, object]:
        return {
            "ran": list(self.ran),
            "skippedByReason": {
                status: list(ids) for status, ids in self.skipped_by_reason.items()
            },
        }

    @classmethod
    def from_run_coverage(cls, coverage: RunCoverage) -> CoverageRecord:
        return cls(
            ran=tuple(o.id for o in coverage.ran),
            skipped_by_reason={
                status: tuple(o.id for o in members)
                for status, members in coverage.skipped_by_reason().items()
            },
        )

    @classmethod
    def from_dict(cls, data: object) -> CoverageRecord | None:
        """Parse the ``coverage`` block, or None when a record predates it."""
        if not isinstance(data, dict):
            return None
        raw_skipped = data.get("skippedByReason", {})
        if not isinstance(raw_skipped, dict):
            raise ValueError("'coverage.skippedByReason' is not an object")
        ran = data.get("ran", [])
        if not isinstance(ran, list):
            raise ValueError("'coverage.ran' is not an array")
        return cls(
            ran=tuple(str(rid) for rid in ran),
            skipped_by_reason={
                str(status): tuple(str(rid) for rid in list(ids))
                for status, ids in raw_skipped.items()
            },
        )


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
    # None only for a record written before the coverage field existed. It
    # means "this ledger does not record what ran", which is a different fact
    # from "everything ran", and `render_trend` keeps them apart.
    coverage: CoverageRecord | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
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
        if self.coverage is not None:
            payload["coverage"] = self.coverage.to_dict()
        return payload


def build_record(
    findings: list[Finding],
    source: str,
    *,
    tool_version: str,
    spec_version: str,
    coverage: RunCoverage | None = None,
    timestamp: str | None = None,
) -> HistoryRecord:
    """Summarize ``findings`` into a :class:`HistoryRecord`.

    Reuses :func:`report.summarize` and :func:`report.by_rule` rather than
    re-deriving counts, so the ledger and the JSON report can never disagree
    about what a run found. Only counts and rule IDs cross into the record;
    ``findings`` themselves (and their message text) are never touched again.

    ``coverage`` is the run's :class:`rules.RunCoverage`. Callers that have one
    should always pass it: without it the record cannot say whether a rule that
    stopped reporting findings was fixed or simply stopped running.
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
        coverage=CoverageRecord.from_run_coverage(coverage) if coverage is not None else None,
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
    parses but carries a ``schemaVersion`` from a different **major** version
    is skipped rather than failing the whole load, so an old or newer record
    written by a different tool version does not block reading the rest of
    the ledger.

    Records from an earlier minor version of this major load normally, with
    the fields they predate left unset -- that is what the additive promise in
    the module docstring means. A record written before ``coverage`` existed
    therefore arrives with ``coverage=None``, which
    :func:`render_trend` reports as unknown rather than as a complete run.
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
        if not isinstance(data, dict) or not _same_major(data.get("schemaVersion")):
            continue  # foreign major version: skip, don't fail the ledger
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
                    coverage=CoverageRecord.from_dict(data.get("coverage")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HistoryError(f"{path}:{lineno}: malformed history record: {exc}") from exc
    return records


UNKNOWN = "?"


def _scope_cell(run: HistoryRecord) -> str:
    """``ran/total`` for this run, or ``?`` for a record that predates coverage."""
    if run.coverage is None:
        return UNKNOWN
    return f"{len(run.coverage.ran)}/{run.coverage.total}"


def _stopped_reporting(previous: HistoryRecord, run: HistoryRecord) -> tuple[str, ...] | None:
    """Rules that reported findings in ``previous`` and did not run in ``run``.

    ``None`` means the question cannot be answered because ``run`` predates the
    coverage field. Only ``run``'s coverage is needed: ``previous.byRule``
    already names the rules that found something, and what has to be checked is
    whether each of them ran this time.

    These are the rules that make a drop in the error count unsupportable. A
    rule that ran clean before and is skipped now contributed nothing to the
    old count, so it cannot manufacture an improvement and is not listed here.
    """
    if run.coverage is None:
        return None
    return tuple(
        rule_id
        for rule_id in sorted(previous.by_rule)
        if previous.by_rule[rule_id] > 0 and not run.coverage.ran_rule(rule_id)
    )


def _delta_cell(
    previous: HistoryRecord, run: HistoryRecord, stopped: tuple[str, ...] | None
) -> str:
    """The "Δ errors" cell, which never claims a reduction it cannot support.

    A rise is always reported: more errors is more errors, whatever the scope
    did. A fall or a flat line is only reported when every rule that found
    something last time actually ran this time. Otherwise the count went down
    because a check went away, and the honest cell is ``?`` -- the whole defect
    in #186 was rendering that case as ``-1``.
    """
    diff = run.errors - previous.errors
    if diff > 0:
        return f"{diff:+d}"
    if stopped is None or stopped:
        return UNKNOWN
    return f"{diff:+d}" if diff != 0 else "0"


def render_trend(records: list[HistoryRecord]) -> str:
    """A text-first, accessible Markdown trend table: one row per run.

    Deliberately no sparklines — severity and change are carried by words and
    numbers so the table reads the same in a terminal, a pasted issue, or a
    screen reader. Grouped by source (one table per feed/agency) so "which
    agency regressed" is answerable at a glance; within a source, runs are
    ordered oldest first and each row compares against that source's previous
    run.

    "Checks ran" states each run's own scope, and "Stopped running" names the
    rules that found something last time and did not execute this time. When
    that column is non-empty the "Δ errors" cell reads ``?`` rather than a
    reduction, because the count fell for a reason the ledger cannot attribute
    to a fix.
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
        lines.append(
            "| Timestamp (UTC) | Errors | Warnings | Infos | Checks ran | "
            "Δ errors | New/worse rules | Stopped running |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |")
        previous: HistoryRecord | None = None
        for run in runs:
            if previous is None:
                delta = "-"
                regressed = "-"
                stopped_cell = "-"
            else:
                stopped = _stopped_reporting(previous, run)
                delta = _delta_cell(previous, run, stopped)
                worse = [
                    rule_id
                    for rule_id, count in sorted(run.by_rule.items())
                    if count > previous.by_rule.get(rule_id, 0)
                ]
                regressed = ", ".join(worse) if worse else "-"
                if stopped is None:
                    stopped_cell = f"{UNKNOWN} (this run recorded no coverage)"
                else:
                    stopped_cell = ", ".join(stopped) if stopped else "-"
            lines.append(
                f"| {run.timestamp} | {run.errors} | {run.warnings} | {run.infos} | "
                f"{_scope_cell(run)} | {delta} | {regressed} | {stopped_cell} |"
            )
            previous = run
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
