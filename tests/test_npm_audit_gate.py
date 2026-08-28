"""The npm-audit waiver is bounded to one advisory, and provably so.

waivers.yml accepts GHSA-jmr9-qjv8-65gv, an unpatched symlink path-traversal
issue in extract-zip that reaches this repository only through the pa11y-ci
development toolchain. An exception mechanism nobody has tested is worse than
no exception at all, so these pin what it will *not* accept: a different
advisory, the same advisory on a different package, the same advisory at a
higher severity, and an expired or malformed waiver all still fail the gate.

The reports here are recorded `npm audit --json` shapes, so none of this needs
a network call or an installed node_modules tree.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_npm_audit.py"
WAIVERS = ROOT / "waivers.yml"

WAIVED_ADVISORY = "GHSA-jmr9-qjv8-65gv"
WAIVED_PACKAGE = "extract-zip"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_npm_audit", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _advisory(
    advisory: str, package: str, severity: str = "high", source: int = 1139346
) -> dict[str, Any]:
    return {
        "source": source,
        "name": package,
        "dependency": package,
        "title": f"{package} test advisory",
        "url": f"https://github.com/advisories/{advisory}",
        "severity": severity,
        "range": "*",
    }


def _report(*advisories: dict[str, Any]) -> dict[str, Any]:
    """Build an `npm audit --json` report carrying the given advisories.

    Mirrors npm's real shape: the package that carries the advisory has an
    object-shaped `via`, and a downstream package just names its parent.
    """

    vulnerabilities: dict[str, Any] = {}
    severities = {"info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0}
    for via in advisories:
        package = str(via["name"])
        vulnerabilities[package] = {
            "name": package,
            "severity": via["severity"],
            "isDirect": False,
            "via": [via],
            "effects": [f"depends-on-{package}"],
            "range": "*",
            "nodes": [f"node_modules/{package}"],
            "fixAvailable": {"name": "pa11y-ci", "version": "3.1.0", "isSemVerMajor": True},
        }
        vulnerabilities[f"depends-on-{package}"] = {
            "name": f"depends-on-{package}",
            "severity": via["severity"],
            "isDirect": True,
            "via": [package],
            "effects": [],
            "range": "*",
            "nodes": [f"node_modules/depends-on-{package}"],
            "fixAvailable": {"name": "pa11y-ci", "version": "3.1.0", "isSemVerMajor": True},
        }
        severities[str(via["severity"])] += 2
    return {
        "auditReportVersion": 2,
        "vulnerabilities": vulnerabilities,
        "metadata": {
            "vulnerabilities": {**severities, "total": sum(severities.values())},
            "dependencies": {"prod": 1, "dev": 162, "total": 162},
        },
    }


def _run(tmp_path: Path, report: dict[str, Any], waivers: Path = WAIVERS) -> int:
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return int(
        _gate().main(
            ["--audit-json", str(path), "--waivers", str(waivers), "--repo", "tods-validate"]
        )
    )


def test_the_committed_waiver_accepts_the_advisory_it_names(tmp_path: Path) -> None:
    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))
    assert _run(tmp_path, report) == 0


def test_a_different_high_advisory_still_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The point of the whole exercise: the waiver is not an allowlist."""

    report = _report(_advisory("GHSA-aaaa-bbbb-cccc", "tar-fs"))
    assert _run(tmp_path, report) == 1
    assert "GHSA-AAAA-BBBB-CCCC" in capsys.readouterr().err


def test_a_different_advisory_alongside_the_waived_one_still_fails(tmp_path: Path) -> None:
    report = _report(
        _advisory(WAIVED_ADVISORY, WAIVED_PACKAGE),
        _advisory("GHSA-aaaa-bbbb-cccc", "tar-fs", source=222222),
    )
    assert _run(tmp_path, report) == 1


def test_a_second_advisory_in_the_same_package_still_fails(tmp_path: Path) -> None:
    """Scoped to the advisory, not to extract-zip."""

    report = _report(_advisory("GHSA-dddd-eeee-ffff", WAIVED_PACKAGE))
    assert _run(tmp_path, report) == 1


def test_the_waived_advisory_on_another_package_still_fails(tmp_path: Path) -> None:
    report = _report(_advisory(WAIVED_ADVISORY, "some-other-package"))
    assert _run(tmp_path, report) == 1


def test_the_waived_advisory_escalated_to_critical_still_fails(tmp_path: Path) -> None:
    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE, severity="critical"))
    assert _run(tmp_path, report) == 1


def test_a_moderate_advisory_does_not_fail_the_high_floor(tmp_path: Path) -> None:
    report = _report(_advisory("GHSA-aaaa-bbbb-cccc", "tar-fs", severity="moderate"))
    assert _run(tmp_path, report) == 0


