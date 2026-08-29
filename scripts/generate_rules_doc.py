#!/usr/bin/env python3
"""Generate docs/rules.md and web/rules/ from the rule registry.

docs/rules.md is a single Markdown catalog. web/rules/ is one permanent HTML
page per rule ID (e.g. web/rules/TODS-1101.html) plus a web/rules/index.html
catalog, deployed by .github/workflows/pages.yml; SARIF ``helpUri`` and LSP
hovers link to these pages (see ``tods_validate.report.RULE_PAGE_BASE``).
Rule IDs are never renumbered once released, so these URLs are permanent.

Run with --check (as CI does) to fail if the committed files have drifted
from the registry instead of rewriting them.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from tods_validate.findings import Severity
from tods_validate.report import RULE_PAGE_BASE
from tods_validate.rules import EXAMPLES, Rule, all_rules, render_example_markdown
from tods_validate.schema import SPEC_VERSION

DOC_PATH = Path(__file__).parent.parent / "docs" / "rules.md"
WEB_RULES_DIR = Path(__file__).parent.parent / "web" / "rules"

# Each page's canonical URL is the address SARIF already publishes for it.
#
# ``RULE_PAGE_BASE`` is what ``helpUri`` points at and what editor hovers open,
# so reusing it here means a rule page's canonical and the URL the tool hands a
# CI annotation cannot drift apart: there is one string, and
# tests/test_generate_rules_doc.py holds the pages to it.
#
# It matters that the base carries ``/tods-validate/``. These pages are served
# at a path under chelseakr.github.io, which five sibling projects also publish
# under, and https://chelseakr.github.io/ is itself a 404. A canonical naming
# the bare origin would tell a crawler that six unrelated projects are one
# page, and a root-relative href would resolve to another project or to
# nothing. Neither is visible in a browser.
_CATALOG_URL = RULE_PAGE_BASE + "index.html"


def _head_metadata(*, title: str, description: str, canonical: str) -> str:
    """The description, canonical and share card shared by every page here.

    Every description is the page's own text: a rule page describes itself with
    the rule's registered description, and the catalog with its own lede. None
    of them states a rule count. The count is derived from the registry at
    build time, README claims about it are pinned by
    tests/test_readme_claims.py, and a number copied into a meta tag would be a
    third copy that nothing derives and nothing checks.
    """
    esc = html.escape
    return (
        f'    <meta name="description" content="{esc(description, quote=True)}" />\n'
        f'    <link rel="canonical" href="{esc(canonical, quote=True)}" />\n'
        f'    <meta property="og:type" content="article" />\n'
        f'    <meta property="og:site_name" content="tods-validate" />\n'
        f'    <meta property="og:url" content="{esc(canonical, quote=True)}" />\n'
        f'    <meta property="og:title" content="{esc(title, quote=True)}" />\n'
        f'    <meta property="og:description" content="{esc(description, quote=True)}" />\n'
        f'    <meta name="twitter:card" content="summary" />\n'
    )


_BANDS = {
    "1": "Package and file structure",
    "2": "Field values",
    "3": "References between files",
    "4": "Semantic checks",
    "5": "Coverage (opt-in, informational)",
    "6": "Advisory (opt-in)",
}

# Every colour here is stated for both schemes and checked against WCAG 2.1 AA.
# The previous stylesheet declared `color-scheme: light dark` and then set no
# colour or background on `body`, so the user agent painted dark-mode text on
# an unpainted canvas: axe reported a contrast failure on every text element of
# every published page, `<h1>` and body copy included. It was never seen
# because `scripts/pa11y-ci.cjs` audited `index.html` and a generated report
# and not the 44 catalog pages `pages.yml` publishes beside them.
#
# Ratios against #ffffff / #121212, computed rather than eyeballed:
#   --fg 17.40 / 15.29   --muted 7.00 / 7.88   --link 7.78 / 8.89
#   --line 5.33 / 6.66 (badge border; non-text, so 3:1 would do)
#
# Links also carry an underline rather than colour alone (WCAG 1.4.1), which is
# what HTML_CodeSniffer flagged 43 times on the index: `a { color: inherit }`
# plus `text-decoration: none` left them indistinguishable from body text by
# any means at all.
_PAGE_STYLE = """\
      :root {
        color-scheme: light dark;
        --fg: #1a1a1a;
        --bg: #ffffff;
        --muted: #595959;
        --link: #0b4fa8;
        --line: #6b6b6b;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --fg: #e8e8e8;
          --bg: #121212;
          --muted: #a8a8a8;
          --link: #8ab4f8;
          --line: #9a9a9a;
        }
      }
      body {
        font: 16px/1.5 system-ui, sans-serif;
        max-width: 40rem;
        margin: 2rem auto;
        padding: 0 1rem;
        color: var(--fg);
        background: var(--bg);
      }
      h1 { margin-bottom: 0.25rem; font-size: 1.5rem; }
      h2 { margin-top: 2rem; font-size: 1.1rem; }
      .lede, .meta, .id { color: var(--muted); }
      .id { font-family: ui-monospace, monospace; margin: 0; }
      .meta { margin: 0.5rem 0 1rem; }
      .badge {
        display: inline-block;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 0.1rem 0.5rem;
        border-radius: 999px;
        border: 1px solid var(--line);
        margin-right: 0.4rem;
      }
      a { color: var(--link); text-decoration: underline; }
      code { background: rgba(127, 127, 127, 0.15); padding: 0 0.25rem; border-radius: 3px; }
      ul.rule-list { list-style: none; padding-left: 0; }
      ul.rule-list li { padding: 0.25rem 0; }
