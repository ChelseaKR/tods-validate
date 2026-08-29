"""docs/rules.md must not drift from the rule registry (`--check` in CI).

Loads scripts/generate_rules_doc.py the same way tests/test_conformance_corpus.py
loads scripts/build_conformance_corpus.py, so this runs under plain pytest
instead of only as a separate CI step.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_rules_doc.py"
_DOC = Path(__file__).resolve().parent.parent / "docs" / "rules.md"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_rules_doc", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rules_doc_matches_the_registry() -> None:
    generator = _load_generator()
    generated = generator.generate()
    committed = _DOC.read_text(encoding="utf-8")
    assert generated == committed, (
        "docs/rules.md is out of date; run `python scripts/generate_rules_doc.py`"
    )


def test_rules_doc_includes_worked_examples() -> None:
    """Guards R6/EXP-01: examples render into docs/rules.md, not just `explain`."""
    from tods_validate.rules import EXAMPLES

    generator = _load_generator()
    generated = generator.generate()
    # Spot-check a core rule's example body actually made it into the doc, so a
    # regression that stops threading EXAMPLES through generate() is caught.
    example = EXAMPLES["TODS-W206"]
    assert f"Example (`{example.file}`)" in generated
    assert example.before in generated
    assert example.after in generated


_WEB_RULES = Path(__file__).resolve().parent.parent / "web" / "rules"
_A11Y_STATEMENT = Path(__file__).resolve().parent.parent / "docs" / "a11y" / "STATEMENT.md"
_GAPS = Path(__file__).resolve().parent.parent / "docs" / "CONFORMANCE-GAPS.md"


def test_web_rule_pages_match_the_registry() -> None:
    """The other half of what the generator writes, compared here too.

    ``scripts/generate_rules_doc.py --check`` compares both docs/rules.md and
    every page under web/rules/, but only `make docs-check` runs it. Until now
    pytest compared docs/rules.md alone, so the 44 published pages were gated
    by exactly one command in one recipe. They are the pages `pages.yml`
    deploys and the pages SARIF `helpUri` links point at, so they are compared
    inside `make test` as well. Nothing is written: the generator's pages are
    rendered in memory and diffed against the committed files.
    """
    generator = _load_generator()
    pages = generator.generate_rule_pages()
    assert pages, "the generator rendered no pages; this comparison would be vacuous"
    for name, content in sorted(pages.items()):
        path = _WEB_RULES / name
        assert path.exists(), f"{path} is missing; run `python scripts/generate_rules_doc.py`"
        assert path.read_text(encoding="utf-8") == content, (
            f"{path} is out of date; run `python scripts/generate_rules_doc.py`"
        )
    committed = {path.name for path in _WEB_RULES.glob("*.html")}
    assert committed == set(pages), sorted(committed ^ set(pages))


def test_the_prose_that_counts_the_published_pages_counts_them_right() -> None:
    """Three documents state how many rule pages are published. None derived it.

    The number is one per rule plus the catalog index, so it moves whenever a
    rule is added. It was right; nothing was keeping it right.
    """
    generator = _load_generator()
    count = len(generator.generate_rule_pages())
    # Anchored to the phrase each document actually uses. A bare "44" would
    # pass on any stray number in the file, which is how a count check goes
    # green while the count it names is wrong.
    phrases = {
        _A11Y_STATEMENT: (f"{count} published pages", f"The {count} pages"),
        _GAPS: (f"the {count} rule-catalog pages",),
    }
    for path, expected in phrases.items():
        text = path.read_text(encoding="utf-8")
        for phrase in expected:
            assert phrase in text, (
                f"{path.name} does not say {phrase!r}; the published rule-page count "
                "and the generator have drifted apart"
            )
