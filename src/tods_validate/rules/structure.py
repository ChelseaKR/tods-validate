"""Package and file structure rules (TODS-x1xx)."""

from __future__ import annotations

from collections.abc import Iterator

from ..findings import Finding, Severity
from ..loader import BLOCKING_PROBLEM_CODES
from ..schema import GTFS_FILENAMES, SPEC_URL, Presence, spec_link
from . import ValidationContext, rule

_FILES_SECTION = f"{SPEC_URL}#files"


@rule(
    id="TODS-W101",
    severity=Severity.WARNING,
    title="No TODS files in package",
    description=(
        "The package contains none of the files defined by the TODS spec version being "
        "validated against. Every TODS file is optional, but a package with none of them "
        "has nothing to validate."
    ),
    spec_section=_FILES_SECTION,
)
def no_tods_files(context: ValidationContext) -> Iterator[Finding]:
    if not any(name in context.tables for name in context.package.files):
        yield Finding(
            rule_id="TODS-W101",
            severity=Severity.WARNING,
            message=(
                "No TODS files were found in this package. Expected at least one of: "
                + ", ".join(sorted(context.tables))
                + "."
            ),
            suggestion="Check that the TODS files are at the top level, not in a subfolder.",
            data={"expected": ",".join(sorted(context.tables))},
        )


@rule(
    id="TODS-I102",
    severity=Severity.INFO,
    title="File is not part of TODS or GTFS",
    description=(
        "A file in the package is neither a TODS file nor a standard GTFS file. It is "
        "ignored by this validator."
    ),
    spec_section=_FILES_SECTION,
)
def unknown_file(context: ValidationContext) -> Iterator[Finding]:
    for name in context.package.files:
        if name not in context.tables and name not in GTFS_FILENAMES:
            yield Finding(
                rule_id="TODS-I102",
                severity=Severity.INFO,
                file=name,
                message=(
                    f"{name} is not a TODS file and not a standard GTFS file; it was not validated."
                ),
                suggestion=(
                    "If this was meant to be a TODS file, check the spelling against the "
                    "file list in the spec."
                ),
                data={"value": name},
            )
    for name in context.package.unparsed:
        yield Finding(
            rule_id="TODS-I102",
            severity=Severity.INFO,
            file=name,
            message=f"{name} is not a CSV text file and was not validated.",
            data={"value": name},
        )


@rule(
    id="TODS-E103",
    severity=Severity.ERROR,
    title="File could not be read",
    description=(
        "A TODS file is empty, not UTF-8 encoded, or not parseable as CSV. The file's "
        "contents were not validated."
    ),
    spec_section=_FILES_SECTION,
)
def file_unreadable(context: ValidationContext) -> Iterator[Finding]:
    for name, feed in context.package.files.items():
        if name not in context.tables:
            continue
        for problem in feed.problems:
            if problem.code in BLOCKING_PROBLEM_CODES:
                yield Finding(
                    rule_id="TODS-E103",
                    severity=Severity.ERROR,
                    file=name,
                    row=problem.line,
                    message=problem.message,
                    data={"value": name, "code": problem.code},
                )


@rule(
    id="TODS-E104",
    severity=Severity.ERROR,
    title="Row has the wrong number of values",
    description=(
        "A row has more or fewer values than the file's header declares columns. "
        "Values after the mismatch may be attributed to the wrong field."
    ),
    spec_section=_FILES_SECTION,
    example=(
        "Before: header is `trip_id,stop_sequence,arrival_time` but a data row is "
        "`T-1,1,08:00,extra`. After: quote fields containing commas, or remove the "
        "stray trailing value so the row has exactly 3 fields."
    ),
)
def ragged_row(context: ValidationContext) -> Iterator[Finding]:
    for name, feed in context.package.files.items():
        if name not in context.tables:
            continue
        for problem in feed.problems:
            if problem.code == "ragged":
                yield Finding(
                    rule_id="TODS-E104",
                    severity=Severity.ERROR,
                    file=name,
                    row=problem.line,
                    message=problem.message,
                    suggestion=(
                        "Open the file in a text editor (not a spreadsheet) and check for "
                        "unquoted commas or missing trailing commas on this row."
                    ),
                    data={
                        "value": str(problem.actual),
                        "expected": str(problem.expected),
                    },
                )


