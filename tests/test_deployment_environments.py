"""Every environment a job deploys to admits the refs that job actually runs at.

A GitHub Environment can carry a deployment branch policy, and a job whose
`environment:` names one is refused before its first step when the ref it runs
at does not match. That refusal produces a failed job with no steps and no
retrievable log, which is a hard thing to read backwards from.

It is also invisible from inside the repository. `github-pages` admitted the
branch `main` and nothing else, while `pypi-publish.yml`'s `deploy-playground`
stage calls `pages.yml` during a `release: published` run, where the ref is
`refs/tags/vX.Y.Z`. That stage therefore failed on v0.10.0 and on v0.11.0,
having never once completed, while the header comment above it described the
sequencing it provides as structural. The playground kept reaching production
by the `push`-to-`main` path the sequencing exists to replace.

`docs/environments/main.json` is the export of both environments' policies.
These tests compare it with the workflows, in the direction that drifts: a job
deploying to an environment whose policy does not admit its refs. What no test
here can do is compare the file with GitHub, the same limit
`docs/rulesets/main.json` has; re-export after changing either.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
ENVIRONMENTS = ROOT / "docs" / "environments" / "main.json"
# What a release run's ref looks like. The tag name is the release checklist's
# (`git tag -s vX.Y.Z`), so a policy admitting this admits every release.
RELEASE_REF = "v0.11.0"


def _load(workflow: Path) -> dict[str, Any]:
    # PyYAML resolves the bare key `on` to True under YAML 1.1.
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    on = document.get(True, document.get("on"))
    return on if isinstance(on, dict) else {}


def _environment_of(job: dict[str, Any]) -> str | None:
    environment = job.get("environment")
    if isinstance(environment, dict):
        name = environment.get("name")
        return name if isinstance(name, str) else None
    return environment if isinstance(environment, str) else None


def _called_workflow(job: dict[str, Any]) -> Path | None:
    uses = job.get("uses")
    if isinstance(uses, str) and uses.startswith("./.github/workflows/"):
        # removeprefix, not lstrip: lstrip("./") strips every leading "." and
        # "/", turning "./.github/..." into "github/...", which resolves to a
        # path that does not exist and makes this whole check pass vacuously.
        return ROOT / uses.removeprefix("./")
    return None


def _environments_reachable_from(workflow: Path, seen: set[Path] | None = None) -> set[str]:
    """Environments deployed to by this workflow, following local `uses:` calls.

    A reusable workflow runs at the caller's ref, so an environment reached
    through `uses:` is subject to the caller's trigger, not its own.
    """
    seen = seen if seen is not None else set()
    if workflow in seen or not workflow.exists():
        return set()
    seen.add(workflow)

    found: set[str] = set()
    for job in _load(workflow).get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        environment = _environment_of(job)
        if environment:
            found.add(environment)
        called = _called_workflow(job)
        if called:
            found |= _environments_reachable_from(called, seen)
    return found


def _committed() -> dict[str, Any]:
    document = json.loads(ENVIRONMENTS.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _admits(environment: str, ref_type: str, ref_name: str) -> bool:
    record = _committed().get(environment)
    if record is None:
        return False
    policy = record["deployment_branch_policy"]
    if policy is None:
        # No policy at all means every ref is admitted.
        return True
    return any(
        entry["type"] == ref_type and fnmatch.fnmatch(ref_name, entry["name"])
        for entry in record["branch_policies"]
    )


def test_every_environment_a_workflow_deploys_to_is_recorded() -> None:
    used: set[str] = set()
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        used |= _environments_reachable_from(workflow)
    unrecorded = used - set(_committed())
    assert not unrecorded, (
        f"{sorted(unrecorded)} are deployed to by a workflow but absent from "
        f"{ENVIRONMENTS.relative_to(ROOT)}, so nothing records what refs they admit."
    )


def test_release_triggered_deploys_are_admitted_at_the_tag() -> None:
    """The failure this module exists for: a release deploy refused at the gate."""
    offenders = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        if "release" not in _triggers(_load(workflow)):
            continue
        for environment in sorted(_environments_reachable_from(workflow)):
            if not _admits(environment, "tag", RELEASE_REF):
                offenders.append(f"{workflow.name} -> {environment}")
    assert not offenders, (
        f"{offenders} deploy during a release, where the ref is a tag, but the "
        f"environment's policy does not admit {RELEASE_REF!r}. The job is refused "
        "before its first step and leaves no log."
    )


def test_push_triggered_deploys_are_admitted_at_the_branch() -> None:
    offenders = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        push = _triggers(_load(workflow)).get("push") or {}
        for branch in push.get("branches", []) if isinstance(push, dict) else []:
            for environment in sorted(_environments_reachable_from(workflow)):
                if not _admits(environment, "branch", str(branch)):
                    offenders.append(f"{workflow.name} -> {environment} at {branch}")
    assert not offenders, (
        f"{offenders} deploy on a push to that branch, but the environment's "
        "policy does not admit it."
    )


def test_a_release_deploy_actually_exists_to_check() -> None:
    # Positive control. Both tests above pass vacuously if no workflow reaches
    # an environment from a release trigger, which is the state that would
    # follow from someone deleting the deploy stage rather than fixing it.
    reachable = [
        (workflow.name, environment)
        for workflow in sorted(WORKFLOWS.glob("*.yml"))
        if "release" in _triggers(_load(workflow))
        for environment in sorted(_environments_reachable_from(workflow))
    ]
    assert reachable, (
        "no workflow reaches a deployment environment from a release trigger, "
        "so the release-tag assertion above checks nothing"
    )
