"""The npm-audit waiver is bounded to one advisory, and provably so.

waivers.yml accepts GHSA-jmr9-qjv8-65gv, an unpatched symlink path-traversal
issue in extract-zip that reaches this repository only through the pa11y-ci
development toolchain. An exception mechanism nobody has tested is worse than
no exception at all, so these pin what it will *not* accept: a different
advisory, the same advisory on a different package, the same advisory at a
higher severity, and an expired or malformed waiver all still fail the gate.

The second half of the module pins *what the gate looks at*, which is a
separate question from what it accepts. `npm audit` reads the lockfile in its
working directory, so a gate that ran it once at the repository root reported
on one dependency tree and was silent about `editor/vscode/`, where a HIGH
advisory sat unseen. The tests here hold the project walk to the lockfiles
this repository actually commits, so narrowing it back to the root fails.

The reports here are recorded `npm audit --json` shapes, so none of this needs
a network call or an installed node_modules tree.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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

# The two npm projects this repository commits today. Named rather than
# derived, because the failure this module exists to prevent is the walk
# quietly returning fewer than there are, and a derived expectation would
# shrink with it.
ROOT_PROJECT = "."
EXTENSION_PROJECT = "editor/vscode"


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
    # Keyed by (npm project, advisory): the same advisory in two dependency
    # trees is two decisions, and one waiver must not answer for both.
    assert set(waivers) == {(ROOT_PROJECT, WAIVED_ADVISORY.upper())}
    waiver = waivers[(ROOT_PROJECT, WAIVED_ADVISORY.upper())]
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


# ---------------------------------------------------------------------------
# Which dependency trees the gate reads.
#
# `npm audit` reads the lockfile in its working directory and nothing else, so
# running it once at the repository root is a report about one project. This
# repository commits two, and on 2026-09-10 the second one carried a live HIGH
# advisory (GHSA-2883-xcg3-v3hh in js-yaml, through @vscode/vsce) that this
# gate could not see. Its own audit lived in a workflow path-filtered to
# `editor/vscode/**`, which runs when the lockfile changes and not when an
# advisory is published against a lockfile that has not.
# ---------------------------------------------------------------------------


def _tracked_lockfile_projects() -> set[str]:
    """The npm projects git says this repository commits.

    An oracle independent of the walk under test: `git ls-files` knows nothing
    about the prune list, so a walk that lost a directory disagrees with it.
    """

    git = shutil.which("git")
    assert git is not None, "git is needed to cross-check the project walk"
    listing = subprocess.run(  # noqa: S603 - fixed argv, resolved binary, no shell
        [git, "-C", str(ROOT), "ls-files", "--", "*package-lock.json"],
        capture_output=True,
        text=True,
        check=True,
    )
    projects = set()
    for line in listing.stdout.splitlines():
        if not line.strip():
            continue
        parent = Path(line).parent.as_posix()
        projects.add(parent if parent != "." else ROOT_PROJECT)
    return projects


def test_the_walk_finds_every_npm_project_this_repository_commits() -> None:
    """The floor. A walk that stopped matching returns [] and fails here."""

    gate = _gate()
    found = gate.npm_projects(ROOT)

    tracked = _tracked_lockfile_projects()
    assert tracked, "git found no committed package-lock.json; this oracle is broken"
    assert tracked <= set(found), (
        f"committed npm project(s) the gate does not audit: {sorted(tracked - set(found))}"
    )

    # Named as well as derived: the extension tree is the one this widening was
    # for, and a rename that took it out of both the walk and the oracle at
    # once would leave the subset check above green.
    assert ROOT_PROJECT in found
    assert EXTENSION_PROJECT in found
    assert found[0] == ROOT_PROJECT, "the root project is reported first"


def test_the_walk_ignores_lockfiles_belonging_to_installed_dependencies(
    tmp_path: Path,
) -> None:
    """`node_modules` is the difference between two projects and hundreds."""

    gate = _gate()
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    for pruned in ("node_modules/some-dep", "dist", ".venv/lib"):
        nested = tmp_path / pruned
        nested.mkdir(parents=True)
        (nested / "package-lock.json").write_text("{}", encoding="utf-8")
    real = tmp_path / "editor" / "vscode"
    real.mkdir(parents=True)
    (real / "package-lock.json").write_text("{}", encoding="utf-8")

    assert gate.npm_projects(tmp_path) == [ROOT_PROJECT, "editor/vscode"]


def test_a_tree_with_no_lockfile_fails_instead_of_reporting_a_clean_audit(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """An empty walk is a broken reader, not a repository without dependencies.

    This is the vacuity case for the widening itself: adjudicating zero
    projects finds zero advisories, which prints exactly like a clean run.
    """

    gate = _gate()
    assert (
        gate.main(["--root", str(tmp_path), "--waivers", str(WAIVERS), "--repo", "tods-validate"])
        == 1
    )
    assert "refusing to report a clean audit over nothing" in capsys.readouterr().err


def test_the_run_says_how_many_projects_it_adjudicated(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Both numbers on the line, so a covered project cannot be dropped quietly."""

    assert _run(tmp_path, _clean_report()) == 0
    assert "adjudicated 1 of 1 npm project(s) [.]" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# A waiver is scoped to the project it was written about.
