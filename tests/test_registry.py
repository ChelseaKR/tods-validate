"""Sanity checks on the rule registry itself."""

from pathlib import Path

from tods_validate.findings import Severity
from tods_validate.rules import OPERATIONAL_NAMESPACE, SPEC_NAMESPACE, all_rules

FIXTURES = Path(__file__).parent / "fixtures" / "invalid"

_SEVERITY_LETTERS = {Severity.ERROR: "E", Severity.WARNING: "W", Severity.INFO: "I"}


def test_ids_are_unique() -> None:
    ids = [r.id for r in all_rules()]
    assert len(ids) == len(set(ids))


_NAMESPACES = {SPEC_NAMESPACE.rstrip("-"), OPERATIONAL_NAMESPACE.rstrip("-")}
_SPEC_URL_PREFIX = "https://tods-transit.org/spec/"


def test_id_letter_matches_severity() -> None:
    for r in all_rules():
        prefix, code = r.id.split("-")
        assert prefix in _NAMESPACES, r.id
        assert code[0] == _SEVERITY_LETTERS[r.severity], r.id


def test_every_tods_rule_cites_the_spec() -> None:
    """The citation promise: a TODS- ID means the spec says so."""
    for r in all_rules():
        if r.id.startswith(SPEC_NAMESPACE):
            assert r.spec_section.startswith(_SPEC_URL_PREFIX), r.id


def test_no_non_tods_rule_cites_the_spec() -> None:
    """The other half of the promise, and the half that can rot silently.

    A rule outside the TODS- namespace is there precisely because the spec does
    not entail it. If such a rule were allowed to carry a spec URL, its findings
    would read in every report and every SARIF ``helpUri`` as though the
    standard required them -- which is the exact misrepresentation the separate
    namespace exists to prevent. Asserting only the first half would let that
    through, because a spec-citing OPS- rule passes it vacuously.
    """
    for r in all_rules():
        if not r.id.startswith(SPEC_NAMESPACE):
            assert not r.spec_section.startswith(_SPEC_URL_PREFIX), (
                f"{r.id} is outside the {SPEC_NAMESPACE} namespace but cites the TODS spec; "
                "cite the ADR that decided it instead"
            )
            assert r.spec_section.startswith("https://"), r.id


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
