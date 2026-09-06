"""The phase-gate tripwire has to report when it is the tripwire that broke.

`.github/workflows/phase-gates.yml` ran the checker as
`python scripts/check_phase_gates.py > gates.md || true` and then decided
there was news only if `gates.md` was non-empty and carried the report
heading. `scripts/check_phase_gates.py` signals "there is news" by printing
that heading and exiting 1 -- but an uncaught exception exits 1 too, with
nothing on stdout. It raises on an empty recorded gate list, and it lets a
missing or malformed `docs/phase-gates.json` raise as well.

Every one of those arrived as an empty `gates.md`, took the `else` branch, set
`news=false`, filed nothing and reported success. The workflow's own header
says a tripwire that goes quiet when it breaks converts an outage into a green
tick; this is that, in the job that says it.

These tests run the workflow's real shell against stub checkers, so they hold
the step itself rather than a copy of it that can drift.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "phase-gates.yml"
INVOCATION = "python scripts/check_phase_gates.py"
BASH = shutil.which("bash")


def _step_body() -> str:
    """The `run:` block of the checking step, verbatim from the workflow."""
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["phase-gates"]["steps"]
    checking = [s for s in steps if INVOCATION in str(s.get("run", ""))]
    assert checking, "the workflow no longer runs scripts/check_phase_gates.py"
    return str(checking[0]["run"])


def _run(tmp_path: Path, checker: str) -> str:
    """Execute the real step with `checker` standing in for the gate script."""
    stub = tmp_path / "checker.py"
    stub.write_text(checker, encoding="utf-8")
    script = tmp_path / "step.sh"
    script.write_text(_step_body().replace(INVOCATION, f"python3 {stub}"), encoding="utf-8")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    assert BASH is not None, "the workflow step is bash; this test needs a bash to run it"
    subprocess.run(  # noqa: S603 -- resolved binary, fixed argv, no shell
        [BASH, str(script)],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        check=False,
    )
    return output.read_text(encoding="utf-8").strip()


def test_a_checker_that_crashes_is_news(tmp_path: Path) -> None:
    # The regression. A traceback exits 1 with an empty stdout, which used to
    # be indistinguishable from "every gate holds" and filed nothing.
    assert _run(tmp_path, 'raise RuntimeError("docs/phase-gates.json is malformed")') == "news=true"


def test_an_empty_recorded_gate_list_is_news(tmp_path: Path) -> None:
    # compare() raises Unreadable("no gates were compared; the recorded list is
    # empty") precisely so this cannot pass as eight unchanged gates.
    assert (
        _run(tmp_path, 'raise SystemExit("no gates were compared; the recorded list is empty")')
        == "news=true"
    )


def test_the_crash_report_says_no_gate_was_compared(tmp_path: Path) -> None:
    # The filed issue has to say the run read nothing, not imply a gate moved.
    _run(tmp_path, 'raise RuntimeError("boom")')
    report = (tmp_path / "gates.md").read_text(encoding="utf-8")
    assert "Phase gates: attention needed" in report
    assert "no gate was compared" in report
    assert "boom" in report, "the checker's own error has to survive into the report"


def test_a_moved_gate_is_still_news(tmp_path: Path) -> None:
    # The path that already worked must keep working.
    checker = (
        'print("## Phase gates: attention needed")\n'
        "print(\"- **Moved.** ChelseaKR/x#1: was 'OPEN', now 'CLOSED'\")\n"
        "raise SystemExit(1)\n"
    )
    assert _run(tmp_path, checker) == "news=true"


def test_every_gate_holding_is_not_news(tmp_path: Path) -> None:
    # And a clean run must not start filing issues.
    assert _run(tmp_path, 'print("every recorded gate still holds")') == "news=false"


def test_the_step_does_not_discard_the_checker_status(tmp_path: Path) -> None:
    body = _step_body()
    assert f"{INVOCATION} > gates.md || true" not in body, (
        "the checker's exit status is being discarded again, so a crash "
        "reports as a run in which every gate held"
    )
    assert "status" in body, "the step no longer keeps the checker's exit status"


@pytest.mark.parametrize("required", ["gates.md", "gates.err"])
def test_the_report_and_the_error_output_are_uploaded(required: str) -> None:
    # Whatever the run concluded, the evidence has to leave the runner.
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["phase-gates"]["steps"]
    uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert uploads, "the workflow uploads no report"
    assert required in str(uploads[0]["with"]["path"])
