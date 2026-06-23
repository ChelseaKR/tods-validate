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
from .anonymize import anonymize_package
from .baseline import diff_findings, load_baseline_identities, new_findings
from .config import Config, ConfigError, load_config
from .findings import Finding, Severity
from .loader import PackageNotFoundError
from .merge import merge_feeds
from .report import (
    RENDERERS,
    render_markdown,
    render_text,
    summarize,
)
from .rules import CATEGORIES, all_rules
from .runner import run
from .schema import SPEC_VERSION, SUPPORTED_SPEC_VERSIONS
from .stats import collect_stats, render_stats_markdown, render_stats_text, stats_to_dict


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
    type=click.Choice(["default", "strict", "lenient"]),
    default=None,
    help="Apply a named preset of settings (overridden by other flags).",
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
    "--stamp",
    is_flag=True,
    help="Add a provenance footer (version, timestamp) to Markdown for a citable report.",
)
@click.option(
    "--encoding", default=None, help="Override UTF-8 decoding for non-conforming exports."
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
def validate(
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
    stamp: bool,
    encoding: str | None,
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

    ignore = tuple(ignore_ids) + config.ignore
    enable = tuple(enable_tokens) + config.enable
    _check_rule_ids(ignore)
    _check_enable(enable)
    effective_fail_on = fail_on or config.fail_on or "error"
    effective_max = max_findings if max_findings is not None else config.max_findings
    effective_encoding = encoding or config.encoding
    effective_spec = spec_version or config.spec_version or SPEC_VERSION
    _check_spec_version(effective_spec)

    try:
        package, findings = run(
            path, gtfs_path, enabled=frozenset(enable), encoding=effective_encoding
        )
    except PackageNotFoundError as exc:
        _fail(str(exc))

    if ignore:
        findings = [f for f in findings if f.rule_id not in ignore]

    click.echo(
        _render(
            output_format,
            findings,
            package.source,
            max_findings=effective_max,
            quiet=quiet,
            stamp=stamp,
        )
    )
    _write_github_outputs(findings)

    # The exit code considers only findings new since the baseline, if given.
    gating = findings
    if baseline_path is not None:
        try:
            baseline = load_baseline_identities(baseline_path)
        except (OSError, json.JSONDecodeError) as exc:
            _fail(f"baseline {baseline_path} could not be read: {exc}")
        gating = new_findings(findings, baseline)

    counts = summarize(gating)
    failed = counts[Severity.ERROR] > 0 or (
        effective_fail_on == "warning" and counts[Severity.WARNING] > 0
    )
    sys.exit(1 if failed else 0)


@main.command()
@click.argument("old", type=click.Path(exists=False))
@click.argument("new", type=click.Path(exists=False))
@click.option("--gtfs", "gtfs_path", type=click.Path(exists=False), default=None)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default="error",
    show_default=True,
    help="Exit non-zero if newly introduced findings reach this severity.",
)
def diff(old: str, new: str, gtfs_path: str | None, fail_on: str) -> None:
    """Compare validation of two feeds: OLD then NEW.

    Reports which findings were fixed, newly introduced, or still present, so a
    change to a feed can be reviewed for regressions.
    """
    try:
        _, old_findings = run(old, gtfs_path)
        _, new_findings_list = run(new, gtfs_path)
    except PackageNotFoundError as exc:
        _fail(str(exc))

    result = diff_findings(old_findings, new_findings_list)
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

    introduced_counts = summarize(result.introduced)
    failed = introduced_counts[Severity.ERROR] > 0 or (
        fail_on == "warning" and introduced_counts[Severity.WARNING] > 0
    )
    sys.exit(1 if failed else 0)


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=False))
@click.option("--gtfs", "gtfs_path", type=click.Path(exists=False), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default="error",
    show_default=True,
)
def batch(paths: tuple[str, ...], gtfs_path: str | None, output_format: str, fail_on: str) -> None:
    """Validate several feeds and print a roll-up table.

    Each PATH is validated independently; the shared --gtfs companion, if given,
    is used for all of them.
    """
    rows: list[dict[str, object]] = []
    any_failed = False
    for path in paths:
        try:
            package, findings = run(path, gtfs_path)
        except PackageNotFoundError as exc:
            rows.append({"source": path, "error": str(exc)})
            any_failed = True
            continue
        counts = summarize(findings)
        rows.append(
            {
                "source": package.source,
                "errors": counts[Severity.ERROR],
                "warnings": counts[Severity.WARNING],
                "infos": counts[Severity.INFO],
            }
        )
        if counts[Severity.ERROR] > 0 or (fail_on == "warning" and counts[Severity.WARNING] > 0):
            any_failed = True

    if output_format == "json":
        click.echo(json.dumps({"feeds": rows}, indent=2))
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
@click.argument("path", type=click.Path(exists=False))
@click.option("--gtfs", "gtfs_path", type=click.Path(exists=False), default=None)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    show_default=True,
)
@click.option("--encoding", default=None)
def stats(path: str, gtfs_path: str | None, output_format: str, encoding: str | None) -> None:
    """Print descriptive statistics about a TODS feed (counts, not a score)."""
    try:
        feed_stats = collect_stats(path, gtfs_path, encoding)
    except PackageNotFoundError as exc:
        _fail(str(exc))
    if output_format == "json":
        click.echo(json.dumps(stats_to_dict(feed_stats), indent=2))
    elif output_format == "markdown":
        click.echo(render_stats_markdown(feed_stats))
    else:
        click.echo(render_stats_text(feed_stats))


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
def anonymize(path: str, output_path: str, salt: str | None, encoding: str | None) -> None:
    """Write a copy of the package with person-identifying fields pseudonymized.

    employee_id, license_plate, and vehicle_id are replaced with stable
    pseudonyms. This is pseudonymization, not guaranteed anonymity.
    """
    try:
        result = anonymize_package(path, Path(output_path), salt=salt, encoding=encoding)
    except PackageNotFoundError as exc:
        _fail(str(exc))
    for target, count in sorted(result.replacements.items()):
        click.echo(f"{target}: {count} value(s) pseudonymized")
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


if __name__ == "__main__":
    main()
