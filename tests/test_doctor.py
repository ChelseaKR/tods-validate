"""``doctor``: one honest end-to-end pass composing validate/merge/gtfs-validator/stats."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main
from tods_validate.doctor import (
    GtfsValidatorPayload,
    StageResult,
    _NoticeCounts,
    _read_gtfs_validator_notices,
    _run_gtfs_validator_stage,
    render_doctor_text,
    run_doctor,
)

E201 = str(FIXTURES / "invalid" / "TODS-E201")


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


def test_doctor_valid_feed_runs_all_stages() -> None:
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0, result.output
    assert "== Validate: RAN ==" in result.output
    assert "== Merge: RAN ==" in result.output
    assert "== GTFS-validator:" in result.output
    assert "== Stats: RAN ==" in result.output
    # No java/jar available in the test environment, so gtfs-validator is
    # honestly skipped, not silently passed.
    assert "SKIPPED" in result.output
    assert "GTFS validity NOT checked" in result.output


def test_doctor_no_companion_gtfs_skips_merge_and_validator_honestly() -> None:
    result = invoke("doctor", E201)
    assert result.exit_code == 1  # TODS-E201's error still fails the gate
    assert "== Validate: RAN ==" in result.output
    assert "== Merge: SKIPPED" in result.output
    assert "== GTFS-validator: SKIPPED" in result.output
    assert "== Stats: RAN ==" in result.output
    assert "GTFS validity NOT checked" in result.output
    # Skipping must never look like a pass: the reason is explicit.
    assert "merge stage was skipped" in result.output


def test_doctor_without_java_or_jar_skips_validator_with_honest_label(monkeypatch) -> None:
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    assert result.exit_code == 0, result.output
    assert "== GTFS-validator: SKIPPED" in result.output
    assert "GTFS validity NOT checked" in result.output
    assert "java was not found on PATH" in result.output


def test_doctor_json_has_per_stage_status() -> None:
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "json")
    payload = json.loads(result.output)
    assert payload["validator"] == "tods-validate"
    stages = {s["name"]: s for s in payload["stages"]}
    assert set(stages) == {"validate", "merge", "gtfs-validator", "stats"}
    assert stages["validate"]["status"] == "ran"
    assert stages["merge"]["status"] == "ran"
    assert stages["gtfs-validator"]["status"] == "skipped"
    assert stages["gtfs-validator"]["reason"]
    assert stages["stats"]["status"] == "ran"
    assert "stats" in stages["stats"]


def test_doctor_json_no_gtfs_marks_merge_skipped() -> None:
    result = invoke("doctor", E201, "--format", "json")
    payload = json.loads(result.output)
    stages = {s["name"]: s for s in payload["stages"]}
    assert stages["merge"]["status"] == "skipped"
    assert stages["gtfs-validator"]["status"] == "skipped"
    assert stages["validate"]["errors"] >= 1


def test_doctor_markdown_labels_every_stage() -> None:
    result = invoke("doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--format", "markdown")
    assert "# TODS doctor report:" in result.output
    assert "## Validate: RAN" in result.output
    assert "## Merge: RAN" in result.output
    assert "## GTFS-validator: SKIPPED" in result.output
    assert "## Stats: RAN" in result.output


def test_doctor_missing_path_exits_two() -> None:
    result = invoke("doctor", "no-such-directory")
    assert result.exit_code == 2
    assert "error" in result.output


def test_doctor_valid_feed_alone_no_gtfs_flag() -> None:
    """VALID_TODS has no base GTFS files of its own, only *_supplement.txt,
    so merge still runs (supplement-only additions) even without --gtfs."""
    result = invoke("doctor", str(VALID_TODS))
    assert result.exit_code == 0, result.output
    assert "== Merge: RAN ==" in result.output


# ---------------------------------------------------------------------------
# Rule-set coverage inside the validate stage (#185)
#
# `doctor` honored the "a stage that could not run says so" contract at the
# stage level and dropped it at the rule level, inside the stage that matters
# most. On a TODS-only package the validate stage was marked RAN, printed "No
# problems found." and said nothing about the 16 reference checks -- 9 of them
# ERROR-severity -- that never executed. The gtfs-validator stage beside it was
# honestly marked SKIPPED; a reader had no way to tell those apart.


def test_doctor_text_discloses_the_checks_that_did_not_run() -> None:
    result = invoke("doctor", str(VALID_TODS))
    assert "== Validate: RAN ==" in result.output
    assert "No problems found." in result.output
    assert "Rule-set coverage:" in result.output
    # Named, not just counted: the reference rules that need a companion feed.
    assert "no companion GTFS feed was provided" in result.output
    assert "TODS-E307" in result.output


def test_doctor_markdown_discloses_the_checks_that_did_not_run() -> None:
    result = invoke("doctor", str(VALID_TODS), "--format", "markdown")
    assert "Rule-set coverage:" in result.output
    assert "TODS-E307" in result.output


def test_doctor_json_carries_coverage_on_the_validate_stage() -> None:
    payload = json.loads(invoke("doctor", str(VALID_TODS), "--format", "json").output)
    stage = next(s for s in payload["stages"] if s["name"] == "validate")
    assert stage["status"] == "ran"
    coverage = stage["coverage"]
    assert coverage["total"] == coverage["ran"] + coverage["skipped"]
    assert coverage["skipped"] > 0
    skipped_ids = {rid for ids in coverage["skippedByReason"].values() for rid in ids}
    assert "TODS-E307" in skipped_ids

    # And it agrees with `validate --format json` on the same directory: one
    # number, produced once, not two surfaces disagreeing about the same run.
    from_validate = json.loads(invoke(str(VALID_TODS), "--format", "json").output)["coverage"]
    assert coverage["total"] == from_validate["total"]
    assert coverage["ran"] == from_validate["ran"]
    assert coverage["skipped"] == from_validate["skipped"]


def test_doctor_states_a_complete_run_when_nothing_was_skipped() -> None:
    # The CLI has no --enable, so the opt-in rules are always a requested skip
    # there; drive run_doctor directly to reach a genuinely complete run and
    # confirm the disclosure is a scope statement rather than a warning that
    # only appears when something is wrong.
    report = run_doctor(
        VALID_TODS,
        VALID_GTFS,
        run_gtfs_validator=False,
        enabled=frozenset({"coverage", "advisory"}),
    )
    text = render_doctor_text(report)
    assert "Every applicable check ran" in text
    assert "Checks skipped" not in text


def test_doctor_require_complete_run_fails_a_partial_pass() -> None:
    # The composing command was the one command that could not be gated on a
    # complete run: the flag existed on validate and batch only.
    without = invoke("doctor", str(VALID_TODS))
    assert without.exit_code == 0  # a skip alone does not fail a pass by default

    with_flag = invoke("doctor", str(VALID_TODS), "--require-complete-run")
    assert with_flag.exit_code == 1
    assert "16 check(s) could not run because an input was missing" in with_flag.output
    assert "TODS-E307" in with_flag.output

    # Requested skips alone must not trip it: with a companion feed the only
    # remaining skips are opt-in rules the caller chose to leave off.
    complete = invoke(
        "doctor", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--require-complete-run"
    )
    assert complete.exit_code == 0, complete.output


# ---------------------------------------------------------------------------
# The gtfs-validator stage's own report.json (#147)
#
# `doctor`'s contract is that a stage which could not produce a result says so.
# The stage that reads another tool's output is the one place that contract was
# not enforced: a report.json which parsed as JSON but was shaped some other
# way yielded zero notices and status="ran", rendering identically to a real
# clean gtfs-validator run. These tests drive the stage with a fake java and a
# fake jar so the parsing path -- which no test reached before -- is exercised
# for both a report it understands and every report shape it does not.
# ---------------------------------------------------------------------------


def _stage_reading(report_text: str, tmp_path: Path, monkeypatch) -> StageResult:
    """Run the gtfs-validator stage against a report.json with this content.

    java and the jar are faked, and the "subprocess" writes the given text to
    the report path the stage asked for, so the stage takes exactly the code
    path a real gtfs-validator invocation takes.
    """
    jar = tmp_path / "gtfs-validator.jar"
    jar.write_text("stand-in for the real jar", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")

    def fake_run(cmd, **kwargs):
        report_dir = Path(cmd[cmd.index("-o") + 1])
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.json").write_text(report_text, encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return _run_gtfs_validator_stage(
        tmp_path / "merged",
        run_gtfs_validator=True,
        jar_path=str(jar),
        report_dir=tmp_path / "gtfs-validator-report",
    )


_REAL_SHAPED_REPORT = json.dumps(
    {
        "summary": {"validatorVersion": "8.0.1"},
        "notices": [
            {"code": "invalid_time", "severity": "ERROR", "totalNotices": 3},
            {"code": "unused_shape", "severity": "WARNING", "totalNotices": 2},
            {"code": "unknown_column", "severity": "INFO", "totalNotices": 7},
        ],
    }
)


def test_gtfs_validator_stage_counts_a_report_it_understands(tmp_path, monkeypatch) -> None:
    """The positive control: a well-formed report still runs and still counts."""
    stage = _stage_reading(_REAL_SHAPED_REPORT, tmp_path, monkeypatch)
    assert stage.status == "ran", stage.reason
    payload = stage.payload
    assert isinstance(payload, GtfsValidatorPayload)
    assert (payload.error_notices, payload.warning_notices, payload.info_notices) == (3, 2, 7)
    assert payload.notice_codes == 3


@pytest.mark.parametrize(
    ("report_text", "expected_detail"),
    [
        # #147's repro exactly: valid JSON, not an object.
        ("null", "not an object"),
        ("[]", "not an object"),
        ('"done"', "not an object"),
        # A future gtfs-validator that renames the top-level key.
        ('{"summary": {}}', "no top-level 'notices' array"),
        ('{"notices": {"invalid_time": 3}}', "not an array"),
        # Shapes inside the array. Each one used to be skipped by a bare
        # `continue`, which quietly understates the totals.
        ('{"notices": ["invalid_time"]}', "notices[0] is a string, not an object"),
        ('{"notices": [{"severity": "ERROR"}]}', "no integer 'totalNotices'"),
        (
            '{"notices": [{"severity": "ERROR", "totalNotices": "3"}]}',
            "no integer 'totalNotices'",
        ),
        (
            '{"notices": [{"severity": "SYSTEM_ERROR", "totalNotices": 3}]}',
            "does not know how to count",
        ),
        ('{"notices": [{"totalNotices": 3}]}', "does not know how to count"),
    ],
)
def test_gtfs_validator_report_it_cannot_read_fails_closed(
    report_text: str, expected_detail: str, tmp_path, monkeypatch
) -> None:
    """A report.json this version cannot read is FAILED, never zero notices.

    Zero notices out of an unreadable document renders exactly like a clean
    run ("0 error notice(s), 0 warning notice(s), 0 info notice(s)"), which is
    the misreading `doctor` exists to prevent.
    """
    stage = _stage_reading(report_text, tmp_path, monkeypatch)
    assert stage.status == "failed"
    assert stage.payload is None
    assert stage.reason is not None
    assert "report.json" in stage.reason
    assert expected_detail in stage.reason


def test_unreadable_report_reaches_the_user_as_failed_and_a_nonzero_exit(
    tmp_path, monkeypatch
) -> None:
    """End to end: the rendered report says FAILED and the command exits 1.

    A clean feed with an unreadable gtfs-validator report must not exit 0 --
    that is the difference between "the merged feed is fine" and "nobody
    checked whether the merged feed is fine".
    """
    jar = tmp_path / "gtfs-validator.jar"
    jar.write_text("stand-in for the real jar", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")

    def fake_run(cmd, **kwargs):
        report_dir = Path(cmd[cmd.index("-o") + 1])
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.json").write_text("null", encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = invoke(
        "doctor",
        str(VALID_TODS),
        "--gtfs",
        str(VALID_GTFS),
        "--gtfs-validator-jar",
        str(jar),
    )
    assert "== GTFS-validator: FAILED" in result.output
    assert "0 error notice(s)" not in result.output
    assert result.exit_code == 1, result.output


def test_unreadable_report_is_failed_in_the_json_report(tmp_path, monkeypatch) -> None:
    jar = tmp_path / "gtfs-validator.jar"
    jar.write_text("stand-in for the real jar", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")

    def fake_run(cmd, **kwargs):
        report_dir = Path(cmd[cmd.index("-o") + 1])
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.json").write_text('{"summary": {}}', encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = invoke(
        "doctor",
        str(VALID_TODS),
        "--gtfs",
        str(VALID_GTFS),
        "--gtfs-validator-jar",
        str(jar),
        "--format",
        "json",
    )
    stage = next(s for s in json.loads(result.output)["stages"] if s["name"] == "gtfs-validator")
    assert stage["status"] == "failed"
    assert "no top-level 'notices' array" in stage["reason"]
    # No counts at all, rather than counts that would read as a clean result.
    assert "errorNotices" not in stage


# ---------------------------------------------------------------------------
# The same contract as a property, over generated documents rather than the
# hand-picked ones above: counts come back only for a document whose shape the
# reader fully understood, and when they do they are the document's own totals.
# ---------------------------------------------------------------------------

_json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-50, max_value=50)
    | st.text(max_size=5)
    | st.sampled_from(["ERROR", "WARNING", "INFO", "SYSTEM_ERROR"]),
    lambda children: (
        st.lists(children, max_size=3)
        | st.dictionaries(
            st.sampled_from(["notices", "severity", "totalNotices", "code"]), children
        )
    ),
    max_leaves=6,
)

# Documents shaped like a real report, so the understood branch is reached
# often instead of only by luck.
_notice_like = st.dictionaries(
    st.sampled_from(["severity", "totalNotices", "code"]),
    st.sampled_from(["ERROR", "WARNING", "INFO", "SYSTEM_ERROR", "", None, True])
    | st.integers(min_value=0, max_value=9),
)
_report_like = st.builds(
    lambda notices: {"summary": {}, "notices": notices},
    st.lists(_notice_like | st.none() | st.text(max_size=3), max_size=4),
)


def _is_a_report_this_code_should_understand(document: object) -> bool:
    """The contract, restated independently of the implementation."""
    if not isinstance(document, dict) or "notices" not in document:
        return False
    notices = document["notices"]
    if not isinstance(notices, list):
        return False
    return all(
        isinstance(n, dict)
        and isinstance(n.get("totalNotices"), int)
        and not isinstance(n.get("totalNotices"), bool)
        and n.get("severity") in ("ERROR", "WARNING", "INFO")
        for n in notices
    )


@settings(max_examples=400, derandomize=True, deadline=None)
@given(document=_json_values | _report_like)
def test_counts_come_back_only_for_a_document_whose_shape_was_understood(
    document: object,
) -> None:
    read = _read_gtfs_validator_notices(document)
    if not _is_a_report_this_code_should_understand(document):
        assert isinstance(read, str), f"guessed counts out of {document!r}"
        assert read.strip()
        return

    assert isinstance(read, _NoticeCounts), f"refused a readable report: {document!r}"
    notices = document["notices"]  # type: ignore[index]
    assert read.codes == len(notices)
    for severity, counted in (
        ("ERROR", read.errors),
        ("WARNING", read.warnings),
        ("INFO", read.infos),
    ):
        assert counted == sum(n["totalNotices"] for n in notices if n["severity"] == severity)
