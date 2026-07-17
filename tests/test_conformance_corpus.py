"""The conformance corpus builder produces a complete, self-consistent archive."""

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_conformance_corpus.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_conformance_corpus", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_corpus_builds_with_consistent_expectations(tmp_path: Path) -> None:
    builder = _load_builder()
    out = tmp_path / "corpus.zip"
    expectations = builder.build(out)
    assert out.is_file()
    assert expectations["valid"] == []  # the valid feed produces nothing
    assert "TODS-E204" in expectations["invalid/TODS-E204"]
    assert "TODS-W315" in expectations["invalid/TODS-W315"]
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert {"expectations.json", "README.md"} <= names
        assert any(n.startswith("invalid/TODS-E204/") for n in names)
        # valid/ is flattened: TODS and GTFS files share one directory so a
        # bare `tods-validate validate valid/` needs no --gtfs flag.
        assert "valid/run_events.txt" in names
        assert "valid/trips.txt" in names
        assert not any(n.startswith(("valid/tods/", "valid/gtfs/")) for n in names)
        embedded = json.loads(zf.read("expectations.json"))
    assert embedded == expectations  # the manifest in the zip matches the return value


def test_extracted_valid_feed_is_clean_without_flags(tmp_path: Path) -> None:
    from tods_validate.rules import CATEGORIES
    from tods_validate.runner import run

    builder = _load_builder()
    out = tmp_path / "corpus.zip"
    builder.build(out)
    with zipfile.ZipFile(out) as zf:
        zf.extractall(tmp_path / "corpus")
    _, findings = run(tmp_path / "corpus" / "valid", None, enabled=frozenset(CATEGORIES))
    assert findings == []


def test_corpus_build_is_byte_deterministic(tmp_path: Path) -> None:
    builder = _load_builder()
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    builder.build(a)
    builder.build(b)
    assert a.read_bytes() == b.read_bytes()


def test_corpus_has_one_fixture_per_rule(tmp_path: Path) -> None:
    from tods_validate.rules import all_rules

    builder = _load_builder()
    expectations = builder.build(tmp_path / "corpus.zip")
    invalid = {k.removeprefix("invalid/") for k in expectations if k.startswith("invalid/")}
    assert invalid == {r.id for r in all_rules()}


def test_corpus_build_rejects_unreviewed_expectation_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = _load_builder()
    monkeypatch.setattr(builder, "_rule_ids", lambda path, gtfs=None: [])
    with pytest.raises(RuntimeError, match="expectations.json"):
        builder.build(tmp_path / "corpus.zip")
