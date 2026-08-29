"""scripts/generate_rules_doc.py: docs/rules.md and the web/rules/ page set."""

from __future__ import annotations

import importlib.util
import re
from html import escape
from pathlib import Path

from tods_validate.findings import Severity
from tods_validate.report import RULE_PAGE_BASE
from tods_validate.rules import all_rules
from tods_validate.schema import SPEC_VERSION

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
    #
    # This used to read `assert "<link " not in page`, which stated the rule
    # more broadly than the rule is. What must not appear is a link that makes
    # the browser fetch something: a stylesheet, an icon, a font, a preload.
    # `rel="canonical"` fetches nothing at all; it is a statement about which
    # URL this page is, and these pages need one, because they are served at a
    # path on an origin five sibling projects share. So the assertion names the
    # rels that load rather than the tag that sometimes does.
    for loading_rel in ("stylesheet", "icon", "preload", "prefetch", "preconnect", "manifest"):
        assert f'rel="{loading_rel}"' not in page, f"{loading_rel} would be an external fetch"
    for link in re.findall(r"<link\b[^>]*>", page):
        assert 'rel="canonical"' in link, f"unexpected <link>: {link}"
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


# ---------------------------------------------------------------------------
# The head, and the shared origin these 44 pages have to survive
#
# The catalog is served at a path under chelseakr.github.io, which five sibling
# projects also publish under, and https://chelseakr.github.io/ is itself a
# 404. A canonical naming the bare origin would tell a crawler that six
# unrelated projects are one page, and a root-relative href would resolve to
# another project or to nothing. Neither is visible in a browser.
#
# The permanence contract makes it sharper here than elsewhere: these URLs are
# what SARIF helpUri, editor hovers and CI annotations link back to, and rule
# IDs are never renumbered, so a link made today is meant to keep working.
# ---------------------------------------------------------------------------

# Written out rather than imported from tods_validate.report.RULE_PAGE_BASE.
# The generator reads its canonical from that constant, so a test that also
# read it would move with the constant and stay green through exactly the
# mistake it is here to catch.
_PUBLISHED_RULE_BASE = "https://chelseakr.github.io/tods-validate/rules/"


def _head(page: str) -> str:
    return page.split("</head>", 1)[0]


def _attribute(head: str, pattern: str) -> str | None:
    found = re.search(pattern, head)
    return found.group(1) if found else None


def test_the_generator_reads_its_canonical_from_the_url_sarif_publishes() -> None:
    # One string, so a rule page's canonical and the helpUri a CI annotation
    # hands a reader cannot come apart.
    assert RULE_PAGE_BASE == _PUBLISHED_RULE_BASE


def test_every_page_canonical_is_its_own_permanent_url() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    for name, page in pages.items():
        head = _head(page)
        expected = _PUBLISHED_RULE_BASE + name
        assert _attribute(head, r'<link rel="canonical" href="([^"]*)"') == expected, (
            f"{name} canonical is not {expected}"
        )
        assert _attribute(head, r'<meta property="og:url" content="([^"]*)"') == expected


def test_every_page_describes_itself_with_its_own_text() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    for rule in all_rules():
        head = _head(pages[f"{rule.id}.html"])
        described = _attribute(head, r'<meta name="description" content="([^"]*)"')
        assert described == escape(rule.description, quote=True), (
            f"{rule.id}: the description is not the rule's registered description"
        )
    catalog = _head(pages["index.html"])
    assert (_attribute(catalog, r'<meta name="description" content="([^"]*)"') or "").strip()


def test_no_two_pages_share_a_description_or_a_title() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    heads = [_head(page) for page in pages.values()]
    descriptions = [_attribute(h, r'<meta name="description" content="([^"]*)"') for h in heads]
    titles = [_attribute(h, r"<title>([^<]*)</title>") for h in heads]
    assert None not in descriptions
    assert len(set(descriptions)) == len(pages), "two rule pages describe themselves identically"
    assert len(set(titles)) == len(pages), "two rule pages carry the same title"


def test_every_page_carries_a_share_card_that_agrees_with_the_page() -> None:
    gen = _load_generator()
    pages = gen.generate_rule_pages()
    for name, page in pages.items():
        head = _head(page)
        assert '<meta property="og:type" content="article" />' in head, name
        assert '<meta property="og:site_name" content="tods-validate" />' in head, name
        assert '<meta name="twitter:card" content="summary" />' in head, name
        title = _attribute(head, r"<title>([^<]*)</title>")
        assert _attribute(head, r'<meta property="og:title" content="([^"]*)"') == title, name
        described = _attribute(head, r'<meta name="description" content="([^"]*)"')
        assert (
            _attribute(head, r'<meta property="og:description" content="([^"]*)"') == described
        ), name


def test_no_page_makes_a_root_relative_reference() -> None:
    gen = _load_generator()
    for name, page in gen.generate_rule_pages().items():
        rooted = re.findall(r'(?:href|src)="(/(?!/)[^"]*)"', page)
        assert rooted == [], f"{name} escapes /tods-validate/ via {rooted}"


def test_no_page_states_a_rule_count_in_its_head() -> None:
    # The rule count is derived from the registry. A number in a meta tag would
    # be a copy nothing derives, wrong the first release a rule is added. Rule
    # IDs are digits too, so this looks only at the description.
    gen = _load_generator()
    for name, page in gen.generate_rule_pages().items():
        if name != "index.html":
            continue
        described = _attribute(_head(page), r'<meta name="description" content="([^"]*)"') or ""
        # The spec version is a figure the description is allowed to carry: it
        # is read from tods_validate.schema.SPEC_VERSION, not typed here.
        without_spec_version = described.replace(f"TODS v{SPEC_VERSION}", "")
        assert re.search(r"\b[0-9]+\b", without_spec_version) is None, (
            f"the catalog description states a figure nothing derives: {described!r}"
        )