"""


def generate() -> str:
    lines = [
        "# Rule catalog",
        "",
        "<!-- Generated by scripts/generate_rules_doc.py; do not edit by hand. -->",
        "",
        f"All rules below validate against TODS v{SPEC_VERSION}. Severities:",
        "",
        "- **ERROR**: the feed violates the spec; consumers may misread or drop data.",
        "- **WARNING**: probably a mistake, but the spec does not forbid it.",
        "- **INFO**: worth knowing; no action required.",
        "",
        "Rules that resolve IDs into the companion GTFS feed run only when one is",
        "available (via `--gtfs` or GTFS files alongside the TODS files).",
        "",
    ]
    rules = sorted(all_rules(), key=lambda r: r.id.split("-")[1][1:])
    for band, heading in _BANDS.items():
        lines.append(f"## {heading} (TODS-x{band}xx)")
        lines.append("")
        for r in rules:
            if r.id.split("-")[1][1] != band:
                continue
            severity = Severity[r.severity.name].name
            needs = " Needs a companion GTFS feed." if r.needs_gtfs else ""
            optin = (
                f" Opt-in: off by default, enable with `--enable {r.category}` or "
                f"`--enable {r.id}`."
                if not r.default_enabled
                else ""
            )
            lines.append(f"### {r.id}: {r.title}")
            lines.append("")
            lines.append(f"Severity: {severity}.{needs}{optin}")
            lines.append("")
            lines.append(r.description)
            lines.append("")
            if r.interpretation:
                lines.append(f"Interpretation: {r.interpretation}")
                lines.append("")
            example = EXAMPLES.get(r.id)
            if example is not None:
                lines.extend(render_example_markdown(example))
                lines.append("")
            lines.append(f"Spec reference: <{r.spec_section}>")
            lines.append("")
    return "\n".join(lines)


def _rule_notes(r: Rule) -> str:
    """The needs-GTFS / opt-in notes shared by docs/rules.md and the rule page."""
    notes = []
    if r.needs_gtfs:
        notes.append("Needs a companion GTFS feed.")
    if not r.default_enabled:
        notes.append(
            f"Opt-in: off by default, enable with --enable {r.category} or --enable {r.id}."
        )
    return " ".join(notes)


def _rule_page_html(r: Rule) -> str:
    """A self-contained, permanent HTML page for one rule.

    No external assets (Pages/CSP-friendly): a single inline <style>, no
    scripts, no fonts or images fetched over the network. All rule text is
    HTML-escaped since it ultimately comes from source strings authored in
    the rule modules.
    """
    esc = html.escape
    severity = Severity[r.severity.name].name
    notes = _rule_notes(r)
    interpretation_html = (
        f"    <p><strong>Interpretation:</strong> {esc(r.interpretation)}</p>\n"
        if r.interpretation
        else ""
    )
    notes_html = f"<p class='meta'>{esc(notes)}</p>\n    " if notes else ""
    spec_href = esc(r.spec_section, quote=True)
    spec_text = esc(r.spec_section)
    title = f"{r.id}: {r.title} — tods-validate rule catalog"
    # The rule's registered description, which is the paragraph the page
    # renders below. Two statements about one rule, from one string.
    metadata = _head_metadata(
        title=title,
        description=r.description,
        canonical=f"{RULE_PAGE_BASE}{r.id}.html",
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{esc(title)}</title>
{metadata}    <style>
{_PAGE_STYLE}    </style>
  </head>
  <body>
    <nav><a href="index.html">&larr; All rules</a></nav>
    <p class="id">{esc(r.id)}</p>
    <h1>{esc(r.title)}</h1>
    <p class="meta"><span class="badge">{esc(severity)}</span></p>
    {notes_html}<p>{esc(r.description)}</p>
{interpretation_html}    <p>Spec reference: <a href="{spec_href}">{spec_text}</a></p>
  </body>
</html>
"""


