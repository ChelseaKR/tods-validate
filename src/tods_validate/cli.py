"""Command-line interface.

Exit codes: 0 when no findings at or above the --fail-on severity were found
(the default fails only on errors), 1 when there were, 2 when the package or
configuration could not be read at all.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import click

from . import __version__
from ._pkgio import UnreadableFileError
from .anonymize import AlreadyProtectedError, anonymize_package
from .baseline import diff_findings, load_baseline_identities
from .config import PROFILES, Config, ConfigError, _merge, _profile_config, load_config
from .doctor import (
    ValidatePayload,
    doctor_to_dict,
    render_doctor_markdown,
    render_doctor_text,
    run_doctor,
)
from .drift import analyze_drift, drift_to_dict, render_drift_markdown, render_drift_text
from .findings import Finding, Severity
from .fix import fix_package
from .init import SHAPES, DestinationNotEmptyError
from .init import scaffold as scaffold_package
from .loader import Package, PackageNotFoundError, load_package
from .merge import merge_feeds
from .policy import EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE, GatingPolicy
from .report import (
    RENDERERS,
    render_batch_markdown,
    render_batch_text,
    render_github,
    render_html,
    render_json,
    render_markdown,
    render_sarif,
    render_text,
    summarize,
)
from .rules import CATEGORIES, RunCoverage, all_rules, render_rule_detail
from .runner import run_with_coverage
from .schema import SPEC_VERSION, SUPPORTED_SPEC_VERSIONS
from .stats import (
    collect_cross_stats,
    collect_stats,
    comparison_to_dict,
    render_comparison_markdown,
    render_comparison_text,
    render_stats_markdown,
    render_stats_text,
    stats_to_dict,
)
from .workspace import (
    DEFAULT_HISTORY_DIR,
    HistoryError,
    append_record,
    build_record,
    load_history,
    render_trend,
)

if TYPE_CHECKING:
    from .suggest import Suggestion


def _fail(message: str) -> NoReturn:
    click.echo(f"tods-validate: error: {message}", err=True)
    sys.exit(EXIT_USAGE)


def _resolve_config(config_path: str | None) -> Config:
    explicit = Path(config_path) if config_path else None
    if explicit is not None and not explicit.is_file():
        _fail(f"config file {explicit} does not exist.")
    try:
        return load_config(explicit, start_dir=Path.cwd())
    except ConfigError as exc:
        _fail(str(exc))


def _check_rule_ids(ignore: tuple[str, ...]) -> None:
    known = {r.id for r in all_rules()}
    unknown = sorted(set(ignore) - known)
    if unknown:
        _fail(
            f"unknown rule ID(s) in ignore list: {', '.join(unknown)}. "
            "See docs/rules.md for the rule catalog."
        )


def _check_enable(enable: tuple[str, ...]) -> None:
    known = {r.id for r in all_rules()} | set(CATEGORIES)
    unknown = sorted(set(enable) - known)
    if unknown:
        _fail(
            f"unknown --enable token(s): {', '.join(unknown)}. Use a rule ID or a "
            f"category ({', '.join(CATEGORIES)})."
        )


def _check_spec_version(spec_version: str) -> None:
    if spec_version not in SUPPORTED_SPEC_VERSIONS:
        _fail(
            f"unsupported --spec-version {spec_version!r}. This build validates against: "
            f"{', '.join(SUPPORTED_SPEC_VERSIONS)}."
        )


def _write_github_outputs(findings: list[Finding]) -> None:
    """Expose counts as GitHub Action step outputs when running in Actions."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    counts = summarize(findings)
    try:
        with open(output_file, "a", encoding="utf-8") as fh:
            fh.write(f"error-count={counts[Severity.ERROR]}\n")
            fh.write(f"warning-count={counts[Severity.WARNING]}\n")
            fh.write(f"info-count={counts[Severity.INFO]}\n")
    except OSError:
        pass  # best effort; never fail validation over an output file


def _render(
    output_format: str,
    findings: list[Finding],
    source: str,
    *,
    max_findings: int | None,
    quiet: bool,
    stamp: bool,
    coverage: RunCoverage | None = None,
    suggestions: list[Suggestion] | None = None,
    spec_version: str = SPEC_VERSION,
    package: Package | None = None,
    timeline: bool = False,
) -> str:
    if output_format == "text":
        return render_text(
            findings,
            source,
            max_findings=max_findings,
            quiet=quiet,
            coverage=coverage,
            spec_version=spec_version,
        )
    if output_format == "markdown":
        return render_markdown(
            findings, source, stamp=stamp, coverage=coverage, spec_version=spec_version
        )
    if output_format == "json":
        return render_json(
            findings,
            source,
            coverage=coverage,
            suggestions=suggestions,
            spec_version=spec_version,
        )
    if output_format == "sarif":
        return render_sarif(findings, source, coverage=coverage)
    if output_format == "html":
        return render_html(
            findings,
            source,
            coverage=coverage,
            spec_version=spec_version,
            timeline_package=package if timeline else None,
        )
    return render_github(findings, source, coverage=coverage)


