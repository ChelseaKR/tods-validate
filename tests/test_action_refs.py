"""A documented pin is checked, not just written.

`scripts/check_action_refs.py` exists because `ChelseaKR/tods-validate@v0` was
published once and never moved: it still resolves to the v0.5.0 release commit,
whose `--format github` reported `0 error(s), 0 warning(s), 0 info` on a feed
that had run 26 of its 43 checks and which has no `require-complete-run` at all.
These pin that the gate can fail -- on a stale exact pin, on a major-only ref,
on a branch, and on the scanner itself going quiet.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_action_refs.py"


def _checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_action_refs", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CURRENT = _checker().declared_version()


def _action_line(ref: str) -> str:
    return f"      - uses: ChelseaKR/tods-validate@{ref}\n"


def _precommit_block(ref: str) -> str:
    return (
        "  - repo: https://github.com/ChelseaKR/tods-validate\n"
        f"    rev: {ref}\n"
        "    hooks:\n"
        "      - id: tods-validate\n"
    )


def test_the_committed_examples_are_current() -> None:
    assert _checker().main() == 0


def test_the_committed_tree_still_teaches_pins() -> None:
    """A scanner that matches nothing would otherwise pass every file.

    README.md carries two Action examples and .pre-commit-hooks.yaml one. If
    this drops, the regexes or the filenames moved, and every other test here
    is passing over an empty set.
    """
    checker = _checker()
    found = 0
    for relative in checker.tracked_files():
        text = (checker.ROOT / relative).read_text(encoding="utf-8", errors="replace")
        if "ChelseaKR/tods-validate" not in text:
            continue
        found += checker.scan_text(relative, text, CURRENT)[1]
    assert found >= 3, f"only {found} documented pins found; the scanner or the docs moved"


@pytest.mark.parametrize(
    ("ref", "expected_fragment"),
    [
        ("v0", "major- or minor-only ref"),
        ("v0.11", "major- or minor-only ref"),
        ("v1", "major- or minor-only ref"),
        ("main", "is not a release"),
        ("master", "is not a release"),
        ("HEAD", "is not a release"),
    ],
)
def test_a_moving_ref_is_refused_however_it_currently_resolves(
    ref: str, expected_fragment: str
) -> None:
    problems, found = _checker().scan_text("doc.md", _action_line(ref), CURRENT)
    assert found == 1
    assert len(problems) == 1
    assert expected_fragment in problems[0]
    assert ref in problems[0]


def test_the_ref_this_repository_actually_published_is_refused() -> None:
    """@v0 is the live case: published, unmoved, and six releases behind."""
    problems, _ = _checker().scan_text("README.md", _action_line("v0"), CURRENT)
    assert len(problems) == 1
    assert "README.md:1" in problems[0]


@pytest.mark.parametrize("stale", ["v0.4.0", "v0.10.0", "v0.9.1"])
def test_an_exact_pin_that_is_not_the_current_release_is_refused(stale: str) -> None:
    assert stale != f"v{CURRENT}"
    problems, found = _checker().scan_text("README.md", _action_line(stale), CURRENT)
    assert found == 1
    assert len(problems) == 1
    assert stale.removeprefix("v") in problems[0]
    assert CURRENT in problems[0]


def test_the_current_exact_pin_passes() -> None:
    problems, found = _checker().scan_text("README.md", _action_line(f"v{CURRENT}"), CURRENT)
    assert found == 1
    assert problems == []


def test_a_bare_commit_sha_passes() -> None:
    problems, found = _checker().scan_text("README.md", _action_line("a" * 40), CURRENT)
    assert found == 1
    assert problems == []


def test_a_commit_sha_whose_comment_names_another_release_is_refused() -> None:
    """The comment is the half a reader reads; a stale one misdescribes the SHA."""
    stale = "v0.10.0"
    assert stale != f"v{CURRENT}"
    line = f"      - uses: ChelseaKR/tods-validate@{'b' * 40}  # {stale}\n"
    problems, found = _checker().scan_text("README.md", line, CURRENT)
    assert found == 1
    assert len(problems) == 1
    assert "comment" in problems[0]


def test_a_commit_sha_whose_comment_names_the_current_release_passes() -> None:
    line = f"      - uses: ChelseaKR/tods-validate@{'c' * 40}  # v{CURRENT}\n"
    problems, found = _checker().scan_text("README.md", line, CURRENT)
    assert found == 1
    assert problems == []


@pytest.mark.parametrize("ref", ["v0", "v0.4.0", "main"])
def test_the_precommit_example_is_checked_too(ref: str) -> None:
    """#137 bumped a stale pre-commit pin by hand; it went stale again by v0.11.0."""
    problems, found = _checker().scan_text(".pre-commit-hooks.yaml", _precommit_block(ref), CURRENT)
    assert found == 1
    assert len(problems) == 1
    assert "pre-commit example" in problems[0]


def test_the_precommit_example_passes_when_current() -> None:
    problems, found = _checker().scan_text(
        ".pre-commit-hooks.yaml", _precommit_block(f"v{CURRENT}"), CURRENT
    )
    assert found == 1
    assert problems == []


def test_a_commented_out_precommit_example_is_checked() -> None:
    """.pre-commit-hooks.yaml's example is a YAML comment, which is still copied."""
    text = (
        "#   - repo: https://github.com/ChelseaKR/tods-validate\n"
        "#     rev: v0.4.0  # stale\n"
        "#     hooks:\n"
    )
    problems, found = _checker().scan_text(".pre-commit-hooks.yaml", text, CURRENT)
    assert found == 1
    assert len(problems) == 1


def test_another_projects_rev_is_not_bound_to_this_projects_version() -> None:
    """.pre-commit-config.yaml pins ruff and friends; those are not ours to date."""
    text = (
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v0.6.9\n"
        "    hooks:\n"
        "      - id: ruff\n"
        "  - repo: https://github.com/ChelseaKR/tods-validate\n"
        f"    rev: v{CURRENT}\n"
        "    hooks:\n"
        "      - id: tods-validate\n"
    )
    problems, found = _checker().scan_text(".pre-commit-config.yaml", text, CURRENT)
    assert found == 1, "the ruff rev was counted, or this project's was missed"
    assert problems == []


def test_prose_about_the_stale_ref_is_not_mistaken_for_teaching_it() -> None:
    """docs/plans/ and the gaps ledger describe @v0 in order to retire it."""
    text = (
        "`v0` is a lightweight tag at the v0.5.0 release commit, so\n"
        "`ChelseaKR/tods-validate@v0` resolves to v0.5.0 today. Remove it with\n"
        "`git push origin :refs/tags/v0`.\n"
    )
    problems, found = _checker().scan_text("docs/plans/v1.0.0-readiness.md", text, CURRENT)
    assert (problems, found) == ([], 0)


def test_a_run_that_finds_no_pin_at_all_refuses_to_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The anti-vacuity control: silence must not read as success.

    A renamed README, or a regex that stopped matching, leaves the problem list
    empty. Without this the gate would print nothing and exit 0.
    """
    checker = _checker()
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "tods-validate"\nversion = "{CURRENT}"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "Install with `pipx install tods-validate`.\n", encoding="utf-8"
    )
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    monkeypatch.setattr(checker, "tracked_files", lambda root=tmp_path: ["README.md"])
    assert checker.main() == 1


def test_a_run_with_no_scannable_files_refuses_to_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checker = _checker()
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "tods-validate"\nversion = "{CURRENT}"\n', encoding="utf-8"
    )
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    monkeypatch.setattr(checker, "tracked_files", lambda root=tmp_path: [])
    assert checker.main() == 1
