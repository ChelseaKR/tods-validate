"""The incident-response contract is checked, not described (IR-05/07/15/16/17).

`scripts/check_incident_contract.py` is a `make verify` gate. These pin what it
does with each shape it can meet, because two of its four checks are regression
guards that were already clean when they landed: a guard that has never had
anything to catch and a guard that is not looking render identically, and this
repository has shipped the second kind before.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_incident_contract.py"
TEMPLATE = ROOT / "docs" / "incidents" / "TEMPLATE.md"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_incident_contract", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rooted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    """The gate pointed at an empty tree, for building shapes into."""
    gate = _gate()
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "LABELS", tmp_path / ".github" / "labels.yml")
    monkeypatch.setattr(gate, "INCIDENTS", tmp_path / "docs" / "incidents")
    monkeypatch.setattr(gate, "TEMPLATE", tmp_path / "docs" / "incidents" / "TEMPLATE.md")
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    return gate


def test_the_repository_satisfies_its_own_contract() -> None:
    assert _gate().main() == 0


def test_the_committed_template_carries_every_required_section() -> None:
    # IR-07's list, verbatim from the standard. If the template loses one, every
    # postmortem written from it loses one too.
    gate = _gate()
    text = TEMPLATE.read_text(encoding="utf-8")
    for section in (*gate.REQUIRED_SECTIONS, *gate.REQUIRED_FIELDS):
        assert section in text, f"the template is missing {section}"


def test_a_postmortem_missing_a_section_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _rooted(monkeypatch, tmp_path)
    gate.INCIDENTS.mkdir(parents=True)
    gate.TEMPLATE.write_text(
        "\n".join([*gate.REQUIRED_SECTIONS, *gate.REQUIRED_FIELDS]), encoding="utf-8"
    )
    # Every section but "Root cause": the one a rushed postmortem drops.
    kept = [s for s in gate.REQUIRED_SECTIONS if s != "## Root cause"]
    (gate.INCIDENTS / "2026-08-27-example.md").write_text(
        "\n".join([*kept, *gate.REQUIRED_FIELDS]), encoding="utf-8"
    )
    problems, count = gate.check_postmortems()
    assert count == 2
    assert any("## Root cause" in p for p in problems)


def test_a_wildcard_git_add_in_automation_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # IR-15. Currently clean, so this is the only place the guard is shown to
    # work at all.
    gate = _rooted(monkeypatch, tmp_path)
    (tmp_path / "scripts" / "release.sh").write_text("set -eu\ngit add -A\n", encoding="utf-8")
    problems, scanned = gate.check_wildcard_add()
    assert scanned == 1
    assert any("IR-15" in p for p in problems)


def test_the_three_spellings_are_all_caught(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _rooted(monkeypatch, tmp_path)
    for index, spelling in enumerate(("git add -A", "git add --all", "git add .")):
        (tmp_path / "scripts" / f"s{index}.sh").write_text(f"{spelling}\n", encoding="utf-8")
    problems, _ = gate.check_wildcard_add()
    assert len(problems) == 3


def test_a_named_path_git_add_is_not_flagged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Positive control. A lint that flagged every `git add` would satisfy the
    # two tests above and be unusable.
    gate = _rooted(monkeypatch, tmp_path)
    (tmp_path / "scripts" / "release.sh").write_text("git add CHANGELOG.md\n", encoding="utf-8")
    problems, scanned = gate.check_wildcard_add()
    assert scanned == 1
    assert problems == []


def test_an_unscanned_scripted_commit_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _rooted(monkeypatch, tmp_path)
    (tmp_path / "scripts" / "bot.sh").write_text("git commit -m auto\n", encoding="utf-8")
    problems, sites = gate.check_commit_is_scanned()
    assert sites == 1
    assert any("IR-16" in p for p in problems)


def test_a_scanned_scripted_commit_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Positive control for the test above.
    gate = _rooted(monkeypatch, tmp_path)
    (tmp_path / "scripts" / "bot.sh").write_text(
        "gitleaks protect --staged\ngit commit -m auto\n", encoding="utf-8"
    )
    problems, sites = gate.check_commit_is_scanned()
    assert sites == 1
    assert problems == []


def test_a_missing_label_declaration_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = _rooted(monkeypatch, tmp_path)
    gate.LABELS.parent.mkdir(parents=True, exist_ok=True)
    gate.LABELS.write_text("labels:\n  - name: incident\n", encoding="utf-8")
    problems = gate.check_labels()
    assert any("sev1" in p for p in problems)


def test_the_committed_labels_file_declares_the_whole_set() -> None:
    assert _gate().check_labels() == []