class _DefaultToValidate(click.Group):
    """Route ``tods-validate path/`` to the validate command.

    ``tods-validate feed/`` predates the subcommands and stays supported;
    a path that is not a known subcommand is treated as ``validate``'s
    argument. A feed directory literally named like a subcommand can always
    be validated explicitly: ``tods-validate validate merge/``.
    """

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            return "validate", self.get_command(ctx, "validate"), args


@click.group(cls=_DefaultToValidate, name="tods-validate")
@click.version_option(__version__, message=f"%(prog)s %(version)s (TODS v{SPEC_VERSION})")
def main() -> None:
    """Validate TODS (Transit Operational Data Standard) feeds."""


@main.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "--gtfs",
    "gtfs_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Companion GTFS feed (directory or .zip) to resolve trip, stop, service, and "
        "block references against. If omitted and GTFS files sit next to the TODS "
        "files, those are used."
    ),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(sorted(RENDERERS)),
    default="text",
    show_default=True,
    help="Report format: text, JSON, Markdown, GitHub annotations, SARIF, or HTML.",
)
@click.option(
    "--timeline",
    is_flag=True,
    help="Include accessible per-run timelines in HTML output (requires --format html).",
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default=None,
    help="Exit non-zero if findings at or above this severity exist.  [default: error]",
)
@click.option(
    "--ignore",
    "ignore_ids",
    multiple=True,
    metavar="RULE_ID",
    help="Suppress a rule by ID (repeatable), e.g. --ignore TODS-W206.",
)
@click.option(
    "--enable",
    "enable_tokens",
    multiple=True,
    metavar="RULE_OR_CATEGORY",
    help=(
        "Turn on an opt-in rule by ID or a whole category (coverage, advisory, "
        "experimental). Repeatable."
    ),
)
@click.option(
    "--profile",
    type=click.Choice(sorted(PROFILES)),
    default=None,
    help=(
        "Apply a named preset of settings (overridden by other flags). "
        "'ingest-ready' is the go/no-go gate for a downstream CAD/AVL "
        "consumer deciding whether to import a feed."
    ),
)
@click.option(
    "--spec-version",
    default=None,
    help=f"TODS spec version to validate against.  [default: {SPEC_VERSION}]",
)
@click.option(
    "--baseline",
    "baseline_path",
    type=click.Path(exists=False),
    default=None,
    help="A previous JSON report; only findings new since it affect the exit code.",
)
@click.option(
    "--require-complete-run",
    is_flag=True,
    help=(
        "Also fail when a check could not run because an input was missing, such as "
        "a companion GTFS feed that was not given. Skips you asked for (--ignore, "
        "opt-in rules left off, --spec-version scoping) still exit 0."
    ),
)
@click.option(
    "--max-findings",
    type=int,
    default=None,
    help="Show at most this many findings in text output (the summary is unaffected).",
)
@click.option("--quiet", is_flag=True, help="Print only the summary, not each finding (text).")
@click.option(
    "--suggest",
    is_flag=True,
    help=(
        "After the report, list concrete fix suggestions for the mechanically-fixable "
        "findings, each marked 'auto' (safe; tods-validate fix applies it) or 'review'. "
        "Text and Markdown print a prose block; JSON adds a structured 'suggestions' array."
    ),
)
@click.option(
    "--stamp",
    is_flag=True,
    help="Add a provenance footer (version, timestamp) to Markdown for a citable report.",
)
@click.option(
    "--encoding", default=None, help="Override UTF-8 decoding for non-conforming exports."
)
@click.option(
    "--watch",
    is_flag=True,
    help="Re-validate whenever the feed changes (polls the files; Ctrl-C to stop).",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Configuration file. Without this option, a tods-validate.toml in the "
        "current directory is used if present."
    ),
)
def validate(  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    path: str,
    gtfs_path: str | None,
    output_format: str,
    timeline: bool,
    fail_on: str | None,
    ignore_ids: tuple[str, ...],
    enable_tokens: tuple[str, ...],
    profile: str | None,
    spec_version: str | None,
    baseline_path: str | None,
    require_complete_run: bool,
    max_findings: int | None,
    quiet: bool,
    suggest: bool,
    stamp: bool,
    encoding: str | None,
    watch: bool,
    config_path: str | None,
) -> None:
    """Validate the TODS feed at PATH.

    PATH is a directory or .zip file containing the TODS .txt files, with or
    without the GTFS feed alongside them.
    """
    if timeline and output_format != "html":
        _fail("--timeline requires --format html.")

    config = _resolve_config(config_path)
    if profile is not None:
        config = _merge(_profile_config(profile), config)

    enable = tuple(enable_tokens) + config.enable
    _check_enable(enable)
    effective_max = max_findings if max_findings is not None else config.max_findings
    effective_encoding = encoding or config.encoding
    effective_spec = spec_version or config.spec_version or SPEC_VERSION
    _check_spec_version(effective_spec)

    baseline_identities = None
    if baseline_path is not None:
        try:
            baseline_identities = load_baseline_identities(baseline_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            _fail(f"baseline {baseline_path} could not be read: {exc}")

    policy = GatingPolicy.from_config(
        fail_on=fail_on,
        config=config,
        ignore_ids=ignore_ids,
        baseline_identities=baseline_identities,
    )
    _check_rule_ids(tuple(policy.ignore))
    severity_remap = dict(config.severity_remap)

    def _validate_once() -> tuple[list[Finding], RunCoverage]:
        package, found, coverage = run_with_coverage(
            path,
            gtfs_path,
            enabled=frozenset(enable),
            encoding=effective_encoding,
            severity_remap=severity_remap,
            spec_version=effective_spec,
        )
        gate = policy.apply(found)
        if gate.suppressed_ignored:
            # Disclose that --ignore withheld these rules' findings, so a clean
            # report still admits what it did not report.
            coverage = coverage.with_ignored(policy.ignore)
        machine_suggestions: list[Suggestion] | None = None
        if suggest and output_format == "json":
            from .suggest import suggest_for_findings

            # Machine-form companion to the text/Markdown --suggest block below:
            # a structured suggestions array in the report itself, so a
            # dashboard need not parse prose to find current/proposed values.
            machine_suggestions = suggest_for_findings(gate.kept, package)
        click.echo(
            _render(
                output_format,
                gate.kept,
                package.source,
                max_findings=effective_max,
                quiet=quiet,
                stamp=stamp,
                coverage=coverage,
                suggestions=machine_suggestions,
                spec_version=effective_spec,
                package=package,
                timeline=timeline,
            )
        )
        if suggest and output_format in ("text", "markdown"):
            from .suggest import render_suggestions, suggest_for_findings

            click.echo("")
            click.echo(render_suggestions(suggest_for_findings(gate.kept, package), output_format))
        return gate.kept, coverage

    if watch:
        from .watch import watch as watch_feed

        click.echo(f"Watching {path} for changes; press Ctrl-C to stop.", err=True)

        def _tick() -> None:
            try:
                _validate_once()
            except PackageNotFoundError as exc:
                click.echo(f"tods-validate: {exc}", err=True)

        try:
            watch_feed(path, _tick)
        except KeyboardInterrupt:
            sys.exit(EXIT_CLEAN)
        return

    try:
        findings, coverage = _validate_once()
    except PackageNotFoundError as exc:
        _fail(str(exc))
    _write_github_outputs(findings)

    # The exit code considers only findings new since the baseline, if given
    # (policy.apply already filtered `findings` for --ignore, so re-running it
    # here just applies the baseline narrowing on top of the same kept list).
    #
    # A skipped check does not by itself change the exit code. That is a
    # deliberate choice, not an oversight: this tool has shipped as a merge
    # gate since 0.1.0, and every feed validated without a companion GTFS feed
    # skips 16 checks, so failing on a skip would turn those pipelines red on
    # an upgrade for something they never asked the tool to promise. The
    # report says what did not run instead, in every format, and
    # --require-complete-run is how a pipeline opts in to gating on it.
    gate = policy.apply(findings)
    incomplete = coverage.unrequested_skips if require_complete_run else ()
    if incomplete:
        click.echo(
            f"tods-validate: --require-complete-run: {len(incomplete)} check(s) could not "
            f"run because an input was missing: {', '.join(o.id for o in incomplete)}.",
            err=True,
        )
    sys.exit(EXIT_FINDINGS if gate.failed or incomplete else EXIT_CLEAN)


@main.command()
@click.argument("old", type=click.Path(exists=False))
@click.argument("new", type=click.Path(exists=False))
@click.option("--gtfs", "gtfs_path", type=click.Path(exists=False), default=None)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default=None,
    help="Exit non-zero if newly introduced findings reach this severity.  [default: error]",
)
@click.option(
    "--ignore",
    "ignore_ids",
    multiple=True,
    metavar="RULE_ID",
    help="Suppress a rule by ID (repeatable), e.g. --ignore TODS-W206.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Configuration file. Without this option, a tods-validate.toml in the "
        "current directory is used if present."
    ),
)
def diff(
    old: str,
    new: str,
    gtfs_path: str | None,
    fail_on: str | None,
    ignore_ids: tuple[str, ...],
    config_path: str | None,
) -> None:
    """Compare validation of two feeds: OLD then NEW.

    Reports which findings were fixed, newly introduced, or still present, so a
    change to a feed can be reviewed for regressions. Honors the same
    --config/--ignore/--fail-on policy as validate.

    A finding present in OLD and absent from NEW is only reported "fixed"
    when its rule actually ran in NEW. A rule that stopped running (a
    dropped or newly unreadable companion GTFS feed, most often) also makes
    its old findings disappear, but that is not evidence anything was fixed
    -- see #126 -- so those land in a separate "unknown" bucket instead, and
    any rule that ran in OLD but not in NEW is named, whether or not it had
    findings to lose.
    """
    config = _resolve_config(config_path)
    policy = GatingPolicy.from_config(fail_on=fail_on, config=config, ignore_ids=ignore_ids)
    _check_rule_ids(tuple(policy.ignore))
    severity_remap = dict(config.severity_remap)

    try:
        _, old_findings, old_coverage = run_with_coverage(
            old, gtfs_path, severity_remap=severity_remap
        )
        _, new_findings_list, new_coverage = run_with_coverage(
            new, gtfs_path, severity_remap=severity_remap
        )
    except PackageNotFoundError as exc:
        _fail(str(exc))

    old_kept = policy.apply(old_findings).kept
    new_kept = policy.apply(new_findings_list).kept
    result = diff_findings(old_kept, new_kept, new_coverage=new_coverage)
    click.echo(f"tods-validate diff: {old} -> {new}")
    click.echo(
        f"  fixed: {len(result.fixed)}, introduced: {len(result.introduced)}, "
        f"persisting: {len(result.persisting)}, moved: {len(result.moved)}, "
        f"unknown: {len(result.unknown)}"
    )
    for finding in result.introduced:
        loc = finding.location()
        click.echo(
            f"  + {finding.rule_id} [{loc}] {finding.message}"
            if loc
            else f"  + {finding.rule_id} {finding.message}"
        )
    for finding in result.fixed:
        loc = finding.location()
        click.echo(
            f"  - {finding.rule_id} [{loc}] {finding.message}"
            if loc
            else f"  - {finding.rule_id} {finding.message}"
        )
    for finding in result.moved:
        loc = finding.location()
        click.echo(
            f"  ~ {finding.rule_id} [{loc}] {finding.message}"
            if loc
            else f"  ~ {finding.rule_id} {finding.message}"
        )
    for finding in result.unknown:
        loc = finding.location()
        click.echo(
            f"  ? {finding.rule_id} [{loc}] {finding.message} (rule did not run in NEW)"
            if loc
            else f"  ? {finding.rule_id} {finding.message} (rule did not run in NEW)"
        )

    # Rules that ran in OLD and not in NEW, named even when they had nothing
    # to lose: a companion GTFS dropped between OLD and NEW can zero out 16
    # checks with 0 findings on either side, which the counts line above
    # would otherwise report as a silently clean diff (#126, same class as
    # #124's "clean report understates its own scope").
    regressed_ids = {o.id for o in old_coverage.ran} - {o.id for o in new_coverage.ran}
    if regressed_ids:
        regressed = RunCoverage(tuple(o for o in new_coverage.outcomes if o.id in regressed_ids))
        click.echo(
            f"  {len(regressed_ids)} rule(s) that ran in OLD do not run in NEW "
            "(their old findings, if any, are 'unknown' above, not 'fixed'):"
        )
        for line in regressed.skipped_detail_lines():
            click.echo(f"    {line}")

    gate = policy.apply(result.introduced)
    sys.exit(EXIT_FINDINGS if gate.failed else EXIT_CLEAN)


