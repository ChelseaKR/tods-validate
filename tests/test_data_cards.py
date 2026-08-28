"""Every declared data source has a card, and every card a source (DG-01).

`scripts/check_data_cards.py` is a `make verify` gate. These pin the four
mismatches it exists to catch, because a file-presence check that only ever
sees a matching set is indistinguishable from one that is not looking.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_data_cards.py"


def _gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_data_cards", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sources: list[dict[str, object]],
    cards: dict[str, str],
) -> ModuleType:
    gate = _gate()
    cards_dir = tmp_path / "docs" / "data"
    cards_dir.mkdir(parents=True)
    (cards_dir / "sources.json").write_text(json.dumps({"sources": sources}), encoding="utf-8")
    for name, body in cards.items():
        (cards_dir / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "CARDS", cards_dir)
    monkeypatch.setattr(gate, "SOURCES", cards_dir / "sources.json")
    return gate


def _card(tier: str) -> str:
    return f"# Data card\n\n**Tier:** {tier}\n"


def test_the_repository_satisfies_its_own_contract() -> None:
    assert _gate().main() == 0


def test_a_declared_source_with_no_card_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    gate = _tree(monkeypatch, tmp_path, [{"id": "ridership", "tier": "L2"}], {})
    assert any("has no docs/data/ridership.md" in p for p in gate.check())


def test_a_card_with_no_declared_source_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The direction a plain file-presence check misses: a card can be added
    # without the list knowing, and then nothing enumerates it.
    gate = _tree(
        monkeypatch,
        tmp_path,
        [{"id": "known", "tier": "L1"}],
        {"known.md": _card("L1"), "stray.md": _card("L1")},
    )
    assert any("stray.md describes a source" in p for p in gate.check())


def test_a_card_and_the_list_disagreeing_about_tier_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Both look authoritative, which makes the disagreement worse than either
    # being absent.
    gate = _tree(monkeypatch, tmp_path, [{"id": "feeds", "tier": "L3"}], {"feeds.md": _card("L1")})
    assert any("says tier L1 but sources.json says L3" in p for p in gate.check())


def test_a_source_pointing_at_a_deleted_path_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # File-presence checks are exactly the kind that keep passing after their
    # subject leaves.
    gate = _tree(
        monkeypatch,
        tmp_path,
        [{"id": "feeds", "tier": "L1", "paths": ["gone/"]}],
        {"feeds.md": _card("L1")},
    )
    assert any("which does not exist" in p for p in gate.check())


def test_a_matching_set_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Positive control for all four above, which a gate that always reported a
    # problem would satisfy.
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    gate = _tree(
        monkeypatch,
        tmp_path,
        [{"id": "feeds", "tier": "L3", "paths": ["src"]}],
        {"feeds.md": _card("L3"), "README.md": "an index, not a card"},
    )
    assert gate.check() == []


def test_the_l3_boundary_is_stated_rather_than_omitted() -> None:
    # The judgement this directory turns on: a user's feed is L3 by content and
    # is not a source this project can claim a licence or retention line over.
    # If that card is ever dropped, the omission would read as "no L3 data
    # here", which is the opposite of true.
    card = ROOT / "docs" / "data" / "user-supplied-feeds.md"
    text = card.read_text(encoding="utf-8")
    assert "**Tier:** L3" in text
    assert "Not retained" in text or "not retained" in text
    for field in ("employee_id", "license_plate", "vehicle_label"):
        assert field in text, f"the L3 card does not name {field}"
