"""``doctor``: one honest end-to-end pass.

Composes the existing pipeline stages -- validate, merge, (optionally)
MobilityData's gtfs-validator against the merged feed, and stats -- into a
single combined report. The whole point is honesty: a stage that could not
run (no companion GTFS, no Java, no gtfs-validator jar) is always labeled
SKIPPED with a specific reason, never silently dropped, so a report can never
be misread as "everything passed" when a stage simply did not execute.

The same rule governs the one document this module reads from another tool.
gtfs-validator's ``report.json`` is counted only when its shape is fully
understood; a report that parses as JSON but is shaped some other way is a
FAILED stage naming what could not be read, never zero notices (#147).

gtfs-validator is invoked only when java and a jar are already available on
this machine (``--gtfs-validator-jar`` or the ``GTFS_VALIDATOR_JAR`` env var).
This module never downloads it -- no surprise network access.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .findings import Finding, Severity
from .loader import PackageNotFoundError
from .merge import merge_feeds
from .report import render_markdown, render_text, summarize
from .runner import run
from .schema import SPEC_VERSION
from .stats import (
    FeedStats,
    collect_stats,
    render_stats_markdown,
    render_stats_text,
    stats_to_dict,
)

StageName = str  # "validate" | "merge" | "gtfs-validator" | "stats"
StageStatus = str  # "ran" | "skipped" | "failed"

_STAGE_TITLES: dict[str, str] = {
    "validate": "Validate",
    "merge": "Merge",
    "gtfs-validator": "GTFS-validator",
    "stats": "Stats",
}


@dataclass
class ValidatePayload:
    findings: list[Finding]
    source: str


@dataclass
class MergePayload:
    written: list[str]
    output_dir: str


@dataclass
class GtfsValidatorPayload:
    error_notices: int
    warning_notices: int
    info_notices: int
    notice_codes: int
    report_dir: str


@dataclass
class StatsPayload:
    stats: FeedStats


@dataclass
class StageResult:
    """The outcome of one stage of the doctor pipeline.

    ``status`` is one of ``"ran"``, ``"skipped"``, or ``"failed"``. ``reason``
    is set for ``skipped`` and ``failed`` stages and explains, in the same
    honest terms a human would want, why the stage did not produce a result.
    ``payload`` carries the stage's own result type (``ValidatePayload``,
    ``MergePayload``, ``GtfsValidatorPayload``, or ``StatsPayload``) when the
    stage ran.
    """

    name: StageName
    status: StageStatus
    reason: str | None = None
    payload: object | None = None


@dataclass
class DoctorReport:
    source: str
    stages: list[StageResult] = field(default_factory=list)

    def stage(self, name: str) -> StageResult | None:
        return next((s for s in self.stages if s.name == name), None)


def _run_merge_stage(
    path: str | Path, gtfs_path: str | Path | None, merged_dir: Path
) -> tuple[StageResult, Path | None]:
    try:
        result = merge_feeds(Path(path), Path(gtfs_path) if gtfs_path else None, merged_dir)
    except PackageNotFoundError as exc:
        return StageResult(name="merge", status="skipped", reason=str(exc)), None
    payload = MergePayload(written=result.written, output_dir=str(merged_dir))
    return StageResult(name="merge", status="ran", payload=payload), merged_dir


@dataclass(frozen=True)
class _NoticeCounts:
    """Notice totals read out of a gtfs-validator ``report.json``."""

    errors: int
    warnings: int
    infos: int
    codes: int


_JSON_TYPE_NAMES: dict[type, str] = {
    type(None): "null",
    bool: "a boolean",
    int: "a number",
    float: "a number",
    str: "a string",
    list: "an array",
    dict: "an object",
}


def _json_type(value: object) -> str:
    """Name a parsed JSON value the way the JSON spec does, for a message."""
    return _JSON_TYPE_NAMES.get(type(value), type(value).__name__)


_COUNTED_SEVERITIES = ("ERROR", "WARNING", "INFO")


def _read_notice(index: int, notice: object) -> tuple[str, int] | str:
    """``(severity, totalNotices)`` for one notice entry, or why it is unreadable."""
    where = f"notices[{index}]"
    if not isinstance(notice, dict):
        return f"{where} is {_json_type(notice)}, not an object"
    total = notice.get("totalNotices")
    if isinstance(total, bool) or not isinstance(total, int):
        return f"{where} has no integer 'totalNotices', so its notices cannot be counted"
    severity = notice.get("severity")
    if not isinstance(severity, str) or severity not in _COUNTED_SEVERITIES:
        return (
            f"{where} has severity {severity!r}, which this version of tods-validate "
            "does not know how to count"
        )
    return severity, total


def _read_gtfs_validator_notices(raw: object) -> _NoticeCounts | str:
    """Count the notices in a parsed gtfs-validator ``report.json``.

    Returns counts, or a sentence saying why the document could not be read.
    It never returns counts it had to guess at, and that is the whole point:
    zero notices read out of a document this code did not understand renders
    identically to a genuinely clean gtfs-validator run ("0 error notice(s),
    0 warning notice(s), 0 info notice(s)"), which is exactly the misreading
    this module exists to prevent. A shape this version does not recognise is
    a stage that produced no result, so the caller reports it FAILED (#147).

    Being strict costs something and it is the right trade here: if a future
    gtfs-validator renames the top-level key or adds a fourth severity, this
    stage stops with a specific reason naming what it did not understand,
    rather than reporting a merged feed as clean because the counters it knows
    about all happened to stay at zero.
    """
    if not isinstance(raw, dict):
        return (
            f"could not read gtfs-validator's report.json: it is valid JSON but "
            f"{_json_type(raw)}, not an object, so it names no notices."
        )
    if "notices" not in raw:
        return "could not read gtfs-validator's report.json: it has no top-level 'notices' array."
    notices = raw["notices"]
    if not isinstance(notices, list):
        return (
            f"could not read gtfs-validator's report.json: its top-level 'notices' "
            f"is {_json_type(notices)}, not an array."
        )

    tallies = dict.fromkeys(_COUNTED_SEVERITIES, 0)
    for index, notice in enumerate(notices):
        entry = _read_notice(index, notice)
        if isinstance(entry, str):
            return f"could not read gtfs-validator's report.json: {entry}."
        severity, total = entry
        tallies[severity] += total

    return _NoticeCounts(
        errors=tallies["ERROR"],
        warnings=tallies["WARNING"],
        infos=tallies["INFO"],
        codes=len(notices),
    )


def _run_gtfs_validator_stage(  # noqa: C901 - stage has several user-facing skip/fail exits
    merged_output: Path | None,
    *,
    run_gtfs_validator: bool,
    jar_path: str | None,
    report_dir: Path,
) -> StageResult:
    name = "gtfs-validator"
    if not run_gtfs_validator:
        return StageResult(name=name, status="skipped", reason="gtfs-validator stage was disabled.")
    if merged_output is None:
        return StageResult(
            name=name,
            status="skipped",
            reason=(
                "merged-feed GTFS validity NOT checked: the merge stage was skipped, "
                "so there is no merged feed to check."
            ),
        )

    java = shutil.which("java")
    if java is None:
        return StageResult(
            name=name,
            status="skipped",
            reason="merged-feed GTFS validity NOT checked: java was not found on PATH.",
        )

    jar = jar_path or os.environ.get("GTFS_VALIDATOR_JAR")
    if not jar or not Path(jar).is_file():
        return StageResult(
            name=name,
            status="skipped",
            reason=(
                "merged-feed GTFS validity NOT checked: no gtfs-validator jar found "
                "(pass --gtfs-validator-jar or set GTFS_VALIDATOR_JAR; tods-validate "
                "never downloads it automatically)."
            ),
        )

    try:
        proc = subprocess.run(  # noqa: S603 - command shape is fixed; inputs are file paths
            [java, "-jar", jar, "-i", str(merged_output), "-o", str(report_dir)],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return StageResult(
            name=name, status="failed", reason=f"gtfs-validator subprocess failed: {exc}"
        )

    report_file = report_dir / "report.json"
    if not report_file.is_file():
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit code {proc.returncode}"
        return StageResult(
            name=name,
            status="failed",
            reason=f"gtfs-validator did not produce a report.json: {detail[:500]}",
        )

    try:
        raw = json.loads(report_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return StageResult(
            name=name,
            status="failed",
            reason=f"could not parse gtfs-validator report.json: {exc}",
        )

    counted = _read_gtfs_validator_notices(raw)
    if isinstance(counted, str):
        return StageResult(name=name, status="failed", reason=counted)

    payload = GtfsValidatorPayload(
        error_notices=counted.errors,
        warning_notices=counted.warnings,
        info_notices=counted.infos,
        notice_codes=counted.codes,
        report_dir=str(report_dir),
    )
    return StageResult(name=name, status="ran", payload=payload)


def _run_stats_stage(
    path: str | Path, gtfs_path: str | Path | None, encoding: str | None
) -> StageResult:
    try:
        feed_stats = collect_stats(path, gtfs_path, encoding)
    except PackageNotFoundError as exc:
        return StageResult(name="stats", status="failed", reason=str(exc))
    return StageResult(name="stats", status="ran", payload=StatsPayload(stats=feed_stats))


def run_doctor(
    path: str | Path,
    gtfs_path: str | Path | None = None,
    *,
    run_gtfs_validator: bool = True,
    jar_path: str | None = None,
    encoding: str | None = None,
    enabled: frozenset[str] = frozenset(),
    ignore: tuple[str, ...] = (),
) -> DoctorReport:
    """Run validate -> merge -> (optional) gtfs-validator -> stats as one pass.

    ``path`` must load as a TODS package; a :class:`PackageNotFoundError` from
    that first stage propagates (there is nothing to report on). Every later
    stage is independently guarded: a companion GTFS feed that cannot be
    found for ``merge`` marks that stage (and, in turn, ``gtfs-validator``)
    skipped rather than aborting the whole pass, and ``stats`` failing to load
    its own package is recorded as a failed stage instead of raising.
    """
    package, findings = run(path, gtfs_path, enabled=enabled, encoding=encoding)
    if ignore:
        findings = [f for f in findings if f.rule_id not in ignore]

    stages: list[StageResult] = [
        StageResult(
            name="validate",
            status="ran",
            payload=ValidatePayload(findings=findings, source=package.source),
        )
    ]

    with tempfile.TemporaryDirectory(prefix="tods-validate-doctor-") as tmp:
        tmp_path = Path(tmp)
        merge_stage, merged_output = _run_merge_stage(path, gtfs_path, tmp_path / "merged")
        stages.append(merge_stage)

        validator_stage = _run_gtfs_validator_stage(
            merged_output,
            run_gtfs_validator=run_gtfs_validator,
            jar_path=jar_path,
            report_dir=tmp_path / "gtfs-validator-report",
        )
        stages.append(validator_stage)

    stages.append(_run_stats_stage(path, gtfs_path, encoding))

    return DoctorReport(source=package.source, stages=stages)


def _marker(stage: StageResult) -> str:
    if stage.status == "ran":
        return "RAN"
    if stage.status == "skipped":
        return f"SKIPPED ({stage.reason})" if stage.reason else "SKIPPED"
    return f"FAILED ({stage.reason})" if stage.reason else "FAILED"


def _overall_line(report: DoctorReport) -> str:
    summary = ", ".join(f"{s.name} {_marker_word(s)}" for s in report.stages)
    return f"Stages: {summary}."


def _marker_word(stage: StageResult) -> str:
    return stage.status.upper()


def _strip_leading_heading(text: str) -> str:
    """Drop a renderer's own ``# Title`` line (and the blank line after it)."""
    lines = text.split("\n")
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    if lines and lines[0] == "":
        lines = lines[1:]
    return "\n".join(lines)


def render_doctor_text(report: DoctorReport) -> str:
    lines = [f"tods-validate doctor: {report.source}", ""]
    for stage in report.stages:
        title = _STAGE_TITLES.get(stage.name, stage.name)
        lines.append(f"== {title}: {_marker(stage)} ==")
        payload = stage.payload
        if isinstance(payload, ValidatePayload):
            lines.append(render_text(payload.findings, payload.source))
        elif isinstance(payload, MergePayload):
            lines.append(f"Wrote {len(payload.written)} file(s) to a temporary merged GTFS feed.")
        elif isinstance(payload, GtfsValidatorPayload):
            lines.append(
                f"{payload.error_notices} error notice(s), {payload.warning_notices} "
                f"warning notice(s), {payload.info_notices} info notice(s) across "
                f"{payload.notice_codes} notice code(s)."
            )
        elif isinstance(payload, StatsPayload):
            lines.append(render_stats_text(payload.stats))
        lines.append("")
    lines.append(_overall_line(report))
    return "\n".join(lines)


def render_doctor_markdown(report: DoctorReport, *, stamp: bool = False) -> str:
    lines = [f"# TODS doctor report: {report.source}", ""]
    for stage in report.stages:
        title = _STAGE_TITLES.get(stage.name, stage.name)
        lines.append(f"## {title}: {_marker(stage)}")
        payload = stage.payload
        body: str | None = None
        if isinstance(payload, ValidatePayload):
            body = _strip_leading_heading(render_markdown(payload.findings, payload.source))
        elif isinstance(payload, MergePayload):
            body = f"Wrote {len(payload.written)} file(s) to a temporary merged GTFS feed."
        elif isinstance(payload, GtfsValidatorPayload):
            body = (
                f"{payload.error_notices} error notice(s), {payload.warning_notices} "
                f"warning notice(s), {payload.info_notices} info notice(s) across "
                f"{payload.notice_codes} notice code(s)."
            )
        elif isinstance(payload, StatsPayload):
            body = _strip_leading_heading(render_stats_markdown(payload.stats))
        if body is not None:
            lines.append("")
            lines.append(body)
        lines.append("")
    lines.append(_overall_line(report))
    if stamp:
        lines.append("")
        lines.append("---")
        lines.append(
            f"_Generated by tods-validate {__version__} against TODS v{SPEC_VERSION} at "
            f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}._"
        )
    return "\n".join(lines)


def doctor_to_dict(report: DoctorReport) -> dict[str, object]:
    """A machine-readable object with a per-stage ``status`` field."""
    stages_payload: list[dict[str, object]] = []
    for stage in report.stages:
        entry: dict[str, object] = {
            "name": stage.name,
            "status": stage.status,
            "reason": stage.reason,
        }
        payload = stage.payload
        if isinstance(payload, ValidatePayload):
            counts = summarize(payload.findings)
            entry["errors"] = counts[Severity.ERROR]
            entry["warnings"] = counts[Severity.WARNING]
            entry["infos"] = counts[Severity.INFO]
            entry["findings"] = [f.to_dict() for f in payload.findings]
        elif isinstance(payload, MergePayload):
            entry["written"] = payload.written
        elif isinstance(payload, GtfsValidatorPayload):
            entry["errorNotices"] = payload.error_notices
            entry["warningNotices"] = payload.warning_notices
            entry["infoNotices"] = payload.info_notices
            entry["noticeCodes"] = payload.notice_codes
        elif isinstance(payload, StatsPayload):
            entry["stats"] = stats_to_dict(payload.stats)
        stages_payload.append(entry)

    return {
        "validator": "tods-validate",
        "toolVersion": __version__,
        "specVersion": SPEC_VERSION,
        "source": report.source,
        "stages": stages_payload,
    }