@main.command()
@click.argument("old_gtfs_path", metavar="OLD_GTFS", type=click.Path(exists=False))
@click.argument("new_gtfs_path", metavar="NEW_GTFS", type=click.Path(exists=False))
@click.option(
    "--tods",
    "tods_path",
    required=True,
    type=click.Path(exists=False),
    help="The TODS package whose GTFS references are being checked.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    show_default=True,
)
@click.option("--encoding", default=None)
def drift(
    old_gtfs_path: str,
    new_gtfs_path: str,
    tods_path: str,
    output_format: str,
    encoding: str | None,
) -> None:
    """Diagnose which TODS references break moving OLD_GTFS to NEW_GTFS.

    Given a TODS package (--tods) and two versions of its companion GTFS
    feed, reports exactly which referenced trip_id/stop_id values disappear
    and which trips' block_id changes -- the diagnosis behind the "your GTFS
    moved under your TODS" failure (see TODS-W302/W313's root-cause hint).
    Rename candidates are offered only when exactly one new GTFS ID is an
    unambiguous close match; they are hints for a human to review, never
    applied. Supplements from the TODS package are applied to both GTFS
    versions before comparing, so a break reported here is one `validate`
    against NEW_GTFS would also raise.

    Exits 1 if any reference breaks or block_id changes were found, so this
    can gate a GTFS-update PR before it reaches production; 0 if clean.
    """
    try:
        old_gtfs = load_package(old_gtfs_path, encoding=encoding)
        new_gtfs = load_package(new_gtfs_path, encoding=encoding)
        tods = load_package(tods_path, encoding=encoding)
    except PackageNotFoundError as exc:
        _fail(str(exc))

    report = analyze_drift(old_gtfs, new_gtfs, tods)
    if output_format == "json":
        click.echo(json.dumps(drift_to_dict(report), indent=2))
    elif output_format == "markdown":
        click.echo(render_drift_markdown(report))
    else:
        click.echo(render_drift_text(report))
    sys.exit(EXIT_FINDINGS if report.has_breaks else EXIT_CLEAN)


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=False))
@click.option("--gtfs", "gtfs_path", type=click.Path(exists=False), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    show_default=True,
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default=None,
    help="Exit non-zero if any feed has findings at or above this severity.  [default: error]",
)
@click.option(
    "--require-complete-run",
    is_flag=True,
    help=(
        "Also fail a feed when a check could not run because an input was missing, "
        "such as a companion GTFS feed that was not given. Skips a feed asked for "
        "(--ignore, opt-in rules left off) still leave it passing. See validate's "
        "flag of the same name."
    ),
)
@click.option(
    "--stamp",
    is_flag=True,
    help=(
        "Add a provenance footer (version, timestamp) to Markdown, for a citable "
        "fleet/portfolio compliance artifact."
    ),
)
@click.option(
    "--ignore",
    "ignore_ids",
    multiple=True,
    metavar="RULE_ID",
    help="Suppress a rule by ID (repeatable), e.g. --ignore TODS-W206.",
)
@click.option(
    "--history",
    "history_dir",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Append a schema-versioned summary record for each feed to "
        "DIR/history.jsonl (counts and rule IDs only, never finding messages). "
        "Also settable as [workspace] history-dir in tods-validate.toml."
    ),
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Configuration file. Without this option, a tods-validate.toml in the "
        "current directory is used if present."
    ),
)
def batch(
    paths: tuple[str, ...],
    gtfs_path: str | None,
    output_format: str,
    fail_on: str | None,
    require_complete_run: bool,
    stamp: bool,
    ignore_ids: tuple[str, ...],
    history_dir: str | None,
    config_path: str | None,
) -> None:
    """Validate several feeds and print a roll-up table.

    Each PATH is validated independently; the shared --gtfs companion, if given,
    is used for all of them. Honors the same --config/--ignore/--fail-on policy
    as validate, applied identically to every feed.
    """
    config = _resolve_config(config_path)
    policy = GatingPolicy.from_config(fail_on=fail_on, config=config, ignore_ids=ignore_ids)
    _check_rule_ids(tuple(policy.ignore))
    effective_history = history_dir or config.history_dir
    severity_remap = dict(config.severity_remap)

    rows: list[dict[str, object]] = []
    coverages: list[RunCoverage | None] = []
    any_failed = False
    for path in paths:
        try:
            package, findings, coverage = run_with_coverage(
                path, gtfs_path, severity_remap=severity_remap
            )
        except PackageNotFoundError as exc:
            rows.append({"source": path, "error": str(exc)})
            coverages.append(None)
            any_failed = True
            continue
        gate = policy.apply(findings)
        counts = gate.counts
        # A skipped check does not by itself fail a feed here either (see the
        # matching comment on validate's exit code): --require-complete-run is
        # how a fleet run opts in to that. What batch must never do is publish
        # status: pass on a partial run without saying so -- every row below
        # carries checksNotRun/coverage beside it regardless of this flag
        # (#127); this only decides whether an incomplete run also fails.
        incomplete = coverage.unrequested_skips if require_complete_run else ()
        failed = gate.failed or bool(incomplete)
        rows.append(
            {
                "source": package.source,
                "errors": counts.get(Severity.ERROR, 0),
                "warnings": counts.get(Severity.WARNING, 0),
                "infos": counts.get(Severity.INFO, 0),
                "status": "fail" if failed else "pass",
                "checksNotRun": len(coverage.skipped),
                "coverage": coverage.to_dict(),
            }
        )
        coverages.append(coverage)
        if failed:
            any_failed = True
        if effective_history is not None:
            record = build_record(
                gate.kept, package.source, tool_version=__version__, spec_version=SPEC_VERSION
            )
            append_record(Path(effective_history), record)

    if output_format == "json":
        click.echo(json.dumps({"feeds": rows}, indent=2))
    elif output_format == "markdown":
        click.echo(render_batch_markdown(rows, coverages, stamp=stamp))
    else:
        click.echo(render_batch_text(rows, coverages))
    sys.exit(EXIT_FINDINGS if any_failed else EXIT_CLEAN)


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=False))
@click.option("--gtfs", "gtfs_path", type=click.Path(exists=False), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    show_default=True,
)
@click.option("--encoding", default=None)
def stats(
    paths: tuple[str, ...], gtfs_path: str | None, output_format: str, encoding: str | None
) -> None:
    """Print descriptive statistics about one or more TODS feeds (counts, not a score).

    A single PATH prints that feed's profile. Multiple PATHs print a
    cross-feed comparison table plus an aggregate (totals/means/min/max)
    summary; the shared --gtfs companion, if given, is used for all of them.
    """
    if len(paths) == 1:
        try:
            feed_stats = collect_stats(paths[0], gtfs_path, encoding)
        except PackageNotFoundError as exc:
            _fail(str(exc))
        if output_format == "json":
            click.echo(json.dumps(stats_to_dict(feed_stats), indent=2))
        elif output_format == "markdown":
            click.echo(render_stats_markdown(feed_stats))
        else:
            click.echo(render_stats_text(feed_stats))
        return

    feeds = collect_cross_stats(paths, gtfs_path, encoding)
    if output_format == "json":
        click.echo(json.dumps(comparison_to_dict(feeds), indent=2))
    elif output_format == "markdown":
        click.echo(render_comparison_markdown(feeds))
    else:
        click.echo(render_comparison_text(feeds))


