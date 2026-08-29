"""Everything CI runs on a pull request is either a `make verify` gate or declared.

The Makefile's header makes a promise: "a green `make verify` is a necessary
condition for merge, not a sufficient one", and then lists what CI additionally
runs. That list is what a contributor uses to decide whether a clean local run
means anything. It was written by hand and compared to nothing, so a workflow
added later could reject a tree that `make verify` had just called green, with
no mention anywhere a contributor would look. The VS Code extension job was
exactly that: type-check, `npm audit` and a VSIX package step, on
`pull_request`, absent from both `VERIFY_GATES` and the header's list.

The contract this pins is deliberately weak and therefore keepable: every job
in a workflow triggered by `pull_request` either runs one of the gates
`make verify` runs, or is named in the Makefile header as something CI does on
its own. It does not require CI to be reproducible on a laptop. It requires the
Makefile to stop being wrong about which parts are not.

The workflow files are read with a small regex parser rather than PyYAML, which
is not a declared dependency here (`scripts/check_npm_audit.py` hand-parses
`waivers.yml` for the same reason). Every parse asserts it found something, so
a format change that made the parser see nothing fails instead of passing.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS = _ROOT / ".github" / "workflows"
_MAKEFILE = _ROOT / "Makefile"

# Jobs that intentionally have no `make` equivalent, mapped to the words that
# must appear in the Makefile header so a contributor reading it learns the job
# exists. The reason is the entry's justification; the string is what is
# checked.
_CI_ONLY_JOBS = {
    "action-self-test": "action's self-test",
    "analyze": "CodeQL",
    "semgrep": "Semgrep",
    "zizmor": "zizmor",
    # The baseline is recorded on the CI runner's machine class, so a laptop
    # number is not comparable; `make perf-check` exists but is deliberately not
    # a `verify` gate. The Makefile says so at the `perf-check` recipe.
    "perf": "`perf` job",
    # Path-filtered to editor/vscode/**, so it does not run on most pull
    # requests -- which is why its absence went unnoticed.
    "package": "VS Code extension",
}

# Jobs that run a gate's recipe directly instead of invoking the make target.
# Equivalent, but only while the two stay in step, so the recipe is compared
# rather than assumed.
_DIRECT_GATE_JOBS = {"i18n": "i18n-check"}


def _workflow_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _triggers_on_pull_request(text: str) -> bool:
    header = text.split("\njobs:", 1)[0]
    return re.search(r"^\s{2}pull_request:", header, re.M) is not None


def _jobs_section(text: str) -> str:
    return text.split("\njobs:", 1)[1] if "\njobs:" in text else ""


def _job_bodies(text: str) -> dict[str, str]:
    """{job id: that job's text}, sliced from the match positions themselves.

    Slicing by `str.index` on the whole file looked equivalent and was not: a
    job id that also occurs earlier in the file resolves to the wrong offset, so
    one job's body ran on into the next and picked up its `make` invocation.
    """
    section = _jobs_section(text)
    matches = list(re.finditer(r"^  ([a-zA-Z0-9_-]+):\s*$", section, re.M))
    bodies: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        bodies[match.group(1)] = _without_comments(section[match.start() : end])
    return bodies


def _without_comments(body: str) -> str:
    """Job text with comment lines removed.

    A job's slice ends where the next job's leading comment block begins, and
    those comments describe the job that follows. Leaving them in made the
    `perf` job look as though it ran `make a11y`, because the paragraph
    introducing the accessibility job says so -- a check that matched prose
    instead of commands, which is the failure mode it exists to catch.
    """
    return "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))


def _verify_gates() -> list[str]:
    makefile = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^VERIFY_GATES := (.*?)$\n(?:\t(.*?)$)?", makefile, re.M | re.S)
    assert match is not None, "Makefile no longer declares VERIFY_GATES"
    joined = match.group(0).replace("VERIFY_GATES :=", "").replace("\\", " ")
    gates = [word for word in joined.split() if word and not word.startswith("#")]
    assert len(gates) >= 5, f"parsed only {gates} out of VERIFY_GATES; the parser is wrong"
    return gates


def _gate_recipe_lines(gate: str) -> list[str]:
    """One verify gate's recipe body."""
    makefile = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(gate)}:\n((?:\t.*\n|\n(?=\t))*)", makefile, re.M)
    assert match is not None, f"Makefile has no `{gate}:` target"
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def _pull_request_jobs() -> dict[str, tuple[str, str]]:
    """{job id: (workflow filename, that job's text)} for pull_request workflows."""
    jobs: dict[str, tuple[str, str]] = {}
    for path in sorted(_WORKFLOWS.glob("*.yml")):
        text = _workflow_text(path)
        if not _triggers_on_pull_request(text):
            continue
        bodies = _job_bodies(text)
        assert bodies, f"{path.name} triggers on pull_request but no jobs were parsed"
        for job, body in bodies.items():
            jobs[job] = (path.name, body)
    return jobs


def test_the_parser_found_the_workflows_it_is_checking() -> None:
    """A parse that silently found nothing would make every check below vacuous."""
    jobs = _pull_request_jobs()
    assert len(jobs) >= 10, f"only parsed {sorted(jobs)}; the workflow format changed"
    for expected in ("lint", "test", "secrets", "audit"):
        assert expected in jobs, f"the {expected} job was not parsed out of ci.yml"


def test_every_pull_request_job_is_a_verify_gate_or_a_declared_exception() -> None:
    header = _MAKEFILE.read_text(encoding="utf-8").split("\n.PHONY:", 1)[0]
    gates = _verify_gates()

    undeclared: list[str] = []
    for job, (workflow, body) in sorted(_pull_request_jobs().items()):
        runs_a_gate = any(f"make {gate}" in body for gate in gates)
        if not runs_a_gate and job in _DIRECT_GATE_JOBS:
            gate = _DIRECT_GATE_JOBS[job]
            runs_a_gate = all(line in body for line in _gate_recipe_lines(gate))
            assert runs_a_gate, (
                f"the {job} job is recorded as running `make {gate}`'s command "
                "directly, and no longer does; point it at the make target."
            )
        if runs_a_gate:
            continue
        phrase = _CI_ONLY_JOBS.get(job)
        if phrase is None or phrase not in header:
            undeclared.append(f"{workflow}:{job}")

    assert not undeclared, (
        f"pull-request CI jobs that `make verify` does not cover and the Makefile "
        f"header does not mention: {', '.join(undeclared)}. Either add the gate to "
        "VERIFY_GATES or name the job in the header, so a green `make verify` does "
        "not read as a promise CI will agree."
    )


def test_every_declared_exception_is_still_a_real_job() -> None:
    """The exception list is the hole in the test above, so it is checked too."""
    jobs = set(_pull_request_jobs())
    stale = sorted(job for job in _CI_ONLY_JOBS if job not in jobs)
    assert not stale, (
        f"{', '.join(stale)} is declared as a CI-only job but no pull_request "
        "workflow defines it; drop the entry."
    )
