"""A citation is labelled by what it cites.

Every TODS- rule cites the section of the TODS specification it enforces, and
no other rule does; tests/test_registry.py holds both halves of that. The
renderers have to keep the same promise when they print the link. An OPS-
rule's citation is the ADR that decided it, and a line reading "TODS
specification" or "Spec:" beside that link tells a feed producer the standard
requires something it does not say, which is the misrepresentation ADR 0008
opened a second namespace to prevent.

There are four places a citation is rendered: ``explain`` as text, ``explain
--format markdown`` (which is also the editor hover, see ``lsp.hover_markdown``),
docs/rules.md, and the published rule pages under web/rules/. Before this file
all four labelled every citation as the specification.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tods_validate.rules import (
    NOT_A_SPEC_REQUIREMENT,
    SPEC_NAMESPACE,
    Rule,
    all_rules,
    cites_spec,
    render_rule_detail,
)

_SCRIPT = Path(__file__).parent.parent / "scripts" / "generate_rules_doc.py"

_RULES = tuple(all_rules())
_SPEC_RULES = tuple(r for r in _RULES if r.id.startswith(SPEC_NAMESPACE))
_OTHER_RULES = tuple(r for r in _RULES if not r.id.startswith(SPEC_NAMESPACE))


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_rules_doc_for_labels", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _doc_section(doc: str, rule_id: str) -> str:
    """One rule's entry in docs/rules.md, from its heading to the next one."""
    start = doc.index(f"### {rule_id}:")
    end = doc.find("\n### ", start + 1)
    return doc[start:] if end == -1 else doc[start:end]


def test_both_kinds_of_rule_exist() -> None:
    # The floor. With no rule outside TODS- every test below that iterates
    # _OTHER_RULES passes over nothing, and with no TODS- rule the other half
    # does.
    assert _SPEC_RULES
    assert _OTHER_RULES


def test_cites_spec_is_the_namespace() -> None:
    assert {r.id for r in _RULES if cites_spec(r)} == {r.id for r in _SPEC_RULES}


@pytest.mark.parametrize("r", _OTHER_RULES, ids=lambda r: r.id)
def test_explain_does_not_present_a_decision_record_as_the_spec(r: Rule) -> None:
    text = render_rule_detail(r, "text")
    markdown = render_rule_detail(r, "markdown")
    assert "Spec:" not in text
    assert "TODS specification](" not in markdown
    assert f"{NOT_A_SPEC_REQUIREMENT} Decision record: {r.spec_section}" in text
    assert f"{NOT_A_SPEC_REQUIREMENT} [Decision record]({r.spec_section})" in markdown


def test_explain_still_cites_the_spec_for_every_tods_rule() -> None:
    for r in _SPEC_RULES:
        text = render_rule_detail(r, "text")
        markdown = render_rule_detail(r, "markdown")
        assert f"Spec: {r.spec_section}" in text, r.id
        assert f"[TODS specification]({r.spec_section})" in markdown, r.id
        assert NOT_A_SPEC_REQUIREMENT not in text + markdown, r.id


def test_rules_doc_and_rule_pages_label_each_citation_by_namespace() -> None:
    generator = _generator()
    doc = generator.generate()
    pages = generator.generate_rule_pages()
    for r in _RULES:
        section = _doc_section(doc, r.id)
        page = pages[f"{r.id}.html"]
        # Branch on the namespace, not on cites_spec(): the generator calls
        # cites_spec() to choose its label, so a test that asked the same
        # function which label to expect would agree with it however wrong it
        # was. Measured: with cites_spec() forced to True, and again to False,
        # this test stayed green when it branched that way.
        if r in _SPEC_RULES:
            assert f"Spec reference: <{r.spec_section}>" in section, r.id
            assert "<p>Spec reference: <a " in page, r.id
            assert NOT_A_SPEC_REQUIREMENT not in section + page, r.id
        else:
            assert "Spec reference" not in section + page, r.id
            assert f"{NOT_A_SPEC_REQUIREMENT} Decision record: <{r.spec_section}>" in section
            assert f"<p>{NOT_A_SPEC_REQUIREMENT} Decision record: <a " in page, r.id