@main.command()
@click.option(
    "--history",
    "history_dir",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Directory containing history.jsonl written by `batch --history`. "
        "Without this, the [workspace] history-dir from tods-validate.toml is "
        "used, falling back to .tods-history/."
    ),
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Configuration file. Without this option, a tods-validate.toml in the "
        "current directory is used if present."
    ),
)
def trend(history_dir: str | None, config_path: str | None) -> None:
    """Print a Markdown trend table from the local run-history ledger.

    Reads the append-only ledger written by `batch --history` and renders one
    table per feed/source, so a regression between runs (more errors, a new
    rule firing) is visible without re-running anything.
    """
    config = _resolve_config(config_path)
    effective_history = history_dir or config.history_dir or str(DEFAULT_HISTORY_DIR)
    try:
        records = load_history(Path(effective_history))
    except HistoryError as exc:
        _fail(str(exc))
    click.echo(render_trend(records))


@main.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "-o",
    "--output",
    "output_path",
    required=True,
    type=click.Path(),
    help="Where to write the pseudonymized package: a directory or a path ending in .zip.",
)
@click.option(
    "--salt",
    default=None,
    help="Fixed salt for stable pseudonyms across runs (default: a random, single-use salt).",
)
@click.option("--encoding", default=None)
@click.option(
    "--also",
    "also_fields",
    multiple=True,
    metavar="FILE:FIELD",
    help=("Pseudonymize an extra column, e.g. --also run_events.txt:job_type. Repeatable."),
)
def anonymize(
    path: str,
    output_path: str,
    salt: str | None,
    encoding: str | None,
    also_fields: tuple[str, ...],
) -> None:
    """Write a copy of the package with person-identifying fields pseudonymized.

    employee_id, license_plate, vehicle_label, and vehicle_id are replaced
    with stable pseudonyms. Use --also FILE:FIELD to pseudonymize additional
    extension columns (fails if FIELD is already protected by default).
    This is pseudonymization, not guaranteed anonymity: after each run, a
    "Carried through unprotected" table lists every remaining column that
    still holds non-enum data, numeric or not, so the residual risk is
    disclosed rather than silently passed through.
    """
    also: list[tuple[str, str]] = []
    for entry in also_fields:
        if entry.count(":") != 1 or not all(entry.split(":")):
            _fail(f"invalid --also value {entry!r}; expected FILE:FIELD, e.g. vehicles.txt:notes.")
        fname, field_name = entry.split(":")
        also.append((fname, field_name))
    try:
        result = anonymize_package(path, Path(output_path), salt=salt, encoding=encoding, also=also)
    except PackageNotFoundError as exc:
        _fail(str(exc))
    except AlreadyProtectedError as exc:
        _fail(str(exc))
    except UnreadableFileError as exc:
        _fail(str(exc))
    for target, count in sorted(result.replacements.items()):
        click.echo(f"{target}: {count} value(s) pseudonymized")
    click.echo(f"Wrote {len(result.written)} file(s) to {output_path}.")
    click.echo("Carried through unprotected (not pseudonymized, still free text):")
    if result.carried_through:
        for fname, col in result.carried_through:
            click.echo(f"  {fname}:{col}")
    else:
        click.echo("  (none)")


