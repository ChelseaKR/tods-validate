"""Handoff records (#197).

The three "Done when" criteria of #197 come first. The skipped-check count in
the second is derived from the registry, not written down: the issue says "the
16 skipped checks", which was true when it was filed and stopped being true
the same day, when OPS-W001 became the seventeenth rule that needs a companion.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import jsonschema
import pytest
from click.testing import CliRunner

from conftest import FIXTURES, VALID_GTFS, VALID_TODS
from tods_validate.cli import main
from tods_validate.handoff import (
    ACCEPT,
    REJECT,
    SIGNATURE_NAMESPACE,
    HandoffSettings,
    build_record,
    render_record,
    sign_record,
    verify_record,
    verify_signature,
)
from tods_validate.rules import all_rules

ROOT = Path(__file__).parent.parent
SCHEMA = json.loads((ROOT / "docs" / "handoff.schema.json").read_text(encoding="utf-8"))
REPORT_SCHEMA = json.loads((ROOT / "docs" / "report.schema.json").read_text(encoding="utf-8"))
INGEST_READY = HandoffSettings(
    profile="ingest-ready",
    fail_on="warning",
    enable=("advisory", "coverage"),
    ignore=(),
    spec_version="2.1.0",
    encoding=None,
    severity_remap=(),
    max_implied_speed_kph=None,
)


def _create(tmp_path: Path, *args: str) -> tuple[int, dict[str, object], Path]:
    out = tmp_path / "handoff.json"
    result = CliRunner().invoke(main, ["handoff", *args, "--out", str(out)])
    assert out.is_file(), result.output
    return result.exit_code, json.loads(out.read_text(encoding="utf-8")), out


def _copy(source: Path, dest: Path) -> Path:
    shutil.copytree(source, dest)
    return dest


# --- #197 "Done when" ---------------------------------------------------------


def test_a_record_verifies_against_its_bytes_and_not_against_one_changed_row(
    tmp_path: Path,
) -> None:
    """Done when 1."""
    tods = _copy(VALID_TODS, tmp_path / "tods")
    code, record, out = _create(
        tmp_path, str(tods), "--gtfs", str(VALID_GTFS), "--profile", "ingest-ready"
    )
    assert code == 0
    assert record["decision"] == ACCEPT
    same = verify_record(out, tods, VALID_GTFS)
    assert same.exit_code == 0, same.lines
    run_events = tods / "run_events.txt"
    lines = run_events.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[2] = lines[2].replace("09:35:00", "09:36:00")
    run_events.write_text("".join(lines), encoding="utf-8")
    changed = verify_record(out, tods, VALID_GTFS)
    assert changed.exit_code == 2
    assert changed.lines[0].startswith("hashes differ")
    assert any("package: run_events.txt differs" in line for line in changed.lines)


def test_a_record_without_a_companion_shows_every_skipped_check_and_rejects(
    tmp_path: Path,
) -> None:
    """Done when 2. The count is the registry's, today 17."""
    code, record, _ = _create(tmp_path, str(VALID_TODS), "--profile", "ingest-ready")
    needs_gtfs = sorted(r.id for r in all_rules() if r.needs_gtfs)
    coverage = record["coverage"]
    assert isinstance(coverage, dict)
    assert sorted(coverage["skippedByReason"]["skipped:needs_gtfs"]) == needs_gtfs
    assert record["decision"] == REJECT
    assert record["decisionBasis"] == {"blockingRules": [], "checksNotRun": needs_gtfs}
    assert code == 1
    # The findings alone would have accepted it: nothing reached "warning".
    assert record["summary"] == {"errors": 0, "warnings": 0, "infos": 0}


def test_a_record_whose_decision_was_changed_does_not_verify(tmp_path: Path) -> None:
    """Done when 3: same hashes, different decision."""
    _, record, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    record["decision"] = REJECT
    out.write_text(render_record(record), encoding="utf-8")
    result = verify_record(out, VALID_TODS, VALID_GTFS)
    assert result.exit_code == 1
    assert "decision: the record says 'reject'; these bytes give 'accept'" in "\n".join(
        result.lines
    )


# --- what the record is ---------------------------------------------------------


def test_the_record_is_a_function_of_its_inputs(tmp_path: Path) -> None:
    first = render_record(build_record(VALID_TODS, VALID_GTFS, INGEST_READY))
    second = render_record(build_record(VALID_TODS, VALID_GTFS, INGEST_READY))
    assert first == second
    assert 'Z"' not in first  # no timestamp anywhere


def test_the_record_matches_its_schema_and_embeds_the_report_coverage(tmp_path: Path) -> None:
    for gtfs in (VALID_GTFS, None):
        record = build_record(VALID_TODS, gtfs, INGEST_READY)
        jsonschema.validate(record, SCHEMA)
        jsonschema.validate(record["coverage"], REPORT_SCHEMA["properties"]["coverage"])


