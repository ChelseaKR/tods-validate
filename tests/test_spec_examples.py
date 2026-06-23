"""Conformance check against the TODS spec's own published examples.

The example CSVs are vendored from the spec repo (docs/en/spec/examples.md in
MobilityData/transit-operational-data-standard, see the header in
tests/fixtures/spec_examples.md). Running the validator over them guards
against two kinds of drift: the validator diverging from the spec, and errata
in the examples themselves. It would have caught the duplicate event_sequence
in the "Run as Directed work" example (PR #147 upstream).

Each example is a fragment that does not ship the companion GTFS its references
resolve against, so reference errors (TODS-E3xx) are expected and ignored here;
only self-contained structural and field errors (TODS-E1xx/E2xx) are asserted.
Whitespace padding used for column alignment in the examples is stripped before
parsing.

Known findings on the vendored snapshot (asserted so the test is green and the
findings are documented, not hidden):

- "Run as Directed work" -> TODS-E204: two run_events rows reuse
  event_sequence 30. Fixed upstream by PR #147.
- "Jobs of entirely nonrevenue operations" -> TODS-E106: the
  stop_times_supplement omits the required stop_sequence column. Flagged for
  upstream discussion.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tods_validate.runner import run

_EXAMPLES_MD = Path(__file__).parent / "fixtures" / "spec_examples.md"

# Structural/field errors expected on the vendored snapshot, by example section.
_KNOWN_FINDINGS: dict[str, set[str]] = {
    "Run as Directed work": {"TODS-E204"},
    "Jobs of entirely nonrevenue operations": {"TODS-E106"},
}


def _parse_examples(md: str) -> dict[str, dict[str, str]]:
    """Return {section title: {filename: de-padded csv text}} from the markdown."""
    sections: dict[str, dict[str, str]] = {}
    section: str | None = None
    filename: str | None = None
    in_block = False
    block: list[str] = []
    for line in md.splitlines():
        if line.startswith("## ") and not line.startswith("###"):
            section = line[3:].strip()
            filename = None
            continue
        heading = re.match(r"###\s+`?([\w.]+\.txt)`?", line)
        if heading:
            filename = heading.group(1)
            continue
        if line.strip() == "```csv":
            in_block, block = True, []
            continue
        if in_block and line.strip() == "```":
            in_block = False
            if section and filename and block:
                rows = [",".join(c.strip() for c in row.split(",")) for row in block]
                sections.setdefault(section, {})[filename] = "\n".join(rows) + "\n"
            continue
        if in_block:
            block.append(line)
    return sections


_SECTIONS = _parse_examples(_EXAMPLES_MD.read_text()) if _EXAMPLES_MD.exists() else {}


def test_examples_were_vendored_and_parsed() -> None:
    # Guards against the vendored file going missing or the parser silently
    # finding nothing (which would make the conformance check vacuous).
    assert len(_SECTIONS) >= 4, f"expected several example sections, got {sorted(_SECTIONS)}"


@pytest.mark.parametrize("section", sorted(_SECTIONS))
def test_spec_example_structural_errors_match_expected(section: str, tmp_path: Path) -> None:
    for name, text in _SECTIONS[section].items():
        (tmp_path / name).write_text(text)
    _, findings = run(tmp_path)
    structural = {f.rule_id for f in findings if f.rule_id.startswith(("TODS-E1", "TODS-E2"))}
    expected = _KNOWN_FINDINGS.get(section, set())
    assert structural == expected, (
        f"spec example {section!r}: structural/field errors {sorted(structural)} "
        f"do not match expected {sorted(expected)} -- the validator drifted from "
        f"the spec examples, or the examples changed."
    )