@main.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help=(
        "Write the fixed package here (a directory, or a path ending in .zip). "
        "Without it, fix is a dry run that only reports what it would change."
    ),
)
@click.option("--encoding", default=None)
def fix(path: str, output_path: str | None, encoding: str | None) -> None:
    """Apply safe, deterministic fixes (trim whitespace, drop blank/duplicate rows).

    Fixes TODS-W206 whitespace padding, drops entirely-blank rows, and drops rows
    that exactly duplicate an earlier one (TODS-W408). A dry run by default; pass
    -o/--output to write the fixed package. Re-encodes files as UTF-8 without a BOM.
    """
    try:
        result = fix_package(path, Path(output_path) if output_path is not None else None, encoding)
    except PackageNotFoundError as exc:
        _fail(str(exc))
    except UnreadableFileError as exc:
        _fail(str(exc))
    click.echo(f"tods-validate fix: {result.source}")
    for name in result.unreadable:
        # Said before the "Nothing to fix." line, which otherwise reads as
        # "this package is fine" when a file in it was never read.
        click.echo(f"  {name}: could not be read; not analyzed and not fixable (see TODS-E103)")
    if not result.changed_any:
        click.echo("  Nothing to fix.")
        return
    for name in sorted(
        set(result.trimmed) | set(result.blank_rows_dropped) | set(result.duplicate_rows_dropped)
    ):
        parts = []
        if name in result.trimmed:
            parts.append(f"trimmed whitespace on {result.trimmed[name]} value(s)")
        if name in result.blank_rows_dropped:
            parts.append(f"dropped {result.blank_rows_dropped[name]} blank row(s)")
        if name in result.duplicate_rows_dropped:
            parts.append(f"dropped {result.duplicate_rows_dropped[name]} duplicate row(s)")
        click.echo(f"  {name}: {', '.join(parts)}")
    total = result.total_trimmed + result.total_blank_dropped + result.total_duplicates_dropped
    if result.written:
        click.echo(f"  wrote {len(result.written)} file(s) to {output_path}")
    else:
        click.echo(f"  dry run: re-run with -o OUTPUT to write {total} fix(es)")