# ---------------------------------------------------------------------------


def _scoped_registry(tmp_path: Path, tree: str | None) -> Path:
    """The committed registry with WVR-001 re-scoped to `tree` (or left at root)."""

    text = WAIVERS.read_text(encoding="utf-8")
    if tree is not None:
        text = text.replace("    kind: npm-audit\n", f"    kind: npm-audit\n    tree: {tree}\n", 1)
    path = tmp_path / "waivers.yml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_root_waiver_does_not_accept_the_same_advisory_in_another_project(
    tmp_path: Path,
) -> None:
    """The reason `tree` exists.

    WVR-001's justification is entirely about the accessibility toolchain --
    "five levels down from pa11y-ci", "the npm devDependencies set". None of
    that is a statement about the VS Code extension's dependency tree, so the
    same advisory arriving there is an unreviewed finding.
    """

    gate = _gate()
    waivers, problems = gate.npm_audit_waivers(
        WAIVERS.read_text(encoding="utf-8"), "tods-validate", date.today()
    )
    assert problems == []
    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))

    at_root = gate.adjudicate(report, waivers, ROOT_PROJECT)
    assert at_root[0] == []
    assert at_root[1], "the waiver accepts the advisory in the project it names"

    elsewhere = gate.adjudicate(report, waivers, EXTENSION_PROJECT)
    assert elsewhere[1] == []
    assert any("no waiver" in failure for failure in elsewhere[0])


def test_a_waiver_can_be_scoped_to_a_project_other_than_the_root(tmp_path: Path) -> None:
    """And the scoping is not one-way: a `tree:` entry accepts in that tree."""

    gate = _gate()
    registry = _scoped_registry(tmp_path, EXTENSION_PROJECT)
    waivers, problems = gate.npm_audit_waivers(
        registry.read_text(encoding="utf-8"), "tods-validate", date.today()
    )
    assert problems == []
    assert set(waivers) == {(EXTENSION_PROJECT, WAIVED_ADVISORY.upper())}

    report = _report(_advisory(WAIVED_ADVISORY, WAIVED_PACKAGE))
    assert gate.adjudicate(report, waivers, EXTENSION_PROJECT)[0] == []
    assert gate.adjudicate(report, waivers, ROOT_PROJECT)[1] == []


def test_a_waiver_naming_a_directory_that_is_not_an_npm_project_is_a_problem(
    tmp_path: Path,
) -> None:
    """A waiver must not outlive the project whose lockfile it describes."""

    gate = _gate()
    registry = _scoped_registry(tmp_path, "editor/atom")
    waivers, problems = gate.npm_audit_waivers(
        registry.read_text(encoding="utf-8"),
        "tods-validate",
        date.today(),
        [ROOT_PROJECT, EXTENSION_PROJECT],
    )
    assert waivers == {}
    assert any("editor/atom" in problem for problem in problems)


def test_the_committed_registry_names_only_projects_that_exist() -> None:
    """Run the tree validation against the real repository, not a fixture."""

    gate = _gate()
    _, problems = gate.npm_audit_waivers(
        WAIVERS.read_text(encoding="utf-8"),
        "tods-validate",
        date.today(),
        gate.npm_projects(ROOT),
    )
    assert problems == []


def test_the_coverage_line_counts_projects_adjudicated_not_projects_found() -> None:
    """The two numbers have to be able to disagree, or one of them is decoration.

    A run that found two projects and got a report out of one has examined
    half of what it named. Printing `2 of 2` there is this portfolio's own
    defect -- a failed read published as a measurement -- inside the line
    written to prevent it.
    """

    gate = _gate()
    both = [ROOT_PROJECT, EXTENSION_PROJECT]
    assert gate.coverage_line(both, both) == (
        "npm audit: adjudicated 2 of 2 npm project(s) [., editor/vscode]"
    )
    assert gate.coverage_line([ROOT_PROJECT], both) == (
        "npm audit: adjudicated 1 of 2 npm project(s) [.]"
    )
    assert gate.coverage_line([], both) == "npm audit: adjudicated 0 of 2 npm project(s) [none]"


def test_a_project_whose_audit_cannot_be_read_is_not_counted_as_examined(
    tmp_path: Path,
) -> None:
    """Both directions, because a reader that examines nothing satisfies one."""

    gate = _gate()
    both = [ROOT_PROJECT, EXTENSION_PROJECT]

    report = tmp_path / "audit.json"
    report.write_text(json.dumps(_clean_report()), encoding="utf-8")
    failures, _, _, audited = gate._audit_projects(both, {}, tmp_path, report)
    assert failures == []
    assert audited == both

    missing = tmp_path / "nowhere.json"
    failures, _, _, audited = gate._audit_projects(both, {}, tmp_path, missing)
    assert audited == []
    assert len(failures) == 2
    assert all("nowhere.json" in failure for failure in failures)
