"""`tods-validate explain RULE_ID`: offline rule detail with a worked example.

Reads only the rule registry (no feed), and shares its rendering with LSP
hovers via ``render_rule_detail`` so the two cannot drift from each other.
"""

from __future__ import annotations

from click.testing import CliRunner

from tods_validate.cli import main
from tods_validate.lsp import hover_markdown
from tods_validate.rules import EXAMPLES, all_rules, render_rule_detail


def invoke(*args: str):
    return CliRunner().invoke(main, list(args))


def test_explain_known_rule_shows_title_spec_and_example() -> None:
    result = invoke("explain", "TODS-W206")
    assert result.exit_code == 0, result.output
    assert "TODS-W206" in result.output
    assert "Value has leading or trailing spaces" in result.output
    assert "https://tods-transit.org/spec/" in result.output
    assert "vehicles.txt" in result.output  # the example's file
    assert "bus-1 ,Old Reliable" in result.output  # the "before" line
    assert "bus-1,Old Reliable" in result.output  # the "after" line


def test_explain_shows_interpretation_when_present() -> None:
    rule_def = next(r for r in all_rules() if r.id == "TODS-E401")
    assert rule_def.interpretation is not None  # sanity: this rule has one
    result = invoke("explain", "TODS-E401")
    assert result.exit_code == 0
    assert rule_def.interpretation in result.output


def test_explain_unknown_rule_exits_nonzero() -> None:
    result = invoke("explain", "TODS-NOPE")
    assert result.exit_code != 0
    assert "TODS-NOPE" in result.output


def test_explain_markdown_format_is_paste_ready() -> None:
    result = invoke("explain", "TODS-W206", "--format", "markdown")
    assert result.exit_code == 0, result.output
    assert "**TODS-W206**" in result.output
    assert "```csv" in result.output


def test_every_core_rule_has_a_worked_example() -> None:
    """The "Excellent" bar: every default-enabled (core) rule ships an example."""
    core_ids = {r.id for r in all_rules() if r.category == "core"}
    assert core_ids <= set(EXAMPLES)


def test_explain_covers_every_rule_that_has_an_example() -> None:
    for rule_id in EXAMPLES:
        result = invoke("explain", rule_id)
        assert result.exit_code == 0, f"{rule_id}: {result.output}"
        assert "Example" in result.output


def test_hover_and_explain_render_the_same_example_body() -> None:
    """Drift guard: hover_markdown and `explain --format markdown` must agree.

    Both call tods_validate.rules.render_rule_detail; this pins that they
    stay wired to the same renderer instead of silently diverging.
    """
    for rule_id in EXAMPLES:
        hover = hover_markdown(rule_id)
        assert hover is not None
        result = invoke("explain", rule_id, "--format", "markdown")
        assert result.exit_code == 0
        explained = result.output.rstrip("\n")
        assert hover == explained
        # And both agree with the shared renderer directly.
        rule_def = next(r for r in all_rules() if r.id == rule_id)
        assert hover == render_rule_detail(rule_def, "markdown")
