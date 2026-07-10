"""--spec-version 1.0.0 vs the default 2.1.0: schema selection and rule gating.

See docs/spec-versions.md for the file/field deltas these fixtures exercise
and the citations behind the v1.0.0 schema in tods_validate.schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import FIXTURES
from tods_validate.api import validate_feed
from tods_validate.rules import STATUS_SKIPPED_SPEC_VERSION, all_rules
from tods_validate.runner import run, run_with_coverage
from tods_validate.schema import (
    SPEC_VERSION,
    SPEC_VERSION_V1,
    TABLES,
    TABLES_V1,
    spec_link,
)

V1_FIXTURES = FIXTURES / "spec_v1"


def test_v1_schema_has_five_files_no_supplements() -> None:
    # Spec (v1.0.0): "Dataset Files" table lists exactly these five files;
    # v1.0.0 predates the Supplement-file mechanism entirely.
    assert set(TABLES_V1) == {
        "deadheads.txt",
        "ops_locations.txt",
        "deadhead_times.txt",
        "runs_pieces.txt",
        "run_events.txt",
    }
    assert all(t.kind == "tods" for t in TABLES_V1.values())


def test_v1_run_events_differs_from_v2_run_events() -> None:
    # Same filename, different spec version, different fields -- the whole
    # point of --spec-version. v1 has no service_id/run_id/event_sequence.
    v1_fields = {f.name for f in TABLES_V1["run_events.txt"].fields}
    v2_fields = {f.name for f in TABLES["run_events.txt"].fields}
    assert v1_fields.isdisjoint({"service_id", "run_id", "event_sequence"})
    assert v2_fields >= {"service_id", "run_id", "event_sequence"}
    assert v1_fields != v2_fields


def test_v1_spec_link_uses_the_historical_commit() -> None:
    link = spec_link(TABLES_V1["deadheads.txt"])
    assert link.startswith(
        "https://github.com/MobilityData/transit-operational-data-standard/blob/"
    )
    assert link.endswith("#deadheadstxt")


def test_v1_valid_feed_is_clean() -> None:
    _, findings = run(V1_FIXTURES / "valid", spec_version=SPEC_VERSION_V1)
    assert findings == []


def test_v1_missing_required_value_is_e201() -> None:
    _, findings = run(V1_FIXTURES / "invalid_missing_required", spec_version=SPEC_VERSION_V1)
    assert [f.rule_id for f in findings] == ["TODS-E201"]
    assert findings[0].field == "event_time"


def test_v1_duplicate_piece_id_is_e204() -> None:
    # runs_pieces.txt is the one v1.0.0 file whose field description states a
    # uniqueness constraint in prose ("The piece_id field must be unique.").
    _, findings = run(V1_FIXTURES / "invalid_duplicate_piece", spec_version=SPEC_VERSION_V1)
    assert [f.rule_id for f in findings] == ["TODS-E204"]


def test_v1_invalid_enum_is_e202() -> None:
    _, findings = run(V1_FIXTURES / "invalid_enum", spec_version=SPEC_VERSION_V1)
    assert [f.rule_id for f in findings] == ["TODS-E202"]
    assert findings[0].field == "start_type"


def test_v1_bad_time_is_e203() -> None:
    _, findings = run(V1_FIXTURES / "invalid_bad_time", spec_version=SPEC_VERSION_V1)
    assert [f.rule_id for f in findings] == ["TODS-E203"]


def test_v1_feed_under_default_version_is_not_recognized() -> None:
    # The same valid v1.0.0 feed, read against the default (2.1.0) schema:
    # deadheads.txt/ops_locations.txt/deadhead_times.txt/runs_pieces.txt are
    # not v2.1.0 files at all (TODS-I102), and run_events.txt exists in both
    # versions but with a different, incompatible field set, so it fails
    # v2.1.0's required-column check instead of validating clean.
    _, findings = run(V1_FIXTURES / "valid")
    rule_ids = {f.rule_id for f in findings}
    assert "TODS-I102" in rule_ids
    assert "TODS-E106" in rule_ids


def test_v2_only_rules_are_skipped_under_v1_with_a_clear_reason() -> None:
    _, findings, coverage = run_with_coverage(V1_FIXTURES / "valid", spec_version=SPEC_VERSION_V1)
    skipped_ids = {o.id for o in coverage.outcomes if o.status == STATUS_SKIPPED_SPEC_VERSION}
    # A representative rule from each of the three v2-only modules.
    assert {"TODS-E301", "TODS-E401", "TODS-I501"} <= skipped_ids
    assert coverage.summary_line() is not None
    assert "not defined by the requested --spec-version" in coverage.summary_line()


def test_v2_only_rules_still_run_by_default() -> None:
    # Sanity check that spec_versions gating does not affect the default
    # (2.1.0) run: every registered rule with spec_versions=None or
    # containing SPEC_VERSION is eligible to run (subject to its other gates,
    # e.g. needs_gtfs/default_enabled), never skipped for spec_version alone.
    _, _, coverage = run_with_coverage(FIXTURES / "valid" / "tods", FIXTURES / "valid" / "gtfs")
    assert not any(o.status == STATUS_SKIPPED_SPEC_VERSION for o in coverage.outcomes)


def test_every_rule_declares_a_supported_spec_version_set() -> None:
    for r in all_rules():
        if r.spec_versions is not None:
            assert set(r.spec_versions) <= {SPEC_VERSION_V1, SPEC_VERSION}


def test_json_report_discloses_the_validated_spec_version() -> None:
    result = validate_feed(V1_FIXTURES / "valid", spec_version=SPEC_VERSION_V1)
    assert result.ok
    # validate_feed returns findings, not the rendered report; assert the
    # renderer honors spec_version too (report.py's specVersion field).
    from tods_validate.report import render_json

    payload = json.loads(render_json(result.findings, "src", spec_version=SPEC_VERSION_V1))
    assert payload["specVersion"] == SPEC_VERSION_V1


def test_cli_reports_the_requested_spec_version(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from tods_validate.cli import main

    result = CliRunner().invoke(
        main,
        [
            "validate",
            str(V1_FIXTURES / "valid"),
            "--spec-version",
            SPEC_VERSION_V1,
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.output)
    assert payload["specVersion"] == SPEC_VERSION_V1
    assert result.exit_code == 0
