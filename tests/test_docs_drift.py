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
