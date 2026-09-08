"""Every trigger that can publish to PyPI carries the same verification.

`.github/workflows/pypi-publish.yml` runs on two events, and both of them
reach the `publish` job -- it declares no trigger condition. The verification
around it did not follow. `verify` was called with an empty `tag` outside a
release event, which silently disabled the two checks in `verify.yml` that are
gated on `inputs.tag != ''` (version consistency, and that the tag is an
annotated tag whose SSH signature verifies against the committed
`allowed_signers`), and `verify-published` -- the job that re-downloads what
actually landed on PyPI and checks its provenance -- carried
`if: github.event_name == 'release'`.

That is not a hypothesis. Run 31966563243 (2026-08-16, `workflow_dispatch`
from `main`) reports, from the API:

    verify / verify   success   step 12 "Version consistency (REL-03)"      skipped
                                step 13 "Tag is annotated and signed (…)"   skipped
    publish           success   <- a real PyPI upload
    verify-published  skipped
    run conclusion    success

A skipped job does not fail a run, so the whole thing reported green. A PyPI
upload cannot be withdrawn.

These assertions are structural rather than textual. They walk the `needs:`
closure instead of substring-matching a job name, because a substring test
passes on a workflow whose dependency has actually been cut; and they check
that no branch of the tag expression can evaluate to an empty string, rather
than that the expression is spelled a particular way.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "pypi-publish.yml"
PUBLISH_ACTION = "pypa/gh-action-pypi-publish"
VERIFIER = "./.github/workflows/verify.yml"

# The job that re-reads what was published. Identified by what it does (it is
# the job that downloads from PyPI), never by name alone -- see
# `_post_publish_jobs`.
PYPI_DOWNLOAD = "pip download"


def _document() -> dict[Any, Any]:
    # `yaml.safe_load` resolves a bare `on:` key to the boolean True under YAML
    # 1.1, so a `document["on"]` lookup raises KeyError on a file that plainly
    # has one. Typed `dict[Any, Any]` so mypy --strict accepts both spellings.
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _triggers() -> dict[str, Any]:
    document = _document()
    on = document.get("on", document.get(True))
    assert isinstance(on, dict), f"{WORKFLOW.name} declares no `on:` mapping"
    return on


def _jobs() -> dict[str, Any]:
    jobs = _document()["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps") or []
    assert isinstance(steps, list)
    return [step for step in steps if isinstance(step, dict)]


def _publishing_jobs() -> dict[str, Any]:
    """Jobs that run the PyPI upload action, found by what they do."""
    return {
        job_id: job
        for job_id, job in _jobs().items()
        if any(PUBLISH_ACTION in str(step.get("uses", "")) for step in _steps(job))
    }


def _post_publish_jobs() -> dict[str, Any]:
    """Jobs that read back what was published, found by what they do."""
    return {
        job_id: job
        for job_id, job in _jobs().items()
        if any(PYPI_DOWNLOAD in str(step.get("run", "")) for step in _steps(job))
    }


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _closure(job_id: str) -> set[str]:
    """Every job `job_id` transitively depends on, itself excluded."""
    jobs = _jobs()
    seen: set[str] = set()
    frontier = list(_needs(jobs[job_id]))
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(_needs(jobs[current]))
    return seen


_EVENT_NAME_COMPARISON = re.compile(r"github\.event_name\s*==\s*'([a-z_]+)'")


def _events_reaching(job_id: str) -> set[str]:
    """Which declared triggers can run this job, and everything it needs.

    Fails closed: an `if:` that mentions `github.event_name` in a shape this
    parser does not recognise raises rather than being read as unrestricted.
    A parser that quietly gives up would turn every assertion below into one
    that cannot fail.
    """
    jobs = _jobs()
    events = set(_triggers())
    for current in {job_id} | _closure(job_id):
        condition = jobs[current].get("if")
        if condition is None:
            continue
        text = str(condition)
        if "github.event_name" not in text:
            continue
        allowed = set(_EVENT_NAME_COMPARISON.findall(text))
        if not allowed or "!=" in text or "!" in text.replace("!=", ""):
            raise AssertionError(
                f"job {current!r} has an `if:` this check cannot read: {text!r}. "
                "Teach it the new shape rather than leaving the trigger "
                "analysis silently permissive."
            )
        events &= allowed
    return events


def test_the_workflow_still_publishes_the_way_this_module_assumes() -> None:
    # Positive control. Every assertion below quantifies over a set found by
    # inspection; if the upload step is renamed or replaced, the sets go empty
    # and the whole module passes having checked nothing.
    assert _publishing_jobs(), (
        f"no job in {WORKFLOW.name} uses {PUBLISH_ACTION}. If publishing moved, "
        "move these checks with it rather than deleting them."
    )
    assert _post_publish_jobs(), (
        f"no job in {WORKFLOW.name} downloads from PyPI after publishing. The "
        "post-publish read-back (REL-16) is what makes 'the job exited 0' mean "
        "the right bits are public."
    )
    assert len(_triggers()) > 1, (
        "this module exists because two triggers reach one publish job; with "
        "one trigger there is no parity question and it should be re-read."
    )


def test_every_publishing_job_depends_on_the_verifier() -> None:
    jobs = _jobs()
    for job_id in _publishing_jobs():
        verifiers = [
            needed for needed in _closure(job_id) if VERIFIER in str(jobs[needed].get("uses", ""))
        ]
        assert verifiers, (
            f"job {job_id!r} publishes to PyPI without {VERIFIER} anywhere in its "
            "`needs:` closure, so nothing re-runs the gate at the tagged commit."
        )


def test_the_verifier_is_never_handed_an_empty_tag() -> None:
    """No branch of the tag expression may be a literal empty string.

    `verify.yml` gates version consistency and the annotated/signed-tag check
    on `inputs.tag != ''`. An empty tag therefore does not fail: it publishes
    with both checks skipped. That is what `|| ''` did on the dispatch path.
    """
    jobs = _jobs()
    verifier_calls = {
        job_id: job for job_id, job in jobs.items() if VERIFIER in str(job.get("uses", ""))
    }
    assert verifier_calls, f"nothing in {WORKFLOW.name} calls {VERIFIER}"

    for job_id, job in verifier_calls.items():
        expression = str((job.get("with") or {}).get("tag", ""))
        assert expression, f"job {job_id!r} calls the verifier without passing a tag at all"
        empty_literals = re.findall(r"\|\|\s*(''|\"\")", expression)
        assert not empty_literals, (
            f"job {job_id!r} falls back to an empty tag: {expression!r}. "
            "An empty tag silently disables the version-consistency and "
            "signed-tag checks in verify.yml while the publish still runs."
        )
        for name in re.findall(r"inputs\.([A-Za-z_][A-Za-z0-9_-]*)", expression):
            declared = (_triggers().get("workflow_dispatch") or {}).get("inputs", {})
            assert name in declared, (
                f"job {job_id!r} passes `inputs.{name}` but workflow_dispatch "
                f"declares no such input, so it is the empty string."
            )
            assert declared[name].get("required") is True, (
                f"`inputs.{name}` is not `required`, so a dispatch that omits it "
                "hands the verifier an empty tag and publishes unverified."
            )


def test_the_post_publish_check_covers_every_trigger_that_can_publish() -> None:
    publishing = {job_id: _events_reaching(job_id) for job_id in _publishing_jobs()}
    reading_back = {job_id: _events_reaching(job_id) for job_id in _post_publish_jobs()}

    covered: set[str] = set()
    for events in reading_back.values():
        covered |= events

    for job_id, events in publishing.items():
        uncovered = events - covered
        assert not uncovered, (
            f"job {job_id!r} uploads to PyPI on {sorted(events)} but the "
            f"post-publish read-back only runs on {sorted(covered)}. On "
            f"{sorted(uncovered)} the upload happens and nothing reads back what "
            "landed -- and a run whose remaining job is skipped concludes "
            "success."
        )


def test_a_dispatch_cannot_publish_without_naming_a_tag() -> None:
    dispatch = _triggers().get("workflow_dispatch")
    if dispatch is None:
        pytest.skip("workflow_dispatch is not a trigger of this workflow")
    assert isinstance(dispatch, dict)
    assert dispatch.get("inputs"), (
        "workflow_dispatch takes no inputs, so a dispatch names no tag -- and "
        "`publish` carries no trigger condition, so it uploads anyway."
    )
    inputs = dispatch["inputs"]
    required = [name for name, spec in inputs.items() if spec.get("required") is True]
    assert required, (
        "no workflow_dispatch input is `required`, so a dispatch can reach the "
        "publish job having named nothing to verify against."
    )
