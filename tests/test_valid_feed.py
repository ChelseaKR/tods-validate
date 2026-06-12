"""The valid fixture feed must be completely clean, however it is loaded."""

from conftest import VALID_GTFS, VALID_TODS
from tods_validate.findings import Finding
from tods_validate.runner import run


def _describe(findings: list[Finding]) -> str:
    return "\n".join(f"{f.rule_id}: {f.message}" for f in findings)


def test_valid_feed_with_gtfs_flag(valid_findings: list[Finding]) -> None:
    assert valid_findings == [], _describe(valid_findings)


def test_valid_feed_without_gtfs() -> None:
    _, findings = run(VALID_TODS)
    assert findings == [], _describe(findings)


def test_valid_feed_combined_directory(tmp_path) -> None:
    """TODS and GTFS files shipped together validate against each other."""
    combined = tmp_path / "feed"
    combined.mkdir()
    for source in (VALID_GTFS, VALID_TODS):
        for f in source.iterdir():
            (combined / f.name).write_bytes(f.read_bytes())
    _, findings = run(combined)
    assert findings == [], _describe(findings)
