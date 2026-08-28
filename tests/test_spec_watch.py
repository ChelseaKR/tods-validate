"""The spec-watch drift detector: parsing, diffing, and rendering."""

import importlib.util
import sys
from pathlib import Path

import pytest

from tods_validate.schema import TABLES, FieldType, Presence

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "spec_watch.py"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "spec_watch"


def _load_spec_watch():
    spec = importlib.util.spec_from_file_location("spec_watch", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses' `from __future__ import annotations` resolution looks the
    # module up in sys.modules by name; register it first or field-type
    # resolution for the frozen dataclasses below crashes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def spec_watch():
    return _load_spec_watch()


def _full_scope(spec_watch):
    """A scope in which every in-scope table was read, i.e. a complete run."""
    return spec_watch.ComparisonScope(compared=spec_watch.in_scope_tables(), not_found=())


def test_in_sync_fixture_parses_to_the_four_tods_specific_tables(spec_watch) -> None:
    text = (_FIXTURES / "in_sync.md").read_text(encoding="utf-8")
    tables = spec_watch.parse_spec_tables(text)
    assert set(tables) == {
        "run_events.txt",
        "employee_run_dates.txt",
        "vehicles.txt",
        "vehicle_assignments.txt",
    }
    run_events = {f.name: f for f in tables["run_events.txt"].fields}
    assert run_events["event_sequence"].type is FieldType.NON_NEGATIVE_INTEGER
    assert run_events["event_sequence"].presence is Presence.REQUIRED
    assert run_events["start_mid_trip"].type is FieldType.ENUM
    assert run_events["start_mid_trip"].enum_values == ("", "0", "1", "2")

    vehicle_assignments = {f.name: f for f in tables["vehicle_assignments.txt"].fields}
    assert vehicle_assignments["service_id"].presence is Presence.CONDITIONAL


def test_in_sync_fixture_produces_zero_drift_against_schema(spec_watch) -> None:
    text = (_FIXTURES / "in_sync.md").read_text(encoding="utf-8")
    tables = spec_watch.parse_spec_tables(text)
    diffs = spec_watch.diff_tables(tables)
    assert diffs == []


def test_in_sync_fixture_covers_every_field_of_the_four_tods_specific_tables() -> None:
    # Guards the fixture itself against silently going stale relative to
    # schema.py (e.g. a new field added to TABLES but not to the fixture,
    # which parse+diff alone wouldn't catch since a missing spec table is
    # simply skipped).
    watch = _load_spec_watch()
    text = (_FIXTURES / "in_sync.md").read_text(encoding="utf-8")
    tables = watch.parse_spec_tables(text)
    names = ("run_events.txt", "employee_run_dates.txt", "vehicles.txt", "vehicle_assignments.txt")
    for name in names:
        assert {f.name for f in tables[name].fields} == {f.name for f in TABLES[name].fields}


def test_drifted_fixture_is_detected_as_a_single_presence_change(spec_watch) -> None:
    text = (_FIXTURES / "drifted.md").read_text(encoding="utf-8")
    tables = spec_watch.parse_spec_tables(text)
    diffs = spec_watch.diff_tables(tables)
    assert len(diffs) == 1
    (diff,) = diffs
    assert diff.kind == "changed"
    assert diff.table == "vehicles.txt"
    assert diff.field == "vehicle_label"
    assert "presence" in diff.detail
    assert "Optional" in diff.detail
    assert "Required" in diff.detail


def test_drifted_fixture_renders_as_a_human_readable_diff(spec_watch) -> None:
    text = (_FIXTURES / "drifted.md").read_text(encoding="utf-8")
    tables = spec_watch.parse_spec_tables(text)
    diffs = spec_watch.diff_tables(tables)
    scope = spec_watch.comparison_scope(tables)
    rendered = spec_watch.render_diff(diffs, "markdown", scope)
    assert "vehicles.txt" in rendered
    assert "vehicle_label" in rendered
    assert "changed" in rendered

    text_rendered = spec_watch.render_diff(diffs, "text", scope)
    assert "vehicle_label" in text_rendered


def test_render_diff_reports_in_sync_when_empty(spec_watch) -> None:
    everything = _full_scope(spec_watch)
    assert "in sync" in spec_watch.render_diff([], "text", everything)
    assert "No drift" in spec_watch.render_diff([], "markdown", everything)


def test_added_and_removed_fields_are_both_reported(spec_watch) -> None:
    from tods_validate.schema import FieldSpec

    spec_table = spec_watch.SpecTable(
        name="vehicles.txt",
        fields=(
            FieldSpec("vehicle_id", FieldType.ID, Presence.REQUIRED),
            # license_plate removed relative to schema.py; new_field added.
            FieldSpec("new_field", FieldType.TEXT, Presence.OPTIONAL),
            FieldSpec("vehicle_label", FieldType.TEXT, Presence.OPTIONAL),
        ),
    )
    diffs = spec_watch.diff_tables({"vehicles.txt": spec_table})
    kinds = {(d.kind, d.field) for d in diffs}
    assert ("added", "new_field") in kinds
    assert ("removed", "license_plate") in kinds


def test_unknown_table_in_spec_is_reported_as_added(spec_watch) -> None:
    from tods_validate.schema import FieldSpec

    spec_table = spec_watch.SpecTable(
        name="a_brand_new_table.txt",
        fields=(FieldSpec("some_id", FieldType.ID, Presence.REQUIRED),),
    )
    diffs = spec_watch.diff_tables({"a_brand_new_table.txt": spec_table})
    assert len(diffs) == 1
    assert diffs[0].kind == "added"
    assert diffs[0].table == "a_brand_new_table.txt"
    assert diffs[0].field == "*"


def test_main_exits_zero_on_in_sync_fixture(spec_watch, capsys) -> None:
    code = spec_watch.main(["--spec-file", str(_FIXTURES / "in_sync.md")])
    assert code == spec_watch.EXIT_OK
    out = capsys.readouterr().out
    assert "in sync" in out


def test_main_exits_nonzero_on_drifted_fixture(spec_watch, capsys) -> None:
    code = spec_watch.main(["--spec-file", str(_FIXTURES / "drifted.md"), "--format", "markdown"])
    assert code == spec_watch.EXIT_DRIFT
    out = capsys.readouterr().out
    assert "vehicle_label" in out
    assert "# Spec drift detected" in out


def test_main_exits_advisory_code_when_spec_file_missing(spec_watch, capsys, tmp_path) -> None:
    code = spec_watch.main(["--spec-file", str(tmp_path / "does-not-exist.md")])
    assert code == spec_watch.EXIT_ADVISORY
    err = capsys.readouterr().err
    assert "could not" in err.lower()


def test_fetch_rejects_non_upstream_urls(spec_watch) -> None:
    with pytest.raises(spec_watch.SpecFetchError):
        spec_watch.fetch_spec_text(None, "file:///etc/passwd")


def test_normalize_type_handles_prose_and_annotations(spec_watch) -> None:
    assert spec_watch._normalize_type("ID referencing `calendar.service_id`") is FieldType.ID
    assert spec_watch._normalize_type("ID, primary key") is FieldType.ID
    assert spec_watch._normalize_type("Non-negative integer") is FieldType.NON_NEGATIVE_INTEGER
    assert spec_watch._normalize_type("Text") is FieldType.TEXT
    assert spec_watch._normalize_type("Enum") is FieldType.ENUM
    assert spec_watch._normalize_type("Time") is FieldType.TIME
    assert spec_watch._normalize_type("Date") is FieldType.DATE
    with pytest.raises(spec_watch.SpecParseError):
        spec_watch._normalize_type("Something else entirely")


def test_normalize_presence(spec_watch) -> None:
    assert spec_watch._normalize_presence("Required") is Presence.REQUIRED
    assert spec_watch._normalize_presence("Optional") is Presence.OPTIONAL
    assert (
        spec_watch._normalize_presence(
            "Optional",
            "Required if `block_id`s are repeated between different `service_id`s.",
        )
        is Presence.CONDITIONAL
    )
    assert spec_watch._normalize_presence("Conditionally required") is Presence.CONDITIONAL
    with pytest.raises(spec_watch.SpecParseError):
        spec_watch._normalize_presence("Sometimes")


# ---------------------------------------------------------------------------
# The tripwire has to be able to say what it compared.
#
# Until these existed, a document this script did not understand produced zero
# tables, zero diffs, and "schema.py is in sync with the upstream spec." at
# exit 0 -- byte-identical to a real clean run. Upstream restructuring its
# headings, renaming the Type/Required columns, or the raw URL serving any
# other 200 all landed there, and the weekly workflow greps stdout for drift,
# so nothing anywhere would have said the check had stopped working.
# ---------------------------------------------------------------------------


def test_a_document_with_no_field_tables_is_a_parse_error_not_a_clean_run(spec_watch) -> None:
    with pytest.raises(spec_watch.SpecParseError) as raised:
        spec_watch.parse_spec_tables("# Some other document\n\nNo field tables here.\n")
    assert "no `### `filename.txt`` field tables" in str(raised.value)


def test_main_refuses_to_report_sync_for_a_document_it_did_not_understand(
    spec_watch, capsys, tmp_path
) -> None:
    not_the_spec = tmp_path / "not-the-spec.md"
    not_the_spec.write_text("# Release notes\n\nNothing to see.\n", encoding="utf-8")

    code = spec_watch.main(["--spec-file", str(not_the_spec)])

    assert code == spec_watch.EXIT_ADVISORY
    captured = capsys.readouterr()
    assert "in sync" not in captured.out
    assert spec_watch.INCOMPLETE_HEADING.lower() in captured.out.lower()


def test_the_workflow_has_an_issue_body_to_post_when_the_comparison_fails(
    spec_watch, capsys, tmp_path
) -> None:
    """spec-watch.yml greps stdout for a heading; an empty stdout opens nothing."""
    not_the_spec = tmp_path / "not-the-spec.md"
    not_the_spec.write_text("# Release notes\n\nNothing to see.\n", encoding="utf-8")

    spec_watch.main(["--spec-file", str(not_the_spec), "--format", "markdown"])

    out = capsys.readouterr().out
    assert f"# {spec_watch.INCOMPLETE_HEADING}" in out
    assert "was **not** checked" in out


def _in_sync_missing_one_table(tmp_path: Path) -> Path:
    """The in-sync fixture with `vehicles.txt`'s heading renamed.

    Stands in for the realistic partial-parse failure: upstream reorganises one
    section, or the parser stops recognising it, and the other three tables
    still match.
    """
    text = (_FIXTURES / "in_sync.md").read_text(encoding="utf-8")
    assert "### `vehicles.txt`" in text
    partial = tmp_path / "partial.md"
    partial.write_text(text.replace("### `vehicles.txt`", "### Vehicles"), encoding="utf-8")
    return partial


def test_a_table_the_parser_missed_is_named_rather_than_counted_as_matching(
    spec_watch, tmp_path
) -> None:
    tables = spec_watch.parse_spec_tables(
        _in_sync_missing_one_table(tmp_path).read_text(encoding="utf-8")
    )
    scope = spec_watch.comparison_scope(tables)
    assert scope.not_found == ("vehicles.txt",)
    assert "vehicles.txt" not in scope.compared
    assert set(scope.compared) == {
        "employee_run_dates.txt",
        "run_events.txt",
        "vehicle_assignments.txt",
    }


def test_a_partial_comparison_never_renders_as_in_sync(spec_watch, tmp_path) -> None:
    tables = spec_watch.parse_spec_tables(
        _in_sync_missing_one_table(tmp_path).read_text(encoding="utf-8")
    )
    scope = spec_watch.comparison_scope(tables)
    diffs = spec_watch.diff_tables(tables)
    assert diffs == []  # everything that WAS compared matched

    for fmt in ("text", "markdown"):
        rendered = spec_watch.render_diff(diffs, fmt, scope)
        assert "in sync" not in rendered
        assert "No drift" not in rendered
        assert "vehicles.txt" in rendered


def test_a_partial_comparison_exits_advisory_not_ok(spec_watch, capsys, tmp_path) -> None:
    code = spec_watch.main(["--spec-file", str(_in_sync_missing_one_table(tmp_path))])
    assert code == spec_watch.EXIT_ADVISORY
    captured = capsys.readouterr()
    assert "in sync" not in captured.out
    assert "vehicles.txt" in captured.err


def test_a_complete_in_sync_run_still_says_so_and_names_its_scope(spec_watch, capsys) -> None:
    """The positive control: a real, complete comparison is unchanged, and now
    says which tables it read."""
    code = spec_watch.main(["--spec-file", str(_FIXTURES / "in_sync.md")])
    assert code == spec_watch.EXIT_OK
    out = capsys.readouterr().out
    assert "in sync" in out
    assert "Compared 4 of 4 in-scope table(s)" in out
    for name in spec_watch.in_scope_tables():
        assert name in out


def test_in_scope_tables_excludes_the_supplement_files(spec_watch) -> None:
    scoped = spec_watch.in_scope_tables()
    assert scoped == (
        "employee_run_dates.txt",
        "run_events.txt",
        "vehicle_assignments.txt",
        "vehicles.txt",
    )
    assert set(scoped) <= set(TABLES)
    assert not any(name.endswith("_supplement.txt") for name in scoped)
