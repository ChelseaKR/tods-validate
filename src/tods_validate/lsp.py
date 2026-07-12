"""Language Server Protocol integration for TODS feeds.

Wraps :func:`tods_validate.validate_feed` in a small language server so editors
show validation findings inline. Opening or saving any TODS file re-validates the
whole feed (the directory the file sits in) and publishes a diagnostic at each
finding's row and field.

The diagnostic-mapping core (:func:`feed_root_for`, :func:`field_span`,
:func:`diagnostics_for_feed`) is pure and unit-tested. The server itself needs the
optional ``pygls`` dependency; install it with ``pip install tods-validate[lsp]``.
Validation runs on open and save, not on every keystroke: it reads the feed from
disk, so an unsaved buffer would be validated stale.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from pathlib import Path

from lsprotocol import types as lsp

from . import __version__
from .api import ValidationResult
from .findings import Finding, Severity
from .schema import TABLES

# Only the TODS files the validator owns trigger a pass; a companion GTFS file
# opening in the same directory should not.
TODS_FILENAMES = frozenset(TABLES)

LANGUAGE_SERVER_NAME = "tods-validate-lsp"

_SEVERITY: dict[Severity, lsp.DiagnosticSeverity] = {
    Severity.ERROR: lsp.DiagnosticSeverity.Error,
    Severity.WARNING: lsp.DiagnosticSeverity.Warning,
    Severity.INFO: lsp.DiagnosticSeverity.Information,
}

# A reader maps a feed-relative filename to its current text, or None if it
# cannot be read (missing file, undecodable bytes). Injected so the core is
# testable without a filesystem.
TextReader = Callable[[str], "str | None"]


def feed_root_for(path: str | Path) -> Path:
    """The feed directory to validate for the file at ``path``.

    A TODS feed is a directory of CSV files, so editing one file means validating
    its parent directory. A directory path is returned unchanged.
    """
    target = Path(path)
    return target if target.is_dir() else target.parent


def field_span(line: str, index: int) -> tuple[int, int] | None:
    """``[start, end)`` character offsets of the field at 0-based ``index``.

    Splits the CSV ``line`` on unquoted commas, honoring double-quote quoting.
    Returns None when the line has fewer than ``index + 1`` fields.
    """
    col = 0
    field_start = 0
    in_quotes = False
    for i, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            if col == index:
                return (field_start, i)
            col += 1
            field_start = i + 1
    if col == index:
        return (field_start, len(line))
    return None


def _header_index(header_line: str, field: str) -> int | None:
    """Column position of ``field`` in a CSV header line, or None if absent."""
    try:
        names = next(csv.reader([header_line]))
    except StopIteration:
        return None
    for i, name in enumerate(names):
        if name == field:
            return i
    return None


def _range_for(finding: Finding, lines: list[str]) -> lsp.Range:
    """The editor range to underline for ``finding`` in a document's ``lines``.

    Highlights the offending field when the finding names one and it can be
    located; otherwise the whole row. A finding with no row, or a row past the
    end of the document, anchors at the start of the file.
    """
    line_index = 0 if finding.row is None else finding.row - 1
    if line_index < 0 or line_index >= len(lines):
        return lsp.Range(lsp.Position(0, 0), lsp.Position(0, 0))
    line = lines[line_index]
    span: tuple[int, int] | None = None
    if finding.field is not None and lines:
        column = _header_index(lines[0], finding.field)
        if column is not None:
            span = field_span(line, column)
    start, end = span if span is not None else (0, len(line))
    return lsp.Range(lsp.Position(line_index, start), lsp.Position(line_index, end))


def _diagnostic(finding: Finding, location: lsp.Range) -> lsp.Diagnostic:
    message = finding.message
    if finding.suggestion:
        message = f"{message}\n{finding.suggestion}"
    return lsp.Diagnostic(
        range=location,
        message=message,
        severity=_SEVERITY[finding.severity],
        code=finding.rule_id,
        source="tods-validate",
    )


def diagnostics_for_feed(
    result: ValidationResult, read_text: TextReader
) -> tuple[dict[str, list[lsp.Diagnostic]], list[Finding]]:
    """Map a :class:`ValidationResult` to per-file LSP diagnostics.

    Returns ``(by_file, unanchored)``: ``by_file`` keys feed-relative filenames to
    their diagnostics; ``unanchored`` holds findings with no file, or whose file
    could not be read, since they have no document to attach to. ``read_text``
    supplies each file's current text so ranges line up with the editor's view.
    """
    by_file: dict[str, list[lsp.Diagnostic]] = {}
    unanchored: list[Finding] = []
    cache: dict[str, list[str] | None] = {}
    for finding in result.findings:
        if finding.file is None:
            unanchored.append(finding)
            continue
        if finding.file not in cache:
            text = read_text(finding.file)
            cache[finding.file] = None if text is None else text.splitlines()
        lines = cache[finding.file]
        if lines is None:
            unanchored.append(finding)
            continue
        by_file.setdefault(finding.file, []).append(
            _diagnostic(finding, _range_for(finding, lines))
        )
    return by_file, unanchored


def _disk_reader(root: Path) -> TextReader:
    def read(filename: str) -> str | None:
        target = root / filename
        if not target.is_file():
            return None
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    return read


# --- Quick fixes and hover (pure) ----------------------------------------
# Rules whose fix is unambiguous enough to offer as a one-click editor action,
# mirroring what `tods-validate fix` does deterministically across a package.
_TRIM_WHITESPACE = "TODS-W206"
_DELETE_DUPLICATE_ROW = "TODS-W408"
FIXABLE = frozenset({_TRIM_WHITESPACE, _DELETE_DUPLICATE_ROW})

LineReader = Callable[[int], "str | None"]


def _whole_line_edit(line: int) -> lsp.TextEdit:
    """A TextEdit that removes line ``line`` entirely, including its newline."""
    return lsp.TextEdit(
        range=lsp.Range(lsp.Position(line, 0), lsp.Position(line + 1, 0)), new_text=""
    )


def build_code_actions(
    uri: str, diagnostics: Sequence[lsp.Diagnostic], get_line: LineReader
) -> list[lsp.CodeAction]:
    """Quick-fix code actions for the fixable diagnostics among ``diagnostics``.

    ``get_line(index)`` returns the document's line text without its newline, or
    None when out of range. Only TODS-W206 (trim the padded value in place) and
    TODS-W408 (delete the duplicate row) are offered; everything else needs a
    human's judgement and is left to ``validate``.
    """
    actions: list[lsp.CodeAction] = []
    for diagnostic in diagnostics:
        if diagnostic.code == _TRIM_WHITESPACE:
            line = get_line(diagnostic.range.start.line)
            if line is None:
                continue
            padded = line[diagnostic.range.start.character : diagnostic.range.end.character]
            trimmed = padded.strip()
            if trimmed == padded:
                continue
            edit = lsp.TextEdit(range=diagnostic.range, new_text=trimmed)
            actions.append(
                lsp.CodeAction(
                    title="Trim surrounding whitespace",
                    kind=lsp.CodeActionKind.QuickFix,
                    diagnostics=[diagnostic],
                    is_preferred=True,
                    edit=lsp.WorkspaceEdit(changes={uri: [edit]}),
                )
            )
        elif diagnostic.code == _DELETE_DUPLICATE_ROW:
            actions.append(
                lsp.CodeAction(
                    title="Delete duplicate row",
                    kind=lsp.CodeActionKind.QuickFix,
                    diagnostics=[diagnostic],
                    edit=lsp.WorkspaceEdit(
                        changes={uri: [_whole_line_edit(diagnostic.range.start.line)]}
                    ),
                )
            )
    return actions


def hover_markdown(rule_id: str) -> str | None:
    """Markdown describing a rule, for an editor hover over one of its findings.

    Renders through :func:`tods_validate.rules.render_rule_detail`, the same
    function ``tods-validate explain --format markdown`` uses, so a hover and
    ``explain`` describe a rule (worked example included) identically.
    """
    from .rules import all_rules, render_rule_detail

    for rule_def in all_rules():
        if rule_def.id == rule_id:
            return render_rule_detail(rule_def, "markdown")
    return None


def _range_covers(span: lsp.Range, position: lsp.Position) -> bool:
    """True when ``position`` falls within ``span`` (inclusive of the endpoints)."""
    here = (position.line, position.character)
    return (span.start.line, span.start.character) <= here <= (span.end.line, span.end.character)


# --- The pygls server -----------------------------------------------------
# Everything above is pure and import-clean with only lsprotocol. The server
# below additionally needs pygls (the [lsp] extra).

from pygls import uris  # noqa: E402
from pygls.lsp.server import LanguageServer  # noqa: E402


class TodsLanguageServer(LanguageServer):
    """A language server that re-validates a TODS feed on open and save."""

    def __init__(self) -> None:
        super().__init__(LANGUAGE_SERVER_NAME, __version__)
        # The diagnostics last published per URI, so a file can be cleared once
        # its findings resolve, and so hover/code-action can look them up.
        self.diagnostics_by_uri: dict[str, list[lsp.Diagnostic]] = {}


def _publish(
    server: TodsLanguageServer, root: Path, by_file: dict[str, list[lsp.Diagnostic]]
) -> None:
    """Publish ``by_file`` and clear any file under ``root`` that is now clean."""
    current: dict[str, list[lsp.Diagnostic]] = {}
    for filename, diagnostics in by_file.items():
        uri = uris.from_fs_path(str(root / filename))
        if uri is None:
            continue
        current[uri] = diagnostics
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
        )
    root_prefix = uris.from_fs_path(str(root)) or ""
    stale = {u for u in server.diagnostics_by_uri if u.startswith(root_prefix) and u not in current}
    for uri in stale:
        server.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=uri, diagnostics=[])
        )
        del server.diagnostics_by_uri[uri]
    server.diagnostics_by_uri.update(current)


def revalidate(server: TodsLanguageServer, doc_uri: str) -> None:
    """Validate the feed containing ``doc_uri`` and publish its diagnostics."""
    fs_path = uris.to_fs_path(doc_uri)
    if fs_path is None:
        return
    path = Path(fs_path)
    if path.name not in TODS_FILENAMES:
        return
    root = feed_root_for(path)
    try:
        from .api import validate_feed

        result = validate_feed(root)
    except Exception as exc:  # noqa: BLE001 - a broken feed must not kill the server
        server.window_show_message(
            lsp.ShowMessageParams(type=lsp.MessageType.Warning, message=f"tods-validate: {exc}")
        )
        return
    by_file, _ = diagnostics_for_feed(result, _disk_reader(root))
    _publish(server, root, by_file)


def build_server() -> TodsLanguageServer:  # noqa: C901 -- pragmatic complexity; ratchet tracked in docs/CONFORMANCE-GAPS.md#code-quality
    """Construct the server and register its document handlers."""
    server = TodsLanguageServer()

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def _did_open(params: lsp.DidOpenTextDocumentParams) -> None:
        revalidate(server, params.text_document.uri)

    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def _did_save(params: lsp.DidSaveTextDocumentParams) -> None:
        revalidate(server, params.text_document.uri)

    @server.feature(lsp.TEXT_DOCUMENT_CODE_ACTION)
    def _code_action(params: lsp.CodeActionParams) -> list[lsp.CodeAction] | None:
        uri = params.text_document.uri
        diagnostics = params.context.diagnostics or server.diagnostics_by_uri.get(uri, [])
        lines = server.workspace.get_text_document(uri).source.splitlines()

        def get_line(index: int) -> str | None:
            return lines[index] if 0 <= index < len(lines) else None

        return build_code_actions(uri, diagnostics, get_line) or None

    @server.feature(lsp.TEXT_DOCUMENT_HOVER)
    def _hover(params: lsp.HoverParams) -> lsp.Hover | None:
        diagnostics = server.diagnostics_by_uri.get(params.text_document.uri, [])
        seen: set[str] = set()
        sections: list[str] = []
        for diagnostic in diagnostics:
            if not _range_covers(diagnostic.range, params.position):
                continue
            rule_id = str(diagnostic.code) if diagnostic.code is not None else ""
            if rule_id in seen:
                continue
            seen.add(rule_id)
            markdown = hover_markdown(rule_id)
            if markdown:
                sections.append(markdown)
        if not sections:
            return None
        return lsp.Hover(
            contents=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown, value="\n\n---\n\n".join(sections)
            )
        )

    return server


def main() -> None:
    """Entry point for ``tods-validate-lsp``: serve over stdio."""
    build_server().start_io()
