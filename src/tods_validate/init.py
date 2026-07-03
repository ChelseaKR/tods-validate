"""Scaffold a starter TODS package that validates clean out of the box.

``tods-validate init DEST`` writes a small, working package instead of
leaving a new integrator to hand-build ten CSVs from the spec. Two things
make the result trustworthy rather than merely well-formed:

- Every TODS/supplement header is read from :data:`tods_validate.schema.TABLES`
  (``[f.name for f in spec.fields]``), never hand-typed, so a generated file
  can never drift from the schema this validator itself checks against.
- Row data is copied verbatim from ``examples/sample-feed/`` — the same
  fixture exercised elsewhere in the test suite — so the scaffold reuses a
  feed already known to validate clean instead of synthesizing plausible-
  looking rows that might not.

If the sample feed cannot be found (for example, a packaging layout that
does not ship it), each table falls back to a schema-accurate header with no
data rows: still structurally valid, since every TODS file is optional, but
not a worked example.
"""

from __future__ import annotations

from pathlib import Path

from . import __version__
from .config import DEFAULT_FILENAME
from .schema import TABLES


class DestinationNotEmptyError(Exception):
    """``dest`` already holds files and ``force`` was not given."""


# Repo layout in a source checkout: src/tods_validate/init.py -> ../../examples.
# Not present in every install (e.g. a wheel that does not bundle `examples/`);
# callers see the headers-only fallback in that case, not an error.
_SAMPLE_FEED_DIR = Path(__file__).resolve().parents[2] / "examples" / "sample-feed"

# GTFS base files with no FieldSpec definition of their own in schema.py (this
# validator does not re-validate GTFS semantics) but that the sample TODS
# files reference and need present for a clean, reference-complete result.
# calendar_dates.txt is deliberately omitted: the sample feed's only
# calendar_dates row lives in calendar_dates_supplement.txt and needs no GTFS
# base row to merge against (a supplement row with no matching base row is
# simply added).
GTFS_BASE_FILES: tuple[str, ...] = (
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
)

# TODS-native and supplement files per shape. Every name here is a key into
# schema.TABLES, so its header is always schema-derived (see table_header()).
_RUN_TABLES: tuple[str, ...] = (
    "run_events.txt",
    "employee_run_dates.txt",
    "trips_supplement.txt",
    "stops_supplement.txt",
    "stop_times_supplement.txt",
    "routes_supplement.txt",
    "calendar_supplement.txt",
    "calendar_dates_supplement.txt",
)
_VEHICLE_TABLES: tuple[str, ...] = ("vehicles.txt", "vehicle_assignments.txt")

# Public: the shapes `init --shape` accepts, and which schema.TABLES files
# each one writes.
SHAPES: dict[str, tuple[str, ...]] = {
    "runs": _RUN_TABLES,
    "runs+vehicles": _RUN_TABLES + _VEHICLE_TABLES,
}


def table_header(filename: str) -> list[str]:
    """The header row schema.py defines for ``filename`` (the drift guard)."""
    return [f.name for f in TABLES[filename].fields]


def _write_table(dest: Path, filename: str) -> Path:
    """Write one schema.TABLES file: sample data if available, else headers only."""
    target = dest / filename
    sample = _SAMPLE_FEED_DIR / filename
    if sample.is_file():
        target.write_bytes(sample.read_bytes())
    else:
        target.write_text(",".join(table_header(filename)) + "\n", encoding="utf-8")
    return target


def _write_gtfs_base(dest: Path, filename: str) -> Path | None:
    """Copy one GTFS companion file verbatim from the sample feed, if present."""
    sample = _SAMPLE_FEED_DIR / filename
    if not sample.is_file():
        return None
    target = dest / filename
    target.write_bytes(sample.read_bytes())
    return target


_CONFIG_TEMPLATE = """\
# Written by `tods-validate init`. Command-line flags still take precedence
# over this file; run `tods-validate rules` for what --enable/--ignore can
# name, or see the README's config section for the full key list.
fail-on = "error"
"""


def _write_config(dest: Path) -> Path:
    target = dest / DEFAULT_FILENAME
    target.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
    return target


_WORKFLOW_TEMPLATE = """\
name: tods-validate
on:
  pull_request:
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ChelseaKR/tods-validate@{action_ref}
        with:
          path: .
"""


def _write_workflow(dest: Path) -> Path:
    workflow_dir = dest / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    target = workflow_dir / "tods-validate.yml"
    # Pin to the installed release, not @main, so the generated workflow never
    # silently picks up an unreviewed Action change (this is exactly the skew
    # docs/RESEARCH-ROADMAP.md's R5 had to fix by hand for README's examples).
    action_ref = "main" if "+" in __version__ else f"v{__version__}"
    target.write_text(_WORKFLOW_TEMPLATE.format(action_ref=action_ref), encoding="utf-8")
    return target


def scaffold(dest: Path, shape: str = "runs", *, force: bool = False) -> list[Path]:
    """Write a starter TODS package to ``dest``; return the paths written, sorted.

    ``shape`` selects which TODS files to include: ``"runs"`` (run_events.txt,
    employee_run_dates.txt, the supplements they reference, and the GTFS base
    files those need for a reference-complete result) or ``"runs+vehicles"``
    (adds vehicles.txt and vehicle_assignments.txt). Also writes a minimal
    ``tods-validate.toml`` and a ``.github/workflows/tods-validate.yml`` stub.

    Refuses to write into a ``dest`` that already exists and is non-empty
    unless ``force`` is true.
    """
    if shape not in SHAPES:
        raise ValueError(f"unknown shape {shape!r}; choose from {sorted(SHAPES)}.")

    dest = Path(dest)
    if dest.is_file():
        raise DestinationNotEmptyError(f"{dest} is an existing file, not a directory.")
    if dest.is_dir() and any(dest.iterdir()) and not force:
        raise DestinationNotEmptyError(
            f"{dest} already exists and is not empty. Pass --force to scaffold into it anyway."
        )
    dest.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for filename in GTFS_BASE_FILES:
        path = _write_gtfs_base(dest, filename)
        if path is not None:
            written.append(path)
    for filename in SHAPES[shape]:
        written.append(_write_table(dest, filename))
    written.append(_write_config(dest))
    written.append(_write_workflow(dest))
    return sorted(written)


__all__ = [
    "GTFS_BASE_FILES",
    "SHAPES",
    "DestinationNotEmptyError",
    "scaffold",
    "table_header",
]