@main.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "--gtfs",
    "gtfs_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Companion GTFS feed (directory or .zip). Omit if the GTFS files sit "
        "next to the TODS files."
    ),
)
@click.option(
    "-o",
    "--output",
    "output_path",
    required=True,
    type=click.Path(),
    help="Where to write the merged feed: a directory, or a path ending in .zip.",
)
@click.option(
    "--manifest/--no-manifest",
    default=True,
    show_default=True,
    help="Also write merge-report.json describing per-file changes.",
)
def merge(path: str, gtfs_path: str | None, output_path: str, manifest: bool) -> None:
    """Write the TODS-Supplemented GTFS feed.

    Applies the supplement files in the TODS package at PATH to the companion
    GTFS feed and writes the merged GTFS dataset. The spec says this dataset
    should form valid GTFS; check it with MobilityData's gtfs-validator.
    Validate the TODS package first so merge decisions rest on clean inputs.
    """
    try:
        result = merge_feeds(
            Path(path),
            Path(gtfs_path) if gtfs_path else None,
            Path(output_path),
        )
    except PackageNotFoundError as exc:
        _fail(str(exc))

    for name, file_stats in sorted(result.stats.items()):
        details = []
        if file_stats.updated:
            details.append(f"{file_stats.updated} row(s) updated")
        if file_stats.added:
            details.append(f"{file_stats.added} added")
        if file_stats.deleted:
            details.append(f"{file_stats.deleted} deleted")
        if file_stats.skipped:
            details.append(f"{file_stats.skipped} skipped (blank primary key)")
        click.echo(f"{name}: {', '.join(details) if details else 'no changes'}")

    if manifest:
        manifest_payload = {
            "validator": "tods-validate",
            "toolVersion": __version__,
            "specVersion": SPEC_VERSION,
            "source": str(path),
            "files": {
                name: {
                    "updated": s.updated,
                    "added": s.added,
                    "deleted": s.deleted,
                    "skipped": s.skipped,
                }
                for name, s in sorted(result.stats.items())
            },
            "written": result.written,
        }
        out = Path(output_path)
        manifest_dir = out.parent if out.suffix.lower() == ".zip" else out
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifest_dir / "merge-report.json"
        manifest_file.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
        click.echo(f"Wrote merge manifest to {manifest_file}.")

    click.echo(f"Wrote {len(result.written)} file(s) to {output_path}.")


