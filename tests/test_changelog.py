"""The CHANGELOG's heading format and the release gate that reads it agree.

`.github/workflows/verify.yml` refuses to release a version CHANGELOG.md has no
section for (REL-03/REL-10). That check is a `grep -qE` pattern written against
one heading format, and nothing tied the two together: renaming the headings
would leave the pattern matching nothing, and the mismatch would surface at
release time, on a tag, as a confusing failure. These run the workflow's own
grep, extracted from the workflow, against the real file.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

# Keep a Changelog's section form (DOC-07/REL-10), plus the unreleased section.
RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$")
UNRELEASED_HEADING = "## [Unreleased]"


def _release_gate_grep() -> str:
    """The bare grep command verify.yml uses to require a CHANGELOG section."""
    for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("if ! grep -qE") and "CHANGELOG.md" in stripped:
            return stripped.removeprefix("if ! ").removesuffix("; then")
    raise AssertionError(
        "verify.yml no longer has a CHANGELOG section check; the release gate "
        "REL-03/REL-10 relies on has been removed or renamed."
    )


def _gate_finds_section_for(version: str) -> bool:
    """Whether the release gate's own grep matches a heading for ``version``."""
    command = f'TAG_VERSION="{version}"\n{_release_gate_grep()}'
    result = subprocess.run(  # noqa: S603 -- fixed argv; the text is read from a repo file
        ["/bin/bash", "-c", command],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def test_every_section_heading_uses_the_keep_a_changelog_form() -> None:
    lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    headings = [line for line in lines if line.startswith("## ")]
    assert headings, "CHANGELOG.md has no section headings"
    assert headings[0] == UNRELEASED_HEADING
    malformed = [h for h in headings[1:] if not RELEASE_HEADING.match(h)]
    assert not malformed, f"headings not in '## [X.Y.Z] - YYYY-MM-DD' form: {malformed}"


def test_the_release_gate_finds_the_current_version() -> None:
    # The tie. If the headings are reformatted and the workflow's grep is not,
    # this fails here rather than on a release tag.
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert _gate_finds_section_for(version), (
        f"the release gate's grep in verify.yml does not match any heading for "
        f"{version}; CHANGELOG.md and the gate have drifted apart"
    )


def test_the_release_gate_still_refuses_a_version_with_no_section() -> None:
    # Positive control in the other direction: a grep loose enough to match
    # anything would satisfy the test above without checking anything.
    assert not _gate_finds_section_for("99.99.99")
