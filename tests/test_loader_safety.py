"""Input-safety and encoding handling in the loader."""

import zipfile
from pathlib import Path

import pytest

from tods_validate.loader import (
    MAX_COMPRESSION_RATIO,
    PackageNotFoundError,
    UnsafeArchiveError,
    load_package,
)


def test_missing_path_message_names_cwd() -> None:
    with pytest.raises(PackageNotFoundError, match="does not exist"):
        load_package("no-such-feed-xyz")


def test_path_traversal_member_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "a,b\n1,2\n")
    with pytest.raises(UnsafeArchiveError, match="escapes the package"):
        load_package(archive)


def test_zip_bomb_ratio_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bomb.zip"
    # Highly compressible content trips the ratio guard.
    payload = ("a,b\n" + "1,2\n" * 2_000_000).encode("utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("run_events.txt", payload)
    with zipfile.ZipFile(archive) as zf:
        info = zf.getinfo("run_events.txt")
        assert info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO
    with pytest.raises(UnsafeArchiveError, match="zip bomb"):
        load_package(archive)


def test_encoding_problem_detected_and_overridable(tmp_path: Path) -> None:
    feed = tmp_path / "feed"
    feed.mkdir()
    (feed / "vehicles.txt").write_bytes(b"vehicle_id,vehicle_label\nbus-1,Caf\xe9\n")

    default = load_package(feed)
    problems = default.files["vehicles.txt"].problems
    assert any(p.code == "encoding" for p in problems)
    assert "Latin-1" in problems[0].message

    overridden = load_package(feed, encoding="latin-1")
    assert overridden.files["vehicles.txt"].problems == []
    assert overridden.files["vehicles.txt"].rows[0].values["vehicle_label"] == "Café"
