"""The README's checkable claims, checked.

The README is the product for anyone who has not installed the tool yet, and
several of its claims are mechanical: a flag name, a rule count, a severity
split. Nothing compared them to the code, and one had been wrong since the
Observability section was written -- it declared "Opt-in ``--log-format json``
only", a flag that exists nowhere in ``src/``, while the Standards Conformance
table two paragraphs below asserted conformance with the tier that asks for it.

These tests are deliberately narrow. They check claims that can be derived
from the implementation, and they say nothing about prose.
"""

from __future__ import annotations

import re
from pathlib import Path

import click

from tods_validate.cli import main
from tods_validate.rules import all_rules

_README = Path(__file__).resolve().parent.parent / "README.md"

# Long options the README names that belong to other programs, not to
# tods-validate. Kept explicit and small: an allowlist is the only part of this
# test that can be used to wave a real mismatch through, so each entry says
# whose flag it is.
_FOREIGN_FLAGS = {
    "--rm": "docker run",
    "--group": "pip install",
    "--no-deps": "pip install",
    "--require-hashes": "pip install",
}

# Flags the README names in order to say they are *not* implemented. Naming one
# is allowed only while the gap is written down, so each entry points at the
# section of the gaps ledger that carries it, and both halves are checked
# below. Without this, "stop claiming it" and "explain why it is missing" would
# be indistinguishable to the test, and the second is the more useful README.
_DOCUMENTED_ABSENT = {
    "--log-format": "observability",
}

_GAPS = Path(__file__).resolve().parent.parent / "docs" / "CONFORMANCE-GAPS.md"


def _readme() -> str:
    return _README.read_text(encoding="utf-8")


def _cli_long_options() -> set[str]:
    """Every ``--option`` the CLI accepts, across the group and its subcommands."""
    found: set[str] = set()

    def walk(command: click.Command) -> None:
        for param in command.params:
            for opt in (*param.opts, *param.secondary_opts):
                if opt.startswith("--"):
                    found.add(opt)
        if isinstance(command, click.Group):
            for sub in command.commands.values():
                walk(sub)

    walk(main)
    return found


def test_every_flag_the_readme_names_exists_in_the_cli() -> None:
    named = set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]+", _readme()))
    claimed = named - set(_FOREIGN_FLAGS) - set(_DOCUMENTED_ABSENT)
    missing = sorted(claimed - _cli_long_options())
    assert not missing, (
        f"README names {', '.join(missing)}, which the CLI does not accept. "
        "Add the flag, stop claiming it, or record it in _DOCUMENTED_ABSENT "
        "with the gap that tracks it. A documented flag that does not exist is "
        "the same defect as a rule that never fires."
    )


def test_a_flag_documented_as_absent_is_absent_and_its_gap_is_recorded() -> None:
    """Both halves of the exemption, so neither can rot.

    If the flag ships, the entry has to go or the README will keep explaining
    an absence that ended. If the gaps ledger loses the section, the README is
    pointing at nothing.
    """
    gaps = _GAPS.read_text(encoding="utf-8")
    options = _cli_long_options()
    for flag, section in _DOCUMENTED_ABSENT.items():
        assert flag not in options, (
            f"{flag} is recorded as not implemented but the CLI now accepts it; "
            "drop the entry so the flag is checked like every other one."
        )
        readme = _readme()
        assert flag in readme, (
            f"{flag} is recorded as documented-absent but the README no longer "
            "mentions it; drop the entry."
        )
        assert f"CONFORMANCE-GAPS.md#{section}" in readme, (
            f"the README names {flag} without linking the gap that tracks it. "
            f"Naming an unimplemented flag is only honest next to "
            f"docs/CONFORMANCE-GAPS.md#{section}; otherwise it reads as a feature."
        )
        assert f"## {section}" in gaps, (
            f"{flag}'s gap link points at docs/CONFORMANCE-GAPS.md#{section}, "
            "which has no such section."
        )


def test_the_foreign_flag_allowlist_still_earns_its_place() -> None:
    """The allowlist is the hole in the test above, so it is checked too.

    An entry that the README no longer mentions is dead, and dead entries are
    how an allowlist grows into a place to hide a real mismatch.
    """
    readme = _readme()
    unused = sorted(flag for flag in _FOREIGN_FLAGS if flag not in readme)
    assert not unused, (
        f"{', '.join(unused)} is allowlisted as another program's flag but the "
        "README no longer names it; drop the entry."
    )
    for flag, owner in _FOREIGN_FLAGS.items():
        assert flag not in _cli_long_options(), (
            f"{flag} is allowlisted as {owner}'s flag but tods-validate now has "
            "one by that name; remove it from the allowlist so it is checked."
        )


def test_the_readme_rule_counts_match_the_registry() -> None:
    """ "43 checks" and "16 rules that read GTFS files" are derived numbers."""
    readme = _readme()
    total = len(list(all_rules()))
    needs_gtfs = sum(1 for rule in all_rules() if rule.needs_gtfs)

    assert f"{total} checks" in readme or f"of {total})" in readme, (
        f"the registry holds {total} rules and the README does not say so"
    )
    assert f"{needs_gtfs} rules that read GTFS files" in readme, (
        f"{needs_gtfs} rules set needs_gtfs=True; the README's count disagrees"
    )


def test_the_readme_does_not_claim_a_logging_surface_the_package_does_not_have() -> None:
    """The specific regression, pinned by its cause rather than its wording.

    ``--log-format`` is covered by the flag test above, but only while the
    README spells it that way. This asserts the underlying fact: no module in
    the package emits log records, so no claim about their format can be true.
    """
    src = Path(__file__).resolve().parent.parent / "src" / "tods_validate"
    importers = sorted(
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if re.search(r"^\s*(import logging|from logging import)", path.read_text("utf-8"), re.M)
    )
    readme = _readme()
    if importers:
        # The package grew a logging surface. That is allowed, but then the
        # Observability section's gap entry is stale and should be revisited
        # rather than left saying nothing logs.
        assert "--log-format" in readme, (
            f"{', '.join(importers)} now use logging, so the Observability "
            "section's reason for having no --log-format flag no longer holds"
        )
    else:
        assert "Opt-in\n--log-format json only" not in readme, (
            "the README declares an opt-in --log-format flag while nothing in "
            "the package logs anything"
        )
