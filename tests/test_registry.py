"""Sanity checks on the rule registry itself."""

from pathlib import Path

from tods_validate.findings import Severity
from tods_validate.rules import all_rules

FIXTURES = Path(__file__).parent / "fixtures" / "invalid"

_SEVERITY_LETTERS = {Severity.ERROR: "E", Severity.WARNING: "W", Severity.INFO: "I"}


def test_ids_are_unique() -> None:
    ids = [r.id for r in all_rules()]
    assert len(ids) == len(set(ids))


def test_id_letter_matches_severity() -> None:
    for r in all_rules():
        prefix, code = r.id.split("-")
        assert prefix == "TODS"
        assert code[0] == _SEVERITY_LETTERS[r.severity], r.id


def test_every_rule_cites_the_spec() -> None:
    for r in all_rules():
        assert r.spec_section.startswith("https://tods-transit.org/spec/"), r.id


def test_every_rule_has_a_dedicated_broken_fixture() -> None:
    fixture_dirs = {p.name for p in FIXTURES.iterdir() if p.is_dir()}
    rule_ids = {r.id for r in all_rules()}
    assert fixture_dirs == rule_ids


def test_descriptions_are_written_out() -> None:
    for r in all_rules():
        assert r.title
        assert not r.title.endswith(".")
        assert len(r.description) > 40, f"{r.id} description too thin"


# The highest-frequency rules: those with root-cause cluster hints in
# report.py (TODS-E307, E308, E309, E314, W206), plus the common structural
# rules E104 and E106. These must carry a worked before/after fix example.
_HIGH_FREQUENCY_RULE_IDS = {
    "TODS-E104",
    "TODS-E106",
    "TODS-E307",
    "TODS-E308",
    "TODS-E309",
    "TODS-E314",
    "TODS-W206",
}


def test_high_frequency_rules_have_worked_examples() -> None:
    rules_by_id = {r.id: r for r in all_rules()}
    for rule_id in _HIGH_FREQUENCY_RULE_IDS:
        assert rule_id in rules_by_id, rule_id
        example = rules_by_id[rule_id].example
        assert example, f"{rule_id} is missing a worked before/after example"
        assert "Before:" in example, rule_id
        assert "After:" in example, rule_id