@rule(
    id="TODS-E105",
    severity=Severity.ERROR,
    title="Duplicate column name",
    description="A column name appears more than once in a file's header row.",
    spec_section=_FILES_SECTION,
)
def duplicate_column(context: ValidationContext) -> Iterator[Finding]:
    for name, feed in context.package.files.items():
        if name not in context.tables:
            continue
        for problem in feed.problems:
            if problem.code == "duplicate_header":
                yield Finding(
                    rule_id="TODS-E105",
                    severity=Severity.ERROR,
                    file=name,
                    row=1,
                    field=problem.column,
                    message=problem.message,
                    data={"field": problem.column or ""},
                )


@rule(
    id="TODS-E106",
    severity=Severity.ERROR,
    title="Required column is missing",
    description=(
        "A TODS file does not declare a column the spec marks Required (for supplement "
        "files: a primary-key column of the GTFS file being supplemented). Rows cannot "
        "be interpreted without it."
    ),
    spec_section=SPEC_URL,
    example=(
        "Before: `stop_time_overrides.txt` header is `trip_id,stop_sequence`. After: "
        "add the required key column — `trip_id,stop_id,stop_sequence`."
    ),
)
def missing_required_column(context: ValidationContext) -> Iterator[Finding]:
    for name, table in context.tables.items():
        feed = context.package.get(name)
        if feed is None or not feed.headers:
            continue
        if table.kind == "supplement":
            required = table.primary_key or ()
            why = f"it is the primary key used to match rows against GTFS {table.gtfs_base}"
        else:
            required = tuple(f.name for f in table.fields if f.presence is Presence.REQUIRED)
            why = "the spec marks it Required"
        for column in required:
            if column not in feed.headers:
                yield Finding(
                    rule_id="TODS-E106",
                    severity=Severity.ERROR,
                    file=name,
                    row=1,
                    field=column,
                    message=(f"{name} is missing the required column {column!r} ({why})."),
                    suggestion=f"Add a {column!r} column. See {spec_link(table)}.",
                    data={"field": column},
                )


@rule(
    id="TODS-W107",
    severity=Severity.WARNING,
    title="Column is not defined by TODS",
    description=(
        "A TODS-specific file declares a column the spec does not define. Consumers "
        "will ignore it; it is often a misspelled field name."
    ),
    spec_section=SPEC_URL,
)
def unknown_column_tods(context: ValidationContext) -> Iterator[Finding]:
    for name, table in context.tables.items():
        if table.kind != "tods":
            continue
        feed = context.package.get(name)
        if feed is None:
            continue
        known = {f.name for f in table.fields}
        for column in feed.headers:
            if column and column not in known:
                yield Finding(
                    rule_id="TODS-W107",
                    severity=Severity.WARNING,
                    file=name,
                    row=1,
                    field=column,
                    message=(
                        f"{name} has a column {column!r} that is not defined in TODS "
                        f"{name.removesuffix('.txt')}. Consumers will ignore it."
                    ),
                    suggestion=(
                        "Check the spelling against the field list in the spec: "
                        f"{spec_link(table)}."
                    ),
                    data={"value": column, "field": column},
                )


@rule(
    id="TODS-I108",
    severity=Severity.INFO,
    title="Supplement column is not defined by GTFS or TODS",
    description=(
        "A supplement file declares a column that is neither a field of the GTFS file "
        "being supplemented nor a TODS_ field. It is carried through to the merged feed "
        "as a GTFS extension field."
    ),
    spec_section=f"{SPEC_URL}#supplement-files",
)
def unknown_column_supplement(context: ValidationContext) -> Iterator[Finding]:
    for name, table in context.tables.items():
        if table.kind != "supplement":
            continue
        feed = context.package.get(name)
        if feed is None:
            continue
        known = {f.name for f in table.fields}
        for column in feed.headers:
            # A TODS_-prefixed column is, by the naming convention itself, a
            # TODS-only extension field (see the rule's own description and
            # its worked example in rules/__init__.py's EXAMPLES, which fixes
            # an unknown column precisely by adding this prefix) -- it should
            # not be flagged as unrecognized just because it isn't literally
            # one of this table's declared fields.
            if column and column not in known and not column.startswith("TODS_"):
                yield Finding(
                    rule_id="TODS-I108",
                    severity=Severity.INFO,
                    file=name,
                    row=1,
                    field=column,
                    message=(
                        f"{name} has a column {column!r} that is not a GTFS "
                        f"{table.gtfs_base} field or a TODS_ field. It will be treated "
                        "as an extension field."
                    ),
                    data={"value": column, "field": column},
                )
