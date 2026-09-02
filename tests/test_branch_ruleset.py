"""The committed branch ruleset and the workflows it gates on stay in step.

`docs/rulesets/main.json` names the status checks that must pass before a pull
request can merge. A check name is a job's rendered name, which changes when a
job is renamed, when a matrix dimension gains or loses a value, or when a job
is added or deleted. Neither direction of drift is observable from inside the
repository once the ruleset is applied: GitHub never complains about a required
check no workflow produces (it waits for it forever), and a check the workflows
produce but the ruleset does not name simply stops blocking, silently.

The path-filter rule below is the one that bites hardest. A workflow whose
`pull_request` trigger carries `paths:` does not run on a pull request that
touches nothing matching, so the check never reports, so a merge that requires
it can never happen. `docs/CONFORMANCE-GAPS.md` described the intended ruleset
in prose and named `zizmor` among the required checks; zizmor is path-filtered,
and following that prose would have blocked every pull request that did not
edit a workflow file. That is what a prose ruleset costs, and why this one is a
file with a test.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parent.parent
RULESET = ROOT / "docs" / "rulesets" / "main.json"
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(workflow: Path) -> dict[str, Any]:
    # PyYAML resolves the bare key `on` to the boolean True (YAML 1.1), which
    # is why this is not a plain document["on"].
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    on = document.get(True, document.get("on"))
    return on if isinstance(on, dict) else {}


def _check_names(document: dict[str, Any]) -> set[str]:
    """Every status-check name the jobs in ``document`` report to GitHub.

    A job reports under its ``name:`` if it has one, otherwise its id. A job
    with a matrix reports once per combination, with the values joined by
    ", " in parentheses in the order the matrix declares its dimensions.
    """
    names: set[str] = set()
    for job_id, job in document.get("jobs", {}).items():
        base = job.get("name", job_id)
        matrix = job.get("strategy", {}).get("matrix", {})
        dimensions = [value for value in matrix.values() if isinstance(value, list)]
        if not dimensions:
            names.add(base)
            continue
        for combination in itertools.product(*dimensions):
            names.add(f"{base} ({', '.join(str(value) for value in combination)})")
    return names


def _workflows_by_kind() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Checks that report on every pull request, and checks that report on some.

    The split is the whole point. Only a check that reports on *every* pull
    request can be required; one that reports on some of them is a check the
    ruleset must leave alone.
    """
    always: dict[str, set[str]] = {}
    conditional: dict[str, set[str]] = {}
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        document = _load(workflow)
        triggers = _triggers(document)
        if "pull_request" not in triggers:
            continue
        settings = triggers["pull_request"] or {}
        target = conditional if {"paths", "paths-ignore"} & set(settings) else always
        target[workflow.name] = _check_names(document)
    return always, conditional


def _required_checks() -> set[str]:
    for rule in json.loads(RULESET.read_text(encoding="utf-8"))["rules"]:
        if rule["type"] == "required_status_checks":
            return {c["context"] for c in rule["parameters"]["required_status_checks"]}
    raise AssertionError("docs/rulesets/main.json requires no status checks at all")


def _unconditional_checks() -> set[str]:
    always, _ = _workflows_by_kind()
    return set().union(*always.values())


def test_every_required_check_is_produced_on_every_pull_request() -> None:
    phantom = _required_checks() - _unconditional_checks()
    assert not phantom, (
        f"docs/rulesets/main.json requires {sorted(phantom)}, which no workflow "
        "reports on every pull request. A required check that does not report "
        "blocks the merge forever."
    )


def test_no_path_filtered_check_is_required() -> None:
    _, conditional = _workflows_by_kind()
    required = _required_checks()
    offenders = {
        f"{workflow}: {name}"
        for workflow, names in conditional.items()
        for name in names & required
    }
    assert not offenders, (
        f"path-filtered checks required by docs/rulesets/main.json: "
        f"{sorted(offenders)}. Their workflow does not run on a pull request "
        "that touches nothing it filters on, so the check never reports."
    )


def test_every_unconditional_check_is_required() -> None:
    unguarded = _unconditional_checks() - _required_checks()
    assert not unguarded, (
        f"{sorted(unguarded)} report on every pull request but are not required "
        "by docs/rulesets/main.json, so a red one would not block a merge."
    )


def test_the_ruleset_blocks_the_things_it_exists_for() -> None:
    # Positive control for the three tests above, which compare two lists and
    # would all be satisfied by an empty ruleset paired with no workflows.
    # These are the protections CQ-37 to 43 name, and why the file exists.
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    kinds = {rule["type"] for rule in ruleset["rules"]}
    assert {"deletion", "non_fast_forward", "required_linear_history", "pull_request"} <= kinds
    assert ruleset["enforcement"] == "active"
    assert ruleset["bypass_actors"] == [], "an admin bypass is what CQ-43 asks not to have"
    pull_request = next(r for r in ruleset["rules"] if r["type"] == "pull_request")
    assert pull_request["parameters"]["dismiss_stale_reviews_on_push"] is True
    assert pull_request["parameters"]["required_review_thread_resolution"] is True


def test_the_review_requirement_matches_the_number_of_people_who_could_meet_it() -> None:
    """Require an approval exactly when someone other than the author could give one.

    This asserted `required_approving_review_count >= 1` and
    `require_code_owner_review is True` until 2026-09-01, when the file stopped
    being an intention and had to be applied. Neither is satisfiable here:
    GitHub does not count a self-approval, `CODEOWNERS` names one person, and
    `bypass_actors` is empty by design, so a one-approval rule on this
    repository blocks every merge instead of reviewing anything. Asserting it
    made the suite green about a configuration that could not run.

    Tying the assertion to the owner count keeps the aspiration without the
    fiction: the moment a second owner is added, zero approvals starts failing
    here and has to be raised.
    """
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    parameters = next(r for r in ruleset["rules"] if r["type"] == "pull_request")["parameters"]
    owners = {
        word
        for line in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
        for word in line.split()
        if word.startswith("@")
    }
    if len(owners) > 1:
        assert parameters["required_approving_review_count"] >= 1, (
            f"CODEOWNERS names {sorted(owners)}, so an approval is now obtainable "
            "from someone other than the author and should be required"
        )
        assert parameters["require_code_owner_review"] is True
    else:
        assert parameters["required_approving_review_count"] == 0, (
            f"CODEOWNERS names only {sorted(owners)}; a required approval no one "
            "can give blocks every merge rather than reviewing anything"
        )
        assert parameters["require_code_owner_review"] is False


def test_the_path_filtered_workflow_this_guards_against_is_still_path_filtered() -> None:
    # Positive control for test_no_path_filtered_check_is_required: with no
    # path-filtered pull-request workflow in the repository, that test would
    # pass without checking anything.
    _, conditional = _workflows_by_kind()
    assert "zizmor.yml" in conditional, (
        "zizmor.yml is no longer path-filtered on pull_request. If it now runs "
        "on every pull request, `zizmor` can and should become a required check."
    )