@main.command()
@click.argument("path", type=click.Path(exists=False))
@click.option(
    "--gtfs",
    "gtfs_path",
    type=click.Path(exists=False),
    default=None,
    help=(
        "Companion GTFS feed (directory or .zip). Omit if the GTFS files sit "
        "next to the TODS files."
    ),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "markdown", "json"]),
    default="text",
    show_default=True,
    help="Report format for the combined pass.",
)
@click.option(
    "--gtfs-validator-jar",
    "gtfs_validator_jar",
    type=click.Path(exists=False),
    default=None,
    envvar="GTFS_VALIDATOR_JAR",
    help=(
        "Path to MobilityData's gtfs-validator jar, to check the merged feed. Never "
        "downloaded automatically; without java and this jar (or GTFS_VALIDATOR_JAR), "
        "that stage is skipped and clearly labeled as such."
    ),
)
@click.option(
    "--encoding", default=None, help="Override UTF-8 decoding for non-conforming exports."
)
@click.option(
    "--stamp",
    is_flag=True,
    help="Add a provenance footer (version, timestamp) to Markdown for a citable report.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default=None,
    help="Exit non-zero if validate findings reach this severity.  [default: error]",
)
@click.option(
    "--require-complete-run",
    is_flag=True,
    help=(
        "Also fail when a check could not run because an input was missing, such as "
        "a companion GTFS feed that was not given. Skips you asked for (opt-in rules "
        "left off, --spec-version scoping) still exit 0."
    ),
)
def doctor(
    path: str,
    gtfs_path: str | None,
    output_format: str,
    gtfs_validator_jar: str | None,
    encoding: str | None,
    stamp: bool,
    fail_on: str | None,
    require_complete_run: bool,
) -> None:
    """Run validate, merge, gtfs-validator, and stats as one pass on PATH.

    One combined report covering the full publish-readiness sequence: validate
    the TODS package, merge it against its companion GTFS feed, optionally
    check that merged feed with MobilityData's gtfs-validator (only if java
    and a jar are already available; never downloaded), and print feed stats.
    Any stage that could not run is labeled SKIPPED with its reason, so a
    skipped check can never be misread as a pass.
    """
    try:
        report = run_doctor(
            path,
            gtfs_path,
            jar_path=gtfs_validator_jar,
            encoding=encoding,
        )
    except PackageNotFoundError as exc:
        _fail(str(exc))

    if output_format == "json":
        click.echo(json.dumps(doctor_to_dict(report), indent=2))
    elif output_format == "markdown":
        click.echo(render_doctor_markdown(report, stamp=stamp))
    else:
        click.echo(render_doctor_text(report))

    validate_stage = report.stage("validate")
    validate_payload = validate_stage.payload if validate_stage is not None else None
    findings = validate_payload.findings if isinstance(validate_payload, ValidatePayload) else []
    counts = summarize(findings)
    effective_fail_on = fail_on or "error"
    failed = counts[Severity.ERROR] > 0 or (
        effective_fail_on == "warning" and counts[Severity.WARNING] > 0
    )
    validator_stage = report.stage("gtfs-validator")
    if validator_stage is not None and validator_stage.status == "failed":
        failed = True

    # Same contract as validate and batch: a skipped check does not change the
    # exit code by itself, and --require-complete-run is how a pipeline opts in
    # to gating on one. doctor is the command that composes the whole pipeline,
    # so it was the one place the flag could not be reached (#185).
    coverage = validate_payload.coverage if isinstance(validate_payload, ValidatePayload) else None
    incomplete = coverage.unrequested_skips if (require_complete_run and coverage) else ()
    if incomplete:
        click.echo(
            f"tods-validate: --require-complete-run: {len(incomplete)} check(s) could not "
            f"run because an input was missing: {', '.join(o.id for o in incomplete)}.",
            err=True,
        )
    sys.exit(EXIT_FINDINGS if failed or incomplete else EXIT_CLEAN)


