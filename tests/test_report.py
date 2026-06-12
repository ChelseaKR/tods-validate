"""Report rendering details not covered by the CLI tests."""

from tods_validate.findings import Finding, Severity
from tods_validate.report import render_github, render_text

FINDING = Finding(
    rule_id="TODS-E999",
    severity=Severity.ERROR,
    file="run_events.txt",
    row=7,
    field="trip_id",
    message="Line one.\nLine two with 100% certainty.",
    suggestion="Do the fix.",
)


def test_text_report_carries_severity_in_words_not_color() -> None:
    text = render_text([FINDING], "feed/")
    assert "ERROR TODS-E999" in text
    assert "\x1b[" not in text  # no ANSI escapes; readable when piped to a file
    assert "Fix: Do the fix." in text
    assert "Summary: 1 error(s), 0 warning(s), 0 info." in text


def test_text_report_groups_by_severity() -> None:
    warning = Finding(rule_id="TODS-W998", severity=Severity.WARNING, message="w")
    text = render_text([warning, FINDING], "feed/")
    assert text.index("1 error:") < text.index("1 warning:")


def test_github_annotations_escape_newlines_and_percent() -> None:
    out = render_github([FINDING], "feed/")
    first = out.splitlines()[0]
    assert first.startswith("::error file=run_events.txt,line=7,title=TODS-E999::")
    assert "%0A" in first  # newline escaped
    assert "100%25" in first  # percent escaped
    assert "\n" not in first
