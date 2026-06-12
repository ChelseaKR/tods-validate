from pathlib import Path

import pytest

from tods_validate.findings import Finding
from tods_validate.runner import run

FIXTURES = Path(__file__).parent / "fixtures"
VALID_TODS = FIXTURES / "valid" / "tods"
VALID_GTFS = FIXTURES / "valid" / "gtfs"


def run_invalid_fixture(rule_id: str) -> list[Finding]:
    """Validate the broken fixture dedicated to one rule.

    Fixtures that need a companion GTFS feed keep the GTFS files in the same
    directory; the runner picks them up automatically.
    """
    path = FIXTURES / "invalid" / rule_id
    assert path.is_dir(), f"missing fixture directory for {rule_id}"
    _, findings = run(path)
    return findings


def rule_ids(findings: list[Finding]) -> set[str]:
    return {f.rule_id for f in findings}


@pytest.fixture(scope="session")
def valid_findings() -> list[Finding]:
    _, findings = run(VALID_TODS, VALID_GTFS)
    return findings
