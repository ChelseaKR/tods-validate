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
from typing import NoReturn

import click

from . import __version__
from .anonymize import AlreadyProtectedError, anonymize_package
from .baseline import diff_findings, load_baseline_identities
from .config import Config, ConfigError, load_config
from .findings import Finding, Severity
from .fix import fix_package
from .loader import PackageNotFoundError
from .merge import merge_feeds
from .policy import GatingPolicy
from .report import (
    RENDERERS,
    render_batch_markdown,
    render_markdown,
    render_text,
    summarize,
)
from .rules import CATEGORIES, all_rules
from .runner import run
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


def _fail(message: str) -> NoReturn:
    click.echo(f"tods-validate: error: {message}", err=True)
    sys.exit(2)


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
) -> str:
    if output_format == "text":
        return render_text(findings, source, max_findings=max_findings, quiet=quiet)
    if output_format == "markdown":
        return render_markdown(findings, source, stamp=stamp)
    return RENDERERS[output_format](findings, source)


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
    type=click.Choice(["default", "strict", "lenient", "ingest-ready"]),
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
        "Text and Markdown output only."
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
    fail_on: str | None,
    ignore_ids: tuple[str, ...],
    enable_tokens: tuple[str, ...],
    profile: str | None,
    spec_version: str | None,
    baseline_path: str | None,
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
    config = _resolve_config(config_path)
    if profile is not None:
        from .config import PROFILES, _merge, _parse_data

        config = _merge(_parse_data(PROFILES[profile], f"profile {profile!r}"), config)

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
        except (OSError, json.JSONDecodeError) as exc:
            _fail(f"baseline {baseline_path} could not be read: {exc}")

    policy = GatingPolicy.from_config(
        fail_on=fail_on,
        config=config,
        ignore_ids=ignore_ids,
        baseline_identities=baseline_identities,
    )
    _check_rule_ids(tuple(policy.ignore))

    def _validate_once() -> list[Finding]:
        package, found = run(
            path, gtfs_path, enabled=frozenset(enable), encoding=effective_encoding
        )
        gate = policy.apply(found)
        click.echo(
            _render(
                output_format,
                gate.kept,
                package.source,
                max_findings=effective_max,
                quiet=quiet,
                stamp=stamp,
            )
        )
        if suggest and output_format in ("text", "markdown"):
            from .suggest import render_suggestions, suggest_for_findings

            click.echo("")
            click.echo(render_suggestions(suggest_for_findings(gate.kept, package), output_format))
        return gate.kept

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
            sys.exit(0)
        return

    try:
        findings = _validate_once()
    except PackageNotFoundError as exc:
        _fail(str(exc))
    _write_github_outputs(findings)

    # The exit code considers only findings new since the baseline, if given
    # (policy.apply already filtered `findings` for --ignore, so re-running it
    # here just applies the baseline narrowing on top of the same kept list).
    gate = policy.apply(findings)
    sys.exit(1 if gate.failed else 0)


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
    """
    config = _resolve_config(config_path)
    policy = GatingPolicy.from_config(fail_on=fail_on, config=config, ignore_ids=ignore_ids)
    _check_rule_ids(tuple(policy.ignore))

    try:
        _, old_findings = run(old, gtfs_path)
        _, new_findings_list = run(new, gtfs_path)
    except PackageNotFoundError as exc:
        _fail(str(exc))

    old_kept = policy.apply(old_findings).kept
    new_kept = policy.apply(new_findings_list).kept
    result = diff_findings(old_kept, new_kept)
    click.echo(f"tods-validate diff: {old} -> {new}")
    click.echo(
        f"  fixed: {len(result.fixed)}, introduced: {len(result.introduced)}, "
        f"persisting: {len(result.persisting)}"
    )
    for finding in result.introduced:
        loc = finding.location()
        click.echo(
            f"  + {finding.rule_id} [{loc}] {finding.message}"
            if loc
            else f"  + {finding.rule_id} {finding.message}"
        )
    for rule_id, pointer, message in result.fixed:
        click.echo(f"  - {rule_id} [{pointer}] {message}")

    gate = policy.apply(result.introduced)
    sys.exit(1 if gate.failed else 0)


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
    stamp: bool,
    ignore_ids: tuple[str, ...],
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

    rows: list[dict[str, object]] = []
    any_failed = False
    for path in paths:
        try:
            package, findings = run(path, gtfs_path)
        except PackageNotFoundError as exc:
            rows.append({"source": path, "error": str(exc)})
            any_failed = True
            continue
        gate = policy.apply(findings)
        counts = gate.counts
        rows.append(
            {
                "source": package.source,
                "errors": counts.get(Severity.ERROR, 0),
                "warnings": counts.get(Severity.WARNING, 0),
                "infos": counts.get(Severity.INFO, 0),
                "status": "fail" if gate.failed else "pass",
            }
        )
        if gate.failed:
            any_failed = True

    if output_format == "json":
        click.echo(json.dumps({"feeds": rows}, indent=2))
    elif output_format == "markdown":
        click.echo(render_batch_markdown(rows, stamp=stamp))
    else:
        click.echo(f"{'errors':>7} {'warnings':>9} {'infos':>6}  source")
        for row in rows:
            if "error" in row:
                click.echo(f"{'-':>7} {'-':>9} {'-':>6}  {row['source']} ({row['error']})")
            else:
                click.echo(
                    f"{row['errors']:>7} {row['warnings']:>9} {row['infos']:>6}  {row['source']}"
                )
    sys.exit(1 if any_failed else 0)


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
    click.echo(f"tods-validate fix: {result.source}")
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
