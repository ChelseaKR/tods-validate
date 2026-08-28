"""scripts/generate_rules_doc.py: docs/rules.md and the web/rules/ page set."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tods_validate.findings import Severity
from tods_validate.rules import all_rules

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_rules_doc.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_rules_doc", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_rule_pages_covers_every_rule() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    rules = list(all_rules())
    # One file per rule, filenames exactly "<RULE_ID>.html" (the permanence
    # contract: filenames are the rule ID verbatim), plus the index catalog.
    assert len(pages) == len(rules) + 1
    assert "index.html" in pages
    for r in rules:
        assert f"{r.id}.html" in pages


def test_rule_page_carries_expected_fields_and_escapes_html() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    rule = next(r for r in all_rules() if r.id == "TODS-W206")
    page = pages["TODS-W206.html"]
    assert rule.id in page
    assert rule.title in page
    assert rule.severity.name in page
    assert rule.spec_section in page
    # No external assets: everything is inlined.
    assert "<link " not in page
    assert "<script" not in page


def test_rule_page_html_escapes_field_text() -> None:
    gen = _load_generator()

    fake_rule = gen.Rule(
        id="TODS-FAKE",
        severity=Severity.ERROR,
        title="<b>bold</b> title",
        description="a <script>alert(1)</script> description",
        spec_section="https://example.org/spec?a=1&b=2",
        check=lambda ctx: iter(()),
    )
    page = gen._rule_page_html(fake_rule)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "<b>bold</b>" not in page


def test_index_page_lists_every_rule_grouped_by_band() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    index = pages["index.html"]
    for r in all_rules():
        assert f'href="{r.id}.html"' in index


def test_check_mode_detects_drift(tmp_path: Path, monkeypatch) -> None:
    gen = _load_generator()
    monkeypatch.setattr(gen, "DOC_PATH", tmp_path / "rules.md")
    monkeypatch.setattr(gen, "WEB_RULES_DIR", tmp_path / "rules")

    # A fresh write leaves --check clean.
    monkeypatch.setattr("sys.argv", ["generate_rules_doc.py"])
    assert gen.main() == 0
    monkeypatch.setattr("sys.argv", ["generate_rules_doc.py", "--check"])
    assert gen.main() == 0

    # Touching a generated rule page introduces drift.
    stale_rule_id = next(iter(all_rules())).id
    stale_page = tmp_path / "rules" / f"{stale_rule_id}.html"
    stale_page.write_text("stale", encoding="utf-8")
    assert gen.main() == 1


def test_every_published_page_carries_the_audited_stylesheet() -> None:
    # scripts/pa11y-ci.cjs audits the catalog index plus one rule page, on the
    # reasoning that all 44 pages share one template. That reasoning is only
    # sound while it is true, so this is where it is checked: an audit of one
    # page is an audit of every page's *shape* precisely because the shape is
    # one string. Without this, a per-band or per-rule style override could
    # reintroduce the contrast failures the widened audit just removed.
    gen = _load_generator()
    pages = gen.generate_rule_pages()  # includes index.html
    assert "index.html" in pages
    assert len(pages) == len(all_rules()) + 1
    for name, html in pages.items():
        assert gen._PAGE_STYLE in html, f"{name} does not use the shared stylesheet"


def test_the_catalog_stylesheet_paints_both_schemes() -> None:
    # The defect the widened audit found: `color-scheme: light dark` with no
    # colour or background on `body`, so the user agent painted dark-mode text
    # on an unpainted canvas and every text element failed contrast. A page
    # that declares the scheme must define the palette for both halves of it.
    gen = _load_generator()
    style = gen._PAGE_STYLE
    assert "color-scheme: light dark" in style
    assert "prefers-color-scheme: dark" in style, "dark half of the scheme is undefined"
    assert "color: var(--fg)" in style
    assert "background: var(--bg)" in style


def test_catalog_links_do_not_rely_on_colour_alone() -> None:
    # WCAG 1.4.1, flagged 43 times on the index by HTML_CodeSniffer: links were
    # `color: inherit` with `text-decoration: none`, so they were not
    # distinguishable from body text by colour *or* anything else.
    style = _load_generator()._PAGE_STYLE
    assert "text-decoration: underline" in style
    assert "text-decoration: none" not in style