def test_every_file_is_hashed_and_the_merge_is_recorded(tmp_path: Path) -> None:
    record = build_record(VALID_TODS, VALID_GTFS, INGEST_READY)
    inputs = record["inputs"]
    assert isinstance(inputs, dict)
    names = [entry["name"] for entry in inputs["package"]["files"]]
    assert names == sorted(p.name for p in VALID_TODS.iterdir() if p.is_file())
    assert inputs["companion"]["source"] == "flag"
    assert [e["name"] for e in inputs["companion"]["files"]] == sorted(
        p.name for p in VALID_GTFS.iterdir() if p.is_file()
    )
    merge = record["merge"]
    assert isinstance(merge, dict)
    assert merge["status"] == "produced"
    assert "trips.txt" in merge["files"]
    # No companion of its own, and no GTFS files beside it: still a merge,
    # because the supplement files alone make one. I expected "not-produced"
    # here and merge_feeds is right: the record says what was actually built.
    no_companion = build_record(VALID_TODS, None, INGEST_READY)
    assert no_companion["inputs"]["companion"] is None
    assert no_companion["merge"]["status"] == "produced"


def test_a_package_with_nothing_to_merge_records_why(tmp_path: Path) -> None:
    bare = tmp_path / "tods"
    bare.mkdir()
    shutil.copy(VALID_TODS / "run_events.txt", bare / "run_events.txt")
    merge = build_record(bare, None, INGEST_READY)["merge"]
    assert isinstance(merge, dict)
    assert merge["status"] == "not-produced"
    assert "nothing to merge" in str(merge["reason"])


def test_a_package_carrying_its_own_gtfs_is_its_own_companion(tmp_path: Path) -> None:
    # The third companion shape: no --gtfs, but GTFS files sit beside the TODS
    # ones, so the runner resolves references against them. Their hashes are
    # already under "package", so the record does not repeat them.
    feed = FIXTURES / "invalid" / "TODS-E309"
    record = build_record(feed, None, INGEST_READY)
    inputs = record["inputs"]
    assert isinstance(inputs, dict)
    assert inputs["companion"] == {"source": "package"}
    out = tmp_path / "handoff.json"
    out.write_text(render_record(record), encoding="utf-8")
    assert verify_record(out, feed, None).exit_code == 0


def test_the_decision_names_the_rules_that_block_it(tmp_path: Path) -> None:
    record = build_record(FIXTURES / "invalid" / "TODS-E307", None, INGEST_READY)
    assert record["decision"] == REJECT
    assert "TODS-E307" in record["decisionBasis"]["blockingRules"]


def test_settings_are_recorded_resolved_not_by_profile_name_alone(tmp_path: Path) -> None:
    _, record, _ = _create(
        tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--profile", "ingest-ready"
    )
    assert record["settings"] == {
        "profile": "ingest-ready",
        "failOn": "warning",
        "enable": ["advisory", "coverage"],
        "ignore": [],
        "specVersion": "2.1.0",
        "encoding": None,
        "severityRemap": {},
        "maxImpliedSpeedKph": None,
    }


# --- verify: every way it can fail --------------------------------------------------


def test_a_record_that_is_not_json_cannot_be_checked(tmp_path: Path) -> None:
    record = tmp_path / "handoff.json"
    record.write_text("{not json", encoding="utf-8")
    result = verify_record(record, VALID_TODS, VALID_GTFS)
    assert result.exit_code == 2
    assert "could not be read" in result.lines[0]


def test_a_record_of_another_major_version_cannot_be_checked(tmp_path: Path) -> None:
    _, record, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    record["handoffVersion"] = "2.0.0"
    out.write_text(render_record(record), encoding="utf-8")
    result = verify_record(out, VALID_TODS, VALID_GTFS)
    assert result.exit_code == 2
    assert "is not a 1.x record" in result.lines[0]


def test_an_added_file_is_a_difference_in_the_bytes(tmp_path: Path) -> None:
    tods = _copy(VALID_TODS, tmp_path / "tods")
    _, _, out = _create(tmp_path, str(tods), "--gtfs", str(VALID_GTFS))
    (tods / "notes.txt").write_text("hello\n", encoding="utf-8")
    result = verify_record(out, tods, VALID_GTFS)
    assert result.exit_code == 2
    assert "package: notes.txt was given and is not in the record" in result.lines


@pytest.mark.parametrize("made_with_companion", [True, False])
def test_a_companion_given_at_one_end_only_is_a_difference(
    tmp_path: Path, made_with_companion: bool
) -> None:
    args = (
        [str(VALID_TODS), "--gtfs", str(VALID_GTFS)] if made_with_companion else [str(VALID_TODS)]
    )
    _, _, out = _create(tmp_path, *args)
    result = verify_record(out, VALID_TODS, None if made_with_companion else VALID_GTFS)
    assert result.exit_code == 2
    assert any(line.startswith("companion: the record was made with") for line in result.lines)


