"""The job that publishes to PyPI is scoped to a GitHub Environment (CICD-06).

Trusted Publishing replaces a stored API token with an OIDC claim, and the
claim is only as narrow as the thing that mints it. A trusted publisher
configured with a blank environment accepts a token from any workflow in the
repository that can ask for one, which is a wider grant than "the release
workflow may publish".

Declaring `environment: pypi` on the publishing job is the repository half of
narrowing it. The other half is the publisher config on PyPI, set on
2026-09-01, which nothing here can read: PyPI's project settings are visible
only to its owner, so no gate in this repository can confirm the two still
agree. What this module can do is stop the half that lives here from being
removed by accident. The declaration is four lines of YAML, and without this
nothing else in the build would notice if they went — least of all the release
that would then publish with an unscoped token.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "pypi-publish.yml"
PUBLISH_ACTION = "pypa/gh-action-pypi-publish"


def _jobs() -> dict[str, Any]:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    jobs = document["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _publishing_jobs() -> dict[str, Any]:
    """Every job that runs the PyPI upload action, found by what it does."""
    found = {}
    for job_id, job in _jobs().items():
        steps = job.get("steps") or []
        if any(PUBLISH_ACTION in str(step.get("uses", "")) for step in steps):
            found[job_id] = job
    return found


def test_the_workflow_still_publishes_the_way_this_module_assumes() -> None:
    # Positive control. If the upload step is renamed or replaced, the tests
    # below would find no jobs and pass without checking anything.
    assert _publishing_jobs(), (
        f"no job in {WORKFLOW.name} uses {PUBLISH_ACTION}. If publishing moved, "
        "move this check with it rather than deleting it."
    )


def test_every_publishing_job_is_environment_scoped() -> None:
    unscoped = [job_id for job_id, job in _publishing_jobs().items() if not job.get("environment")]
    assert not unscoped, (
        f"{unscoped} upload to PyPI without declaring an environment, so the OIDC "
        "token they mint carries no environment claim for PyPI to check (CICD-06)."
    )


def test_the_environment_is_the_one_pypi_is_configured_against() -> None:
    # The name is not cosmetic: PyPI compares it to the claim, so a rename here
    # is a publishing outage at the next release rather than a lint failure.
    for job_id, job in _publishing_jobs().items():
        environment = job["environment"]
        name = environment["name"] if isinstance(environment, dict) else environment
        assert name == "pypi", (
            f"job {job_id!r} publishes from environment {name!r}; PyPI's trusted "
            "publisher for this project is configured against 'pypi'."
        )
