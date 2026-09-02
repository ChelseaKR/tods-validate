"""The secret-scan gate must scan the working tree, not only committed history.

`make secrets` is the merge-blocking secret scan (SEC-17/18). Its recipe used
to be one line, ``gitleaks detect --source .``, which walks commits. A file
written into the working tree and not yet committed is invisible to that scan,
so the gate reported "no leaks found" and exit 0 over a tree holding a live
key. Measured at v0.10.0 against a root-level file containing an AWS key pair,
a GitHub PAT and a Slack bot token: the history scan gave exit 0, and the same
scan with ``--no-git`` gave exit 1.

Two tests here, doing different jobs. The first reads the recipe and always
runs, so deleting the working-tree half turns a test red on every machine and
in every CI job that runs pytest. The second drives the real binary and can
only run where it is installed; it is the one that proves the claim rather
than restating it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_MAKEFILE = _ROOT / "Makefile"
_GITLEAKS_CONFIG = _ROOT / ".gitleaks.toml"
# Resolved once, absolutely: the two behavioural tests run a real binary, and an
# absolute path is both what the linter asks for and one fewer thing that can
# resolve to something other than the scanner under test.
_GITLEAKS = shutil.which("gitleaks")

# Values that match gitleaks' default rules by shape. Nothing here is or ever
# was a credential: the AWS pair is the example AWS publishes in its own
# documentation, and the other two are digit runs.
#
# Each one is assembled from fragments rather than written out. A literal would
# make this file itself a finding, and the honest response to that is to keep
# the file inert, not to allowlist a path out of the scan the file exists to
# defend. Measured: with the Slack value written as one string, `make secrets`
# reported "leaks found: 1" against this file.
_PLANTED_SECRETS = "\n".join(
    (
        "aws_access_key_id = " + "AKIA" + "IOSFODNN7EXAMPLE",
        "aws_secret_access_key = " + "wJalrXUtnFEMI/K7MDENG/" + "bPxRfiCYEXAMPLEKEY",
        "github_pat = " + "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyzAB",
        "slack_token = " + "xoxb-" + "123456789012-123456789012-abcdefghijklmnopqrstuvwx",
    )
)


def _scan(binary: str, target: Path) -> subprocess.CompletedProcess[str]:
    """Run the working-tree scan the `secrets` gate runs, against one directory."""
    return subprocess.run(  # noqa: S603  # absolute binary path, fixed argv
        [
            binary,
            "detect",
            "--no-git",
            "--source",
            str(target),
            "--config",
            str(_GITLEAKS_CONFIG),
            "--redact",
            "--exit-code",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _secrets_recipe() -> str:
    """The body of the `secrets:` target, up to the next target or blank-line gap."""
    text = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^secrets:\n((?:\t.*\n|\n(?=\t))*)", text, re.M)
    assert match is not None, "Makefile has no `secrets:` target"
    return match.group(1)


def test_the_secret_gate_scans_the_working_tree_as_well_as_history() -> None:
    recipe = _secrets_recipe()
    assert "gitleaks" in recipe, "the secrets gate no longer invokes gitleaks"
    assert "--no-git" in recipe, (
        "`make secrets` runs only the committed-history scan. `gitleaks detect "
        "--source .` walks commits and cannot see an uncommitted file, so the "
        "gate would pass over a working tree holding a secret. Keep the "
        "`--no-git` scan."
    )
    history_scans = [
        line for line in recipe.splitlines() if "gitleaks detect" in line and "--no-git" not in line
    ]
    assert history_scans, (
        "`make secrets` no longer scans committed history; --no-git alone cannot "
        "find a secret that was committed and later deleted from the tree."
    )


def test_both_scans_report_independently() -> None:
    """Neither scan may be short-circuited by the other's result.

    `a && b` skips b when a fails, and `a; b` throws away a's exit code. Both
    have to run and both have to be able to fail the target on their own.
    """
    recipe = _secrets_recipe()
    assert "&&" not in recipe, (
        "the two gitleaks scans are chained with `&&`, so a failure in the first "
        "one prevents the second from running at all"
    )
    assert "status=1" in recipe, (
        "the recipe does not record a per-scan failure status; it cannot report "
        "which of the two scans failed, or fail when only the second one did"
    )


def test_the_gitleaks_config_scopes_only_dependencies_and_build_output() -> None:
    """The allowlist must not be a way to stop scanning project source.

    The working-tree scan walks whatever is on disk, which in the release
    verification workflow includes `.venv/` and `node_modules/`. Those are
    allowlisted so the gate measures this repository. An allowlist entry
    covering `src/`, `tests/`, `scripts/` or the repository root would silence
    the gate instead of scoping it.
    """
    assert _GITLEAKS_CONFIG.exists(), ".gitleaks.toml is missing"
    config = _GITLEAKS_CONFIG.read_text(encoding="utf-8")
    paths = re.findall(r"'''(.+?)'''", config)
    assert paths, "the allowlist has no path entries"
    for entry in paths:
        assert re.search(r"src|tests|scripts|examples|web|docs", entry) is None, (
            f"allowlist entry {entry!r} covers project source, which would stop "
            "the gate scanning the files it exists to scan"
        )
    for required in (".venv", "node_modules"):
        assert any(required in entry for entry in paths), (
            f"{required} is not allowlisted; the release verification workflow "
            "populates it before running `make verify`, so the working-tree scan "
            "would report third-party findings this project cannot fix"
        )


@pytest.mark.skipif(_GITLEAKS is None, reason="gitleaks is not installed")
def test_a_planted_secret_is_found_in_an_uncommitted_file(tmp_path: Path) -> None:
    """The behavioural half: the working-tree scan finds what history cannot.

    A directory that is not a git repository at all is the sharpest version of
    "not committed". The history scan has nothing to walk; the working-tree
    scan has the file.
    """
    (tmp_path / "config.env").write_text(_PLANTED_SECRETS, encoding="utf-8")

    assert _GITLEAKS is not None
    working_tree = _scan(_GITLEAKS, tmp_path)
    assert working_tree.returncode == 1, (
        "gitleaks did not flag a planted credential in an uncommitted file; "
        f"stdout={working_tree.stdout!r} stderr={working_tree.stderr!r}"
    )


@pytest.mark.skipif(_GITLEAKS is None, reason="gitleaks is not installed")
def test_the_working_tree_scan_is_clean_on_a_file_with_no_secret(tmp_path: Path) -> None:
    """The control. Without it, a scanner that fails on everything would pass
    the test above and tell us nothing."""
    (tmp_path / "config.env").write_text("region = us-west-2\nretries = 3\n", encoding="utf-8")

    assert _GITLEAKS is not None
    result = _scan(_GITLEAKS, tmp_path)
    assert result.returncode == 0, (
        f"gitleaks reported a finding on a file with no secret in it; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