def test_an_edited_coverage_block_does_not_verify_even_with_the_same_decision(
    tmp_path: Path,
) -> None:
    # A record whose decision was left alone but whose manifest was edited to
    # hide what did not run is as wrong as one whose decision was flipped.
    _, record, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    coverage = record["coverage"]
    assert isinstance(coverage, dict)
    coverage["skipped"] = 0
    out.write_text(render_record(record), encoding="utf-8")
    result = verify_record(out, VALID_TODS, VALID_GTFS)
    assert result.exit_code == 1
    assert "coverage" in result.lines[0]


# --- the command line -----------------------------------------------------------------


def test_handoff_feed_and_handoff_create_feed_are_the_same_command(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    CliRunner().invoke(
        main, ["handoff", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--out", str(a)]
    )
    CliRunner().invoke(
        main, ["handoff", "create", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--out", str(b)]
    )
    assert a.read_bytes() == b.read_bytes()


def test_verify_on_the_command_line_uses_the_documented_exit_codes(tmp_path: Path) -> None:
    _, record, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    args = ["handoff", "verify", str(out), str(VALID_TODS), "--gtfs", str(VALID_GTFS)]
    assert CliRunner().invoke(main, args).exit_code == 0
    record["decision"] = REJECT
    out.write_text(render_record(record), encoding="utf-8")
    assert CliRunner().invoke(main, args).exit_code == 1


def test_verify_wants_the_signers_file_and_the_identity_together(tmp_path: Path) -> None:
    _, _, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    result = CliRunner().invoke(
        main, ["handoff", "verify", str(out), str(VALID_TODS), "--signer", "someone"]
    )
    assert result.exit_code == 2
    assert "go together" in result.output


# --- the detached signature, with a throwaway key and nothing else ----------------------

ssh_keygen = shutil.which("ssh-keygen")
needs_ssh_keygen = pytest.mark.skipif(ssh_keygen is None, reason="ssh-keygen is not installed")


def _throwaway_key(tmp_path: Path, name: str = "tester") -> tuple[Path, Path]:
    key = tmp_path / f"{name}_ed25519"
    subprocess.run(  # noqa: S603 - fixed argv
        [ssh_keygen or "ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(key)],
        check=True,
    )
    public = key.with_suffix(".pub").read_text(encoding="utf-8").split()
    signers = tmp_path / f"{name}_allowed_signers"
    signers.write_text(
        f'{name} namespaces="{SIGNATURE_NAMESPACE}" {public[0]} {public[1]}\n', encoding="utf-8"
    )
    return key, signers


@needs_ssh_keygen
def test_a_signed_record_verifies_and_an_edited_one_does_not(tmp_path: Path) -> None:
    key, signers = _throwaway_key(tmp_path)
    _, record, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    sign_record(out, key)
    assert verify_signature(out, signers, "tester") is None
    assert verify_signature(out, signers, "someone-else") is not None
    record["decision"] = REJECT
    out.write_text(render_record(record), encoding="utf-8")
    assert verify_signature(out, signers, "tester") is not None


@needs_ssh_keygen
def test_a_signature_in_another_namespace_is_refused(tmp_path: Path) -> None:
    # A release-tag signature (namespace "git") must not pass as a handoff one.
    key, signers = _throwaway_key(tmp_path)
    _, _, out = _create(tmp_path, str(VALID_TODS), "--gtfs", str(VALID_GTFS))
    subprocess.run(  # noqa: S603 - fixed argv
        [ssh_keygen or "ssh-keygen", "-Y", "sign", "-q", "-f", str(key), "-n", "git", str(out)],
        check=True,
        capture_output=True,
    )
    assert verify_signature(out, signers, "tester") is not None


@needs_ssh_keygen
def test_verify_on_the_command_line_checks_a_requested_signature_first(tmp_path: Path) -> None:
    key, signers = _throwaway_key(tmp_path)
    out = tmp_path / "handoff.json"
    created = CliRunner().invoke(
        main,
        ["handoff", str(VALID_TODS), "--gtfs", str(VALID_GTFS), "--out", str(out)]
        + ["--sign-key", str(key)],
    )
    assert created.exit_code == 0, created.output
    base = ["handoff", "verify", str(out), str(VALID_TODS), "--gtfs", str(VALID_GTFS)]
    good = CliRunner().invoke(
        main, [*base, "--allowed-signers", str(signers), "--signer", "tester"]
    )
    assert good.exit_code == 0, good.output
    bad = CliRunner().invoke(
        main, [*base, "--allowed-signers", str(signers), "--signer", "mallory"]
    )
    assert bad.exit_code == 2
    assert "signature does not verify" in bad.output
