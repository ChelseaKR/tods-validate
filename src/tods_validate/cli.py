"""Command-line interface.

Exit codes: 0 when no errors were found (warnings and infos do not fail the
run unless --fail-on warning is set), 1 when errors were found, 2 when the
package could not be read at all.
"""

from __future__ import annotations

import sys

import click

from . import __version__
from .findings import Severity
from .loader import PackageNotFoundError
from .report import RENDERERS, summarize
from .runner import run
from .schema import SPEC_VERSION


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
    help="Report format: human-readable text, JSON, or GitHub Actions annotations.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["error", "warning"]),
    default="error",
    show_default=True,
    help="Exit non-zero if findings at or above this severity exist.",
)
def main(path: str, gtfs_path: str | None, output_format: str, fail_on: str) -> None:
    """Validate a TODS (Transit Operational Data Standard) feed at PATH.

    PATH is a directory or .zip file containing the TODS .txt files, with or
    without the GTFS feed alongside them.
    """
    try:
        package, findings = run(path, gtfs_path)
    except PackageNotFoundError as exc:
        click.echo(f"tods-validate: error: {exc}", err=True)
        sys.exit(2)

    click.echo(RENDERERS[output_format](findings, package.source))

    counts = summarize(findings)
    failed = counts[Severity.ERROR] > 0 or (fail_on == "warning" and counts[Severity.WARNING] > 0)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
