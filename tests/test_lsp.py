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
    build_server,
    diagnostics_for_feed,
    feed_root_for,
    field_span,
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
        self.published: set[str] = set()
        self.sent: list[lsp.PublishDiagnosticsParams] = []

    def text_document_publish_diagnostics(self, params: lsp.PublishDiagnosticsParams) -> None:
        self.sent.append(params)


def test_publish_clears_a_file_once_it_is_clean(tmp_path: Path) -> None:
    server = _CapturingServer()
    diag = lsp.Diagnostic(range=lsp.Range(lsp.Position(0, 0), lsp.Position(0, 1)), message="x")
    _publish(server, tmp_path, {"run_events.txt": [diag]})  # type: ignore[arg-type]
    assert server.published == {uris.from_fs_path(str(tmp_path / "run_events.txt"))}
    assert server.sent[-1].diagnostics  # non-empty first time

    _publish(server, tmp_path, {})  # type: ignore[arg-type]  # now clean
    assert server.sent[-1].diagnostics == []  # an explicit clear was sent
    assert server.published == set()


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