def test_an_expired_waiver_accepts_nothing(tmp_path: Path) -> None:
    stale = tmp_path / "waivers.yml"
    text = WAIVERS.read_text(encoding="utf-8")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    stale.write_text(text.replace("expires: 2026-11-15", f"expires: {yesterday}"), encoding="utf-8")
    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))
    assert _run(tmp_path, report, waivers=stale) == 1


def test_a_waiver_missing_a_required_field_accepts_nothing(tmp_path: Path) -> None:
    broken = tmp_path / "waivers.yml"
    text = WAIVERS.read_text(encoding="utf-8")
    broken.write_text(text.replace("    owner: chelseakr\n", ""), encoding="utf-8")
    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))
    assert _run(tmp_path, report, waivers=broken) == 1


def test_a_report_shape_the_gate_cannot_read_fails_closed(tmp_path: Path) -> None:
    """npm says there are HIGH findings; the gate cannot see them. Fail."""

    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))
    report["vulnerabilities"] = {"opaque": {"severity": "high", "via": ["something"]}}
    assert _run(tmp_path, report) == 1


def test_the_committed_registry_is_well_formed() -> None:
    gate = _gate()
    waivers, problems = gate.npm_audit_waivers(
        WAIVERS.read_text(encoding="utf-8"), "tods-validate", date.today()
    )
    assert problems == []
    assert set(waivers) == {WAIVED_ADVISORY.upper()}
    waiver = waivers[WAIVED_ADVISORY.upper()]
    assert waiver["package"] == WAIVED_PACKAGE
    assert waiver["severity"] == "high"
    # The record has to carry the facts the acceptance rests on, not just an id.
    for claim in ("2.0.1", "pa11y-ci", "2026-08-15"):
        assert claim in waiver["reason"] + waiver["version"] + waiver["dependency_path"]


# ---------------------------------------------------------------------------
# A report this gate cannot read is a failure, not a zero.
#
# The gate's own docstring promises it fails on "an `npm audit` report this
# gate cannot parse, or a count of HIGH/CRITICAL findings that the parsed
# advisories do not account for". The cross-check that keeps that promise is
# guarded by `blocking_total(report) > 0`, and `blocking_total` used to answer
# 0 for a report whose counts it could not read -- so a report that degraded
# in both halves at once disarmed the guard and passed.
# ---------------------------------------------------------------------------


def _clean_report() -> dict[str, Any]:
    """A report with nothing wrong in it, so only the damage under test differs."""
    return _report()


def test_a_clean_report_still_passes(tmp_path: Path) -> None:
    """The positive control for everything below."""
    assert _run(tmp_path, _clean_report()) == 0


@pytest.mark.parametrize(
    ("damage", "expected"),
    [
        pytest.param({}, "metadata.vulnerabilities", id="metadata-missing"),
        pytest.param({"metadata": []}, "metadata.vulnerabilities", id="metadata-not-an-object"),
        pytest.param(
            {"metadata": {"vulnerabilities": []}},
            "metadata.vulnerabilities",
            id="counts-not-an-object",
        ),
        pytest.param(
            {"metadata": {"vulnerabilities": {"high": None, "critical": 0}}},
            "metadata.vulnerabilities",
            id="count-is-null",
        ),
        pytest.param(
            {"metadata": {"vulnerabilities": {"high": "0", "critical": 0}}},
            "metadata.vulnerabilities",
            id="count-is-a-string",
        ),
        pytest.param(
            {"metadata": {"vulnerabilities": {"critical": 0}}},
            "metadata.vulnerabilities",
            id="a-blocking-severity-is-absent",
        ),
        pytest.param(
            {"vulnerabilities": []},
            "no readable 'vulnerabilities' object",
            id="vulnerabilities-not-an-object",
        ),
    ],
)
def test_a_report_whose_counts_cannot_be_read_fails_closed(
    damage: dict[str, Any],
    expected: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    report = _clean_report()
    if damage:
        report.update(damage)
    else:  # the metadata key removed entirely
        report.pop("metadata")

    assert _run(tmp_path, report) == 1
    assert expected in capsys.readouterr().err


def test_both_halves_degrading_at_once_still_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The shape that used to slip through.

    `vulnerabilities` as a list makes the advisory parse empty; no `metadata`
    made the reported count read as 0. Neither half could see the other was
    broken, so the gate reported a clean audit.
    """
    report = {"auditReportVersion": 2, "vulnerabilities": []}
    assert _run(tmp_path, report) == 1
    err = capsys.readouterr().err
    assert "refusing to pass a report it does not understand" in err


def test_blocking_total_separates_unreadable_from_zero() -> None:
    gate = _gate()
    assert gate.blocking_total(_clean_report()) == 0
    assert gate.blocking_total(_report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))) == 2
    assert gate.blocking_total({"metadata": {"vulnerabilities": {"high": 1}}}) is None
    assert gate.blocking_total({}) is None
