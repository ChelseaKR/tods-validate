"""Accessible, opt-in run timelines in the standalone HTML report."""

from click.testing import CliRunner

from conftest import VALID_TODS
from tods_validate.cli import main
from tods_validate.findings import Finding, Severity
from tods_validate.loader import load_package
from tods_validate.report import render_html


def test_timeline_has_decorative_svg_and_equivalent_event_table() -> None:
    package = load_package(VALID_TODS)
    finding = Finding(
        rule_id="TODS-E401",
        severity=Severity.ERROR,
        file="run_events.txt",
        row=4,
        message="The event ends before it starts.",
    )

    out = render_html([finding], "feed/", timeline_package=package)

    assert "<h2 id='timelines-heading'>Run timelines</h2>" in out
    assert "Service daily · run 10000 — 9 events, 1 finding" in out
    assert "class='timeline-chart' aria-hidden='true' focusable='false'" in out
    assert "role='img'" not in out
    assert "aria-label='Scrollable visual run timeline'" in out
    assert "aria-label='Scrollable event table'" in out
    assert "stroke-dasharray:5 3" in out
    assert "class='issue-marker'" in out
    assert "◆" in out

    # The table, not the decorative SVG, is the screen-reader contract.
    assert "This table is the text equivalent of the visual timeline." in out
    assert "<th scope='col'>Sequence</th>" in out
    assert "<th scope='col'>Findings on row</th>" in out
    assert "ERROR TODS-E401" in out
    assert "garage → stop-1" in out


def test_timeline_is_opt_in_and_cli_rejects_other_formats() -> None:
    runner = CliRunner()

    plain = runner.invoke(main, [str(VALID_TODS), "--format", "html"])
    assert plain.exit_code == 0, plain.output
    assert "Run timelines" not in plain.output

    timeline = runner.invoke(main, [str(VALID_TODS), "--format", "html", "--timeline"])
    assert timeline.exit_code == 0, timeline.output
    assert "Run timelines" in timeline.output
    assert "Service daily · run 10000" in timeline.output

    invalid = runner.invoke(main, [str(VALID_TODS), "--timeline"])
    assert invalid.exit_code == 2
    assert "--timeline requires --format html" in invalid.output


def test_timeline_discloses_unsupported_v1_shape() -> None:
    package = load_package(VALID_TODS)
    out = render_html([], "feed/", spec_version="1.0.0", timeline_package=package)
    assert "Timelines are not available for TODS v1.0.0" in out


def test_timeline_escapes_feed_values() -> None:
    package = load_package(VALID_TODS)
    feed = package.get("run_events.txt")
    assert feed is not None  # noqa: S101 - narrows the fixture type for this test
    feed.rows[0].values["event_type"] = "<script>alert(1)</script>"

    out = render_html([], "feed/", timeline_package=package)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_timeline_graphic_colors_have_non_color_redundancy() -> None:
    out = render_html([], "feed/", timeline_package=load_package(VALID_TODS))
    assert ".event-bar.has-finding" in out
    assert "stroke-dasharray:5 3" in out
    assert "A dashed bar and diamond mark an event row with findings." in out
    assert "@media (max-width:600px)" in out