@main.command(name="rules")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Plain listing, or JSON for tooling.",
)
def rules_command(output_format: str) -> None:
    """List every rule with its severity and description."""
    rules = sorted(all_rules(), key=lambda r: r.id.split("-")[1][1:])
    if output_format == "json":
        payload = [
            {
                "id": r.id,
                "severity": r.severity.name,
                "title": r.title,
                "description": r.description,
                "specSection": r.spec_section,
                "needsGtfs": r.needs_gtfs,
                # Which companion GTFS files the rule reads. Each inner list is
                # a set of alternatives; the rule is skipped
                # ("skipped:needs_gtfs_table") unless every group is satisfied.
                "gtfsTables": [list(group) for group in r.gtfs_tables],
                "category": r.category,
                "defaultEnabled": r.default_enabled,
                "interpretation": r.interpretation,
            }
            for r in rules
        ]
        click.echo(json.dumps(payload, indent=2))
        return
    for r in rules:
        needs = " (needs companion GTFS)" if r.needs_gtfs else ""
        optin = "" if r.default_enabled else f" (opt-in: --enable {r.category})"
        click.echo(f"{r.id}  {r.severity.name:7}  {r.title}{needs}{optin}")


@main.command(name="explain")
@click.argument("rule_id", metavar="RULE_ID")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "markdown"]),
    default="text",
    show_default=True,
    help="Plain text for the terminal, or paste-ready Markdown.",
)
def explain(rule_id: str, output_format: str) -> None:
    """Show RULE_ID's full detail: description, spec citation, and a worked example.

    Offline - reads only the rule registry, no feed required. Rendering is
    shared with docs/rules.md and editor hovers (see `tods-validate lsp`), so
    the rule catalog, the terminal, and the editor cannot describe a rule
    differently.
    """
    known = {r.id: r for r in all_rules()}
    rule_def = known.get(rule_id)
    if rule_def is None:
        _fail(
            f"unknown rule ID {rule_id!r}. Run `tods-validate rules` or see "
            "docs/rules.md for the rule catalog."
        )
    click.echo(render_rule_detail(rule_def, output_format))


@main.command(name="init")
@click.argument("dest", type=click.Path(exists=False), default=".")
@click.option(
    "--shape",
    type=click.Choice(sorted(SHAPES)),
    default="runs",
    show_default=True,
    help="Which TODS files to scaffold: run events only, or runs plus vehicles.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Scaffold into DEST even if it already exists and is not empty.",
)
def init_command(dest: str, shape: str, force: bool) -> None:
    """Scaffold a starter TODS package at DEST that validates clean.

    Writes GTFS base files, TODS files, and a tods-validate.toml plus CI
    workflow stub, all generated from schema.py so headers can never drift
    and sample rows copied from a feed already known to validate clean. Run
    `tods-validate DEST` afterward to see it pass.
    """
    try:
        written = scaffold_package(Path(dest), shape, force=force)
    except (ValueError, DestinationNotEmptyError) as exc:
        _fail(str(exc))
    click.echo(f"tods-validate init: wrote {len(written)} file(s) to {dest}")
    for path in written:
        click.echo(f"  {path}")


@main.command(name="lsp")
def lsp_command() -> None:
    """Run the language server over stdio (for editor integration).

    Editors launch this; it is not meant to be run by hand. Requires the optional
    'lsp' extra: pip install 'tods-validate[lsp]'.
    """
    try:
        from .lsp import main as serve
    except ImportError:
        _fail("The language server needs the 'lsp' extra: pip install 'tods-validate[lsp]'")
    serve()


if __name__ == "__main__":
    main()
