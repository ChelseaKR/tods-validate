"""Command-line interface.

Exit codes: 0 when no findings at or above the --fail-on severity were found
(the default fails only on errors), 1 when there were, 2 when the package or
configuration could not be read at all.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

import click

from . import __version__
from .config import Config, ConfigError, load_config
from .findings import Severity
from .loader import PackageNotFoundError
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


@click.command(name="tods-validate")
@click.version_option(__version__, message=f"%(prog)s %(version)s (TODS v{SPEC_VERSION})")
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
def main(
    path: str,
    gtfs_path: str | None,
    output_format: str,
    fail_on: str | None,
    ignore_ids: tuple[str, ...],
    config_path: str | None,
) -> None:
    """Validate a TODS (Transit Operational Data Standard) feed at PATH.

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


if __name__ == "__main__":
    main()
