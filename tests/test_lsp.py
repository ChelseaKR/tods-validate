"""The language server: pure diagnostic mapping and the pygls wiring."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from lsprotocol import types as lsp
from pygls import uris

from tods_validate.api import ValidationResult, validate_feed
from tods_validate.cli import main
from tods_validate.findings import Finding, Severity
from tods_validate.lsp import (
    _disk_reader,
    _publish,
    _range_covers,
    build_code_actions,
    build_server,
    diagnostics_for_feed,
    feed_root_for,
    field_span,
    hover_markdown,
    revalidate,
)

FIXTURES = Path(__file__).parent / "fixtures"


# --- field_span ---------------------------------------------------------------


def test_field_span_basic_and_bounds() -> None:
    assert field_span("a,b,c", 0) == (0, 1)
    assert field_span("a,b,c", 1) == (2, 3)
    assert field_span("a,b,c", 2) == (4, 5)  # last field reaches end of line
    assert field_span("a,b,c", 3) is None  # past the last field


def test_field_span_honors_quoting_and_empties() -> None:
    assert field_span('x,"a,b",z', 1) == (2, 7)  # the comma inside quotes is not a split
    assert field_span('x,"a,b",z', 2) == (8, 9)
    assert field_span("", 0) == (0, 0)  # an empty line has one empty field
    assert field_span("a,,c", 1) == (2, 2)  # a blank middle field is a zero-width span


# --- feed_root_for ------------------------------------------------------------


def test_feed_root_for_file_and_dir(tmp_path: Path) -> None:
    (tmp_path / "run_events.txt").write_text("x")
    assert feed_root_for(tmp_path / "run_events.txt") == tmp_path
    assert feed_root_for(tmp_path) == tmp_path  # a directory is its own root


# --- diagnostics_for_feed -----------------------------------------------------


def _result(*findings: Finding) -> ValidationResult:
    return ValidationResult(source="test", findings=list(findings))


def test_diagnostics_map_field_to_column_and_carry_metadata() -> None:
    reader = {"run_events.txt": "service_id,event_type\nS1,bogus\n"}.get
    result = _result(
        Finding(
            rule_id="TODS-E202",
            severity=Severity.ERROR,
            message="bad value",
            file="run_events.txt",
            row=2,
            field="event_type",
            suggestion="use a known type",
        )
    )
    by_file, unanchored = diagnostics_for_feed(result, reader)
    assert not unanchored
    [diag] = by_file["run_events.txt"]
    assert diag.code == "TODS-E202"
    assert diag.source == "tods-validate"
    assert diag.severity == lsp.DiagnosticSeverity.Error
    assert "use a known type" in diag.message  # suggestion is appended
    # "bogus" sits at characters 3..8 of the second line (line index 1).
    assert diag.range.start == lsp.Position(1, 3)
    assert diag.range.end == lsp.Position(1, 8)


def test_diagnostics_anchor_whole_row_without_a_field() -> None:
    reader = {"vehicles.txt": "vehicle_id\nV1\n"}.get
    result = _result(
        Finding(
            rule_id="TODS-E1", severity=Severity.WARNING, message="m", file="vehicles.txt", row=2
        )
    )
    [diag] = diagnostics_for_feed(result, reader)[0]["vehicles.txt"]
    assert diag.range == lsp.Range(lsp.Position(1, 0), lsp.Position(1, 2))


def test_findings_without_a_readable_file_are_unanchored() -> None:
    result = _result(
        Finding(rule_id="A", severity=Severity.ERROR, message="no file"),  # file is None
        Finding(rule_id="B", severity=Severity.ERROR, message="missing", file="absent.txt", row=1),
    )
    by_file, unanchored = diagnostics_for_feed(result, lambda _name: None)
    assert by_file == {}
    assert {f.rule_id for f in unanchored} == {"A", "B"}


# --- the pygls server ---------------------------------------------------------


class _CapturingServer:
    """Stands in for the pygls publish surface to record what would be sent."""

    def __init__(self) -> None:
        self.diagnostics_by_uri: dict[str, list[lsp.Diagnostic]] = {}
        self.sent: list[lsp.PublishDiagnosticsParams] = []

    def text_document_publish_diagnostics(self, params: lsp.PublishDiagnosticsParams) -> None:
        self.sent.append(params)


def test_publish_clears_a_file_once_it_is_clean(tmp_path: Path) -> None:
    server = _CapturingServer()
    diag = lsp.Diagnostic(range=lsp.Range(lsp.Position(0, 0), lsp.Position(0, 1)), message="x")
    _publish(server, tmp_path, {"run_events.txt": [diag]})  # type: ignore[arg-type]
    assert set(server.diagnostics_by_uri) == {uris.from_fs_path(str(tmp_path / "run_events.txt"))}
    assert server.sent[-1].diagnostics  # non-empty first time

    _publish(server, tmp_path, {})  # type: ignore[arg-type]  # now clean
    assert server.sent[-1].diagnostics == []  # an explicit clear was sent
    assert server.diagnostics_by_uri == {}


def test_revalidate_publishes_real_findings(monkeypatch) -> None:
    captured: list[lsp.PublishDiagnosticsParams] = []
    server = build_server()
    monkeypatch.setattr(
        server, "text_document_publish_diagnostics", lambda params: captured.append(params)
    )
    feed = FIXTURES / "invalid" / "TODS-E202"
    assert validate_feed(feed).findings  # the fixture really does have findings
    uri = uris.from_fs_path(str(feed / "stops_supplement.txt"))
    revalidate(server, uri)
    assert any(p.diagnostics for p in captured)  # something was published


def test_revalidate_ignores_non_tods_files() -> None:
    captured: list[lsp.PublishDiagnosticsParams] = []
    server = build_server()
    server.text_document_publish_diagnostics = lambda params: captured.append(params)  # type: ignore[method-assign]
    revalidate(server, uris.from_fs_path(str(FIXTURES / "valid" / "gtfs" / "agency.txt")))
    assert captured == []  # a GTFS file does not trigger a TODS validation pass


def test_disk_reader_reads_and_misses(tmp_path: Path) -> None:
    (tmp_path / "run_events.txt").write_text("a,b\n")
    read = _disk_reader(tmp_path)
    assert read("run_events.txt") == "a,b\n"
    assert read("missing.txt") is None


def test_cli_exposes_lsp_command() -> None:
    result = CliRunner().invoke(main, ["lsp", "--help"])
    assert result.exit_code == 0
    assert "language server" in result.output.lower()


# --- quick fixes and hover ----------------------------------------------------


def _diag(code: str, start: tuple[int, int], end: tuple[int, int]) -> lsp.Diagnostic:
    return lsp.Diagnostic(
        range=lsp.Range(lsp.Position(*start), lsp.Position(*end)), message="m", code=code
    )


def test_w206_quick_fix_trims_the_padded_span() -> None:
    # The padded value "garage " sits at characters 4..11 of the line.
    line = "S1,, garage ,x"
    diag = _diag("TODS-W206", (1, 4), (1, 12))
    [action] = build_code_actions("file://feed/run_events.txt", [diag], lambda _i: line)
    assert action.title == "Trim surrounding whitespace"
    assert action.kind == lsp.CodeActionKind.QuickFix
    [edit] = action.edit.changes["file://feed/run_events.txt"]
    assert edit.new_text == "garage"  # the surrounding spaces are gone
    assert edit.range == diag.range


def test_w408_quick_fix_deletes_the_whole_row() -> None:
    diag = _diag("TODS-W408", (3, 0), (3, 20))
    [action] = build_code_actions("file://feed/employee_run_dates.txt", [diag], lambda _i: "x")
    assert action.title == "Delete duplicate row"
    [edit] = action.edit.changes["file://feed/employee_run_dates.txt"]
    assert edit.new_text == ""
    assert edit.range == lsp.Range(lsp.Position(3, 0), lsp.Position(4, 0))  # consumes the newline


def test_non_fixable_diagnostics_offer_no_action() -> None:
    diag = _diag("TODS-E201", (1, 0), (1, 5))  # a missing required value needs a human
    assert build_code_actions("file://feed/run_events.txt", [diag], lambda _i: "x,y") == []


def test_hover_markdown_describes_a_real_rule() -> None:
    text = hover_markdown("TODS-W206")
    assert text is not None
    assert "TODS-W206" in text
    assert "WARNING" in text
    assert "https://" in text  # links to the spec
    assert hover_markdown("TODS-NOPE") is None  # unknown rule


def test_range_covers_endpoints_and_excludes_outside() -> None:
    span = lsp.Range(lsp.Position(1, 4), lsp.Position(1, 10))
    assert _range_covers(span, lsp.Position(1, 4))  # inclusive start
    assert _range_covers(span, lsp.Position(1, 10))  # inclusive end
    assert not _range_covers(span, lsp.Position(1, 3))  # before
    assert not _range_covers(span, lsp.Position(2, 5))  # different line


def test_server_advertises_its_features() -> None:
    features = build_server().protocol.fm.features
    assert lsp.TEXT_DOCUMENT_DID_OPEN in features
    assert lsp.TEXT_DOCUMENT_DID_SAVE in features
    assert lsp.TEXT_DOCUMENT_CODE_ACTION in features  # quick fixes
    assert lsp.TEXT_DOCUMENT_HOVER in features  # rule descriptions
