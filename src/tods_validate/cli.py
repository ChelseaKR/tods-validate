"""Command-line interface.

Exit codes: 0 when no findings at or above the --fail-on severity were found
(the default fails only on errors), 1 when there were, 2 when the package or
configuration could not be read at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

import click

from . import __version__
from .config import Config, ConfigError, load_config
from .findings import Severity
from .loader import PackageNotFoundError
from .merge import merge_feeds
from .report import RENDERERS, summarize
from .rules import all_rules
from .runner import run
from .schema import SPEC_VERSION


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
    help="Report format: human-readable text, JSON, Markdown, or GitHub annotations.",
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
    config_path: str | None,
) -> None:
    """Validate the TODS feed at PATH.

    PATH is a directory or .zip file containing the TODS .txt files, with or
    without the GTFS feed alongside them.
    """
    config = _resolve_config(config_path)
    ignore = tuple(ignore_ids) + config.ignore
    _check_rule_ids(ignore)
    effective_fail_on = fail_on or config.fail_on or "error"

    try:
        package, findings = run(path, gtfs_path)
    except PackageNotFoundError as exc:
        _fail(str(exc))

    if ignore:
        findings = [f for f in findings if f.rule_id not in ignore]

    click.echo(RENDERERS[output_format](findings, package.source))

    counts = summarize(findings)
    failed = counts[Severity.ERROR] > 0 or (
        effective_fail_on == "warning" and counts[Severity.WARNING] > 0
    )
    sys.exit(1 if failed else 0)


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
def merge(path: str, gtfs_path: str | None, output_path: str) -> None:
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

    for name, stats in sorted(result.stats.items()):
        details = []
        if stats.updated:
            details.append(f"{stats.updated} row(s) updated")
        if stats.added:
            details.append(f"{stats.added} added")
        if stats.deleted:
            details.append(f"{stats.deleted} deleted")
        if stats.skipped:
            details.append(f"{stats.skipped} skipped (blank primary key)")
        click.echo(f"{name}: {', '.join(details) if details else 'no changes'}")
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
            }
            for r in rules
        ]
        click.echo(json.dumps(payload, indent=2))
        return
    for r in rules:
        needs = " (needs companion GTFS)" if r.needs_gtfs else ""
        click.echo(f"{r.id}  {r.severity.name:7}  {r.title}{needs}")


if __name__ == "__main__":
    main()
