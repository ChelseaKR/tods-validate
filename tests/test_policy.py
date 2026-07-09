"""GatingPolicy: the exit-code/suppression contract shared by validate, diff,
batch, and testing.assert_feed_valid.

FIX-06's "excellent looks like": a parametrized test proving all four
surfaces give identical pass/fail verdicts for identical findings and policy
inputs, plus golden exit-code assertions (0 pass / 1 gate-fail / 2 usage)
guarding the stated contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate import testing
from tods_validate.baseline import finding_identity
from tods_validate.cli import main
from tods_validate.config import Config
from tods_validate.findings import Finding, Severity
from tods_validate.policy import GatingPolicy

# Single-rule fixtures: exactly one ERROR / one WARNING finding, nothing else,
# so the golden cases below aren't tangled up with unrelated rule noise.
E201 = FIXTURES / "invalid" / "TODS-E201"  # one ERROR
W101 = FIXTURES / "invalid" / "TODS-W101"  # one WARNING


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


# --- unit tests on synthetic findings ---------------------------------------


def test_ignore_withholds_findings_from_kept_and_gating() -> None:
    error = Finding("TODS-E100", Severity.ERROR, "boom")
    warning = Finding("TODS-W100", Severity.WARNING, "meh")
    policy = GatingPolicy(fail_on="error", ignore=frozenset({"TODS-E100"}))
    gate = policy.apply([error, warning])
    assert gate.kept == [warning]
    assert gate.suppressed_ignored == [error]
    assert gate.gating == [warning]
    assert gate.counts == {Severity.WARNING: 1}
    assert gate.failed is False  # the only surviving finding is a warning, fail_on=error


def test_fail_on_warning_gates_on_warnings_too() -> None:
    findings = [Finding("TODS-W100", Severity.WARNING, "meh")]
    policy = GatingPolicy(fail_on="warning", ignore=frozenset())
    assert policy.apply(findings).failed is True


def test_error_always_fails_regardless_of_fail_on() -> None:
    findings = [Finding("TODS-E100", Severity.ERROR, "boom")]
    for fail_on in ("error", "warning", "info"):
        policy = GatingPolicy(fail_on=fail_on, ignore=frozenset())
        assert policy.apply(findings).failed is True


def test_clean_findings_never_fail() -> None:
    policy = GatingPolicy(fail_on="info", ignore=frozenset())
    gate = policy.apply([])
    assert gate.kept == []
    assert gate.gating == []
    assert gate.counts == {}
    assert gate.failed is False


def test_baseline_narrows_gating_but_never_kept() -> None:
    old = Finding("TODS-E100", Severity.ERROR, "boom", file="a.txt", row=2)
    new = Finding("TODS-E100", Severity.ERROR, "boom two", file="a.txt", row=3)
    baseline = {finding_identity(old)}
    policy = GatingPolicy(fail_on="error", ignore=frozenset(), baseline_identities=baseline)
    gate = policy.apply([old, new])
    assert gate.kept == [old, new]  # the report still admits both
    assert gate.gating == [new]  # only the new one gates the exit code
    assert gate.failed is True


def test_baseline_covering_everything_passes_the_gate() -> None:
    finding = Finding("TODS-E100", Severity.ERROR, "boom", file="a.txt", row=2)
    policy = GatingPolicy(
        fail_on="error", ignore=frozenset(), baseline_identities={finding_identity(finding)}
    )
    gate = policy.apply([finding])
    assert gate.kept == [finding]
    assert gate.gating == []
    assert gate.failed is False


def test_from_config_precedence() -> None:
    config = Config(fail_on="warning", ignore=("TODS-W206",))
    # An explicit --fail-on/--ignore on the command line wins over the config file.
    policy = GatingPolicy.from_config(fail_on="error", config=config, ignore_ids=("TODS-E100",))
    assert policy.fail_on == "error"
    assert policy.ignore == frozenset({"TODS-E100", "TODS-W206"})
    # Absent an explicit --fail-on, the config file applies.
    policy = GatingPolicy.from_config(fail_on=None, config=config)
    assert policy.fail_on == "warning"
    # Absent both, "error" is the default and nothing is ignored.
    policy = GatingPolicy.from_config(fail_on=None, config=Config())
    assert policy.fail_on == "error"
    assert policy.ignore == frozenset()


def test_unknown_fail_on_raises() -> None:
    policy = GatingPolicy(fail_on="nope", ignore=frozenset())
    with pytest.raises(ValueError, match="fail_on"):
        policy.apply([])


# --- cross-surface golden verdicts ------------------------------------------


@pytest.mark.parametrize(
    ("fixture", "fail_on", "ignore", "expect_fail"),
    [
        (E201, "error", (), True),
        (E201, "error", ("TODS-E201",), False),
        (W101, "error", (), False),
        (W101, "warning", (), True),
        (W101, "warning", ("TODS-W101",), False),
    ],
    ids=[
        "error-fails-by-default",
        "ignored-error-passes",
        "warning-passes-by-default",
        "fail-on-warning-fails",
        "ignored-warning-passes",
    ],
)
def test_all_surfaces_agree_on_the_same_verdict(
    fixture: Path, fail_on: str, ignore: tuple[str, ...], expect_fail: bool
) -> None:
    """validate, diff, batch, and assert_feed_valid must all reach the same
    pass/fail verdict for the same findings and the same fail_on/ignore."""
    ignore_flags = [flag for rule in ignore for flag in ("--ignore", rule)]

    result = invoke(str(fixture), "--fail-on", fail_on, *ignore_flags)
    assert (result.exit_code == 1) is expect_fail, f"validate: {result.output}"

    # old=the clean reference feed, new=the fixture, so the fixture's one
    # finding is exactly what's "introduced".
    result = invoke("diff", str(VALID_TODS), str(fixture), "--fail-on", fail_on, *ignore_flags)
    assert (result.exit_code == 1) is expect_fail, f"diff: {result.output}"

    result = invoke("batch", str(fixture), "--fail-on", fail_on, *ignore_flags)
    assert (result.exit_code == 1) is expect_fail, f"batch: {result.output}"

    if expect_fail:
        with pytest.raises(AssertionError):
            testing.assert_feed_valid(fixture, fail_on=fail_on, ignore=ignore)
    else:
        testing.assert_feed_valid(fixture, fail_on=fail_on, ignore=ignore)


# --- golden exit codes: 0 pass / 1 gate-fail / 2 usage, per subcommand -----


def test_validate_golden_exit_codes() -> None:
    assert invoke(str(VALID_TODS), "--gtfs", str(VALID_GTFS)).exit_code == 0
    assert invoke(str(E201)).exit_code == 1
    assert invoke("no-such-directory").exit_code == 2


def test_diff_golden_exit_codes() -> None:
    assert invoke("diff", str(VALID_TODS), str(VALID_TODS)).exit_code == 0
    assert invoke("diff", str(VALID_TODS), str(E201)).exit_code == 1
    assert invoke("diff", str(VALID_TODS), "no-such-directory").exit_code == 2


def test_batch_golden_exit_codes() -> None:
    assert invoke("batch", str(VALID_TODS)).exit_code == 0
    assert invoke("batch", str(E201)).exit_code == 1
    # A per-feed load failure fails the roll-up but is not a usage error.
    assert invoke("batch", str(VALID_TODS), "no-such-directory").exit_code == 1


def test_diff_and_batch_honor_config_file(tmp_path: Path) -> None:
    config = tmp_path / "tods-validate.toml"
    config.write_text('ignore = ["TODS-E201"]\n', encoding="utf-8")
    result = invoke("diff", str(VALID_TODS), str(E201), "--config", str(config))
    assert result.exit_code == 0, result.output
    result = invoke("batch", str(E201), "--config", str(config))
    assert result.exit_code == 0, result.output


def test_diff_and_batch_reject_unknown_ignore_id() -> None:
    assert invoke("diff", str(VALID_TODS), str(E201), "--ignore", "TODS-E999").exit_code == 2
    assert invoke("batch", str(E201), "--ignore", "TODS-E999").exit_code == 2