def _index_page_html(rules: list[Rule]) -> str:
    """The web/rules/ catalog: every rule grouped by band, linking to its page."""
    esc = html.escape
    sections = []
    for band, heading in _BANDS.items():
        band_rules = [r for r in rules if r.id.split("-")[1][1] == band]
        if not band_rules:
            continue
        items = []
        for r in band_rules:
            severity = Severity[r.severity.name].name
            items.append(
                "      <li>"
                f'<a href="{esc(r.id)}.html"><code>{esc(r.id)}</code></a> '
                f"&mdash; {esc(r.title)} "
                f'<span class="badge">{esc(severity)}</span></li>'
            )
        sections.append(
            f"    <h2>{esc(heading)} (TODS-x{esc(band)}xx)</h2>\n"
            '    <ul class="rule-list">\n' + "\n".join(items) + "\n    </ul>\n"
        )
    body = "\n".join(sections)
    metadata = _head_metadata(
        title="tods-validate rule catalog",
        description=(
            f"Every rule tods-validate checks against TODS v{SPEC_VERSION}, one permanent "
            f"page per rule ID. These are the URLs SARIF helpUri, editor hovers and CI "
            f"annotations link back to."
        ),
        canonical=_CATALOG_URL,
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>tods-validate rule catalog</title>
{metadata}    <style>
{_PAGE_STYLE}    </style>
  </head>
  <body>
    <h1>tods-validate rule catalog</h1>
    <p class="lede">
      Every rule tods-validate checks against TODS v{esc(SPEC_VERSION)}, one
      permanent page per rule ID. These URLs are what SARIF <code>helpUri</code>,
      editor hovers, and CI annotations link back to; rule IDs are never
      renumbered once released, so a link made today keeps working.
    </p>
{body}  </body>
</html>
"""


def generate_rule_pages() -> dict[str, str]:
    """Render every web/rules/<RULE_ID>.html page plus web/rules/index.html.

    Returns a mapping of filename to full file content so callers can either
    write it to disk or diff it against the committed files (--check) without
    duplicating the rendering logic.
    """
    rules = sorted(all_rules(), key=lambda r: r.id.split("-")[1][1:])
    pages = {f"{r.id}.html": _rule_page_html(r) for r in rules}
    pages["index.html"] = _index_page_html(rules)
    return pages


def _check_web_rules(pages: dict[str, str]) -> list[str]:
    """Return a list of stale/missing/orphaned paths under web/rules/, if any."""
    stale: list[str] = []
    for name, content in sorted(pages.items()):
        path = WEB_RULES_DIR / name
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            stale.append(str(path))
    if WEB_RULES_DIR.exists():
        existing = {p.name for p in WEB_RULES_DIR.glob("*.html")}
        for name in sorted(existing - set(pages)):
            stale.append(f"{WEB_RULES_DIR / name} (orphaned: no matching rule)")
    return stale


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail if docs/rules.md or web/rules/ are stale"
    )
    args = parser.parse_args()
    content = generate()
    pages = generate_rule_pages()
    if args.check:
        stale = []
        if not DOC_PATH.exists() or DOC_PATH.read_text(encoding="utf-8") != content:
            stale.append(str(DOC_PATH))
        stale.extend(_check_web_rules(pages))
        if stale:
            print(
                "Generated docs are out of date; run scripts/generate_rules_doc.py. "
                "Stale or missing:",
                file=sys.stderr,
            )
            for path in stale:
                print(f"  {path}", file=sys.stderr)
            return 1
        print("docs/rules.md and web/rules/ are up to date")
        return 0
    DOC_PATH.write_text(content, encoding="utf-8")
    WEB_RULES_DIR.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in WEB_RULES_DIR.glob("*.html")} if WEB_RULES_DIR.exists() else set()
    for name, page_content in pages.items():
        (WEB_RULES_DIR / name).write_text(page_content, encoding="utf-8")
    for orphaned in existing - set(pages):
        (WEB_RULES_DIR / orphaned).unlink()
    print(f"wrote {DOC_PATH} and {len(pages)} file(s) in {WEB_RULES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
