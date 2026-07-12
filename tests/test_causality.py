"""Finding causality: TODS-E201 echoes of a TODS-E104 ragged row link back to it.

Uses a hand-built package in ``tmp_path`` rather than the shared conformance
corpus (``tests/fixtures/invalid/``) because every directory there must trip
exactly the rule it is named for (see ``test_conformance.py::
test_corpus_covers_every_rule``); this scenario deliberately trips two rules
on the same row.
"""

from pathlib import Path

from tods_validate.findings import Severity
from tods_validate.report import render_json, render_markdown, render_text
from tods_validate.runner import run

_HEADER = (
    "service_id,run_id,event_sequence,piece_id,block_id,job_type,event_type,"
    "trip_id,start_location,start_time,start_mid_trip,end_location,end_time,"
    "end_mid_trip"
)

# Only 10 of the 14 declared columns are given, so csv parsing leaves the
# trailing columns (start_mid_trip, end_location, end_time, end_mid_trip)
# missing from the row -- a genuine TODS-E104 (ragged row) that also starves
# two Required fields (end_location, end_time), independently tripping
# TODS-E201 twice on that same row.
_RAGGED_ROW = "daily,1,1,,,,depart,,garage,08:00:00"


def _write_ragged_package(tmp_path: Path) -> Path:
    feed_dir = tmp_path / "feed"
    feed_dir.mkdir()
    (feed_dir / "run_events.txt").write_text(f"{_HEADER}\n{_RAGGED_ROW}\n", encoding="utf-8")
    return feed_dir


def test_ragged_row_causes_e201_findings_with_caused_by(tmp_path: Path) -> None:
    _, findings = run(_write_ragged_package(tmp_path))

    roots = [f for f in findings if f.rule_id == "TODS-E104"]
    assert len(roots) == 1
    root_pointer = roots[0].pointer()
    assert root_pointer == "run_events.txt#L2"

    echoes = [f for f in findings if f.rule_id == "TODS-E201"]
    assert len(echoes) == 2  # end_location and end_time both starved
    assert all(f.caused_by == root_pointer for f in echoes)


def test_render_text_collapses_echoes_under_their_root(tmp_path: Path) -> None:
    _, findings = run(_write_ragged_package(tmp_path))
    text = render_text(findings, "feed/")

    # The echoes are not listed individually; only the by-rule breakdown at
    # the bottom (unaffected by collapsing) still names TODS-E201.
    assert "ERROR TODS-E201" not in text
    assert "By rule: TODS-E201" in text or "TODS-E201 ×2" in text
    assert "ERROR TODS-E104" in text
    assert "and 2 follow-on findings" in text
    # The severity header reflects what is actually listed (root only), not
    # the raw finding count (root + 2 echoes).
    assert "1 error:" in text


def test_render_json_keeps_every_finding_with_the_link(tmp_path: Path) -> None:
    import json

    _, findings = run(_write_ragged_package(tmp_path))
    payload = json.loads(render_json(findings, "feed/"))

    e201 = [f for f in payload["findings"] if f["rule_id"] == "TODS-E201"]
    assert len(e201) == 2  # nothing removed from the machine format
    assert all(f["caused_by"] == "run_events.txt#L2" for f in e201)

    e104 = [f for f in payload["findings"] if f["rule_id"] == "TODS-E104"]
    assert len(e104) == 1
    assert e104[0]["caused_by"] is None


def test_render_markdown_keeps_every_finding_and_shows_the_link(tmp_path: Path) -> None:
    _, findings = run(_write_ragged_package(tmp_path))
    md = render_markdown(findings, "feed/")

    assert md.count("**TODS-E201**") == 2  # nothing removed
    assert md.count("Caused by: run_events.txt#L2") == 2


def test_finding_silent_by_default_has_no_causal_link() -> None:
    """A finding not created by cascade linking has caused_by=None."""
    from tods_validate.findings import Finding

    f = Finding(rule_id="TODS-E999", severity=Severity.ERROR, message="unrelated")
    assert f.caused_by is None
    assert f.to_dict()["caused_by"] is None
