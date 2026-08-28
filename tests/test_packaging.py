"""Declared dependencies stay in the table that matches what they are.

CQ-27 in `docs/standards/CODE-QUALITY-STANDARD.md` asks that development
dependencies be declared in a PEP 735 `[dependency-groups]` table rather than
in `[project.optional-dependencies]`, "so linters/type-checkers never ship as
extras", and marks it AUTO-GATE. This is that gate. Without it the move is one
edit away from being undone, silently, by anyone adding a test dependency to
the table that reads most familiar.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"

# Packages that exist to develop, test, or audit this project and never to run
# it. The list is explicit because it cannot be derived from the tables: pygls
# is legitimately in both the `lsp` extra (a runtime capability of an installed
# tods-validate) and the `dev` group (needed to test that capability), so
# "appears in a dependency group" is not the test. Add to this list when a new
# tool is adopted; it is the machine-readable half of CQ-27's claim.
DEV_ONLY_TOOLS = frozenset(
    {
        "coverage",
        "hypothesis",
        "jsonschema",
        "mutmut",
        "mypy",
        "pip-audit",
        "pre-commit",
        "pytest",
        "pytest-cov",
        "ruff",
    }
)


def _pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _requirement_names(specifiers: list[str]) -> set[str]:
    """The bare distribution names in a list of PEP 508 requirement strings."""
    names = set()
    for specifier in specifiers:
        name = specifier.split(";")[0].split("[")[0]
        for operator in ("===", "==", ">=", "<=", "~=", "!=", ">", "<"):
            name = name.split(operator)[0]
        names.add(name.strip().lower())
    return names


def test_development_tooling_is_declared_as_a_dependency_group() -> None:
    groups = _pyproject().get("dependency-groups")
    assert isinstance(groups, dict), "pyproject.toml has no [dependency-groups] table"
    assert "dev" in groups, "the dev dependency group is where development tooling belongs"
    declared = _requirement_names(groups["dev"])
    assert {"pytest", "ruff", "mypy"} <= declared


def test_development_tooling_is_not_an_extra_of_the_published_package() -> None:
    # The half that can regress. An extra ships with the distribution, so a
    # linter declared as one is installable by anyone who installs this tool.
    extras = _pyproject()["project"].get("optional-dependencies", {})
    offenders = {
        f"{extra}: {name}"
        for extra, specifiers in extras.items()
        for name in _requirement_names(specifiers) & DEV_ONLY_TOOLS
    }
    assert not offenders, (
        "development tooling declared as a published extra (CQ-27): "
        f"{', '.join(sorted(offenders))}. Move it to [dependency-groups]."
    )


def test_the_runtime_extras_are_still_runtime_extras() -> None:
    # Positive control for the test above: the two extras that should exist do
    # exist and still carry their runtime dependency. A change that emptied
    # [project.optional-dependencies] altogether would satisfy the CQ-27 test
    # and fail this one.
    extras = _pyproject()["project"]["optional-dependencies"]
    assert _requirement_names(extras["lsp"]) == {"pygls"}
    assert _requirement_names(extras["dataframe"]) == {"pandas"}
