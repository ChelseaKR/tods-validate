"""Structured finding parameters (Finding.data), end to end.

These pin the acceptance bar from FIX-05: every ERROR-band finding carries
`data`, a dashboard-style consumer can read the offending value and any
referenced ID straight out of `data` with no message-string parsing, and
SARIF results carry the same structured context.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from conftest import FIXTURES, rule_ids
from tods_validate.cli import main
from tods_validate.findings import Finding, Severity
from tods_validate.report import render_sarif
from tods_validate.rules import CATEGORIES, all_rules
from tods_validate.runner import run

_ALL_CATEGORIES = frozenset(set(CATEGORIES))
_INVALID_FIXTURES = sorted(p.name for p in (FIXTURES / "invalid").iterdir() if p.is_dir())


def test_dashboard_reads_reference_finding_without_parsing_the_message() -> None:
    """A JSON consumer gets the offending value and referenced ID from `data` alone.

    TODS-E307's fixture references a trip_id that does not exist in the
    companion GTFS; this only inspects `finding["data"]`, never
    `finding["message"]`, to prove no message parsing is needed.
    """
    result = CliRunner().invoke(
        main,
        ["validate", str(FIXTURES / "invalid" / "TODS-E307"), "--format", "json"],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    findings = [f for f in payload["findings"] if f["rule_id"] == "TODS-E307"]
    assert len(findings) == 1
    data = findings[0]["data"]
    assert data is not None
    assert data["value"] == "ghost-trip"
    assert data["referenced"] == "trips.trip_id"


def test_every_error_finding_across_the_corpus_carries_data() -> None:
    """Every ERROR-severity finding, from every rule's dedicated fixture, has data.

    This is the "excellent looks like" bar from FIX-05: it is impossible to
    produce an ERROR finding with no structured context.
    """
    missing: list[str] = []
    for fixture_id in _INVALID_FIXTURES:
        _, findings = run(FIXTURES / "invalid" / fixture_id, enabled=_ALL_CATEGORIES)
        for f in findings:
            if f.severity is Severity.ERROR and (f.data is None or len(f.data) == 0):
                missing.append(f"{fixture_id}: {f.rule_id} has no data")
    assert not missing, "\n".join(missing)


def test_every_error_rule_is_exercised_by_the_corpus() -> None:
    """Sanity check that the sweep above actually visits every ERROR rule."""
    seen: set[str] = set()
    for fixture_id in _INVALID_FIXTURES:
        _, findings = run(FIXTURES / "invalid" / fixture_id, enabled=_ALL_CATEGORIES)
        seen |= rule_ids(findings)
    error_rules = {r.id for r in all_rules() if r.severity is Severity.ERROR}
    assert error_rules <= seen


def test_sarif_results_carry_structured_data_properties() -> None:
    finding = Finding(
        rule_id="TODS-E307",
        severity=Severity.ERROR,
        file="run_events.txt",
        row=5,
        field="trip_id",
        message="run_events.txt row 5: trip_id 'ghost-trip' does not exist.",
        data={"value": "ghost-trip", "referenced": "trips.trip_id"},
    )
    sarif = json.loads(render_sarif([finding], "feed/"))
    result = sarif["runs"][0]["results"][0]
    assert result["properties"]["value"] == "ghost-trip"
    assert result["properties"]["referenced"] == "trips.trip_id"
    assert result["properties"]["field"] == "trip_id"


def test_sarif_rule_descriptors_are_enriched() -> None:
    finding = Finding(
        rule_id="TODS-E307",
        severity=Severity.ERROR,
        file="run_events.txt",
        row=5,
        message="m",
        data={"value": "ghost-trip", "referenced": "trips.trip_id"},
    )
    sarif = json.loads(render_sarif([finding], "feed/"))
    descriptor = sarif["runs"][0]["tool"]["driver"]["rules"][0]
    assert descriptor["id"] == "TODS-E307"
    assert descriptor["shortDescription"]["text"]
    assert descriptor["fullDescription"]["text"]
    assert descriptor["helpUri"].startswith("https://")


def test_suggest_json_yields_structured_suggestions_array() -> None:
    """``--suggest -f json`` adds a machine-form ``suggestions`` array."""
    result = CliRunner().invoke(
        main,
        [
            "validate",
            str(FIXTURES / "invalid" / "TODS-W206"),
            "--suggest",
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.output)
    assert "suggestions" in payload
    trims = [s for s in payload["suggestions"] if s["rule_id"] == "TODS-W206"]
    assert len(trims) == 1
    assert trims[0]["kind"] == "auto"
    assert trims[0]["current"] == "bus-1 "
    assert trims[0]["proposed"] == "bus-1"


def test_suggest_without_flag_omits_suggestions_key() -> None:
    """The additive `suggestions` key is only present when `--suggest` is used."""
    result = CliRunner().invoke(
        main,
        ["validate", str(FIXTURES / "invalid" / "TODS-W206"), "--format", "json"],
    )
    payload = json.loads(result.output)
    assert "suggestions" not in payload
