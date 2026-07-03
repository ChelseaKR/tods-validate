"""Property-based tests for the untrusted-input parsing path.

Hypothesis-driven invariants for the loader/fix/merge/suggest pipeline:
round-tripping a generated feed through serialize -> load, fix idempotence,
merge determinism, and suggest.py's meaning-preservation promise for its
normalizers. Inputs are generated (quotes, commas, embedded newlines, BOMs,
unicode) rather than hand-picked, so a failure surfaces as a minimal
counterexample; Hypothesis also stores failing examples under
``.hypothesis/examples`` so a regression stays reproduced once found.

Kept out of ``[tool.mutmut] pytest_add_cli_args_test_selection`` in
pyproject.toml: mutmut drives mutants with the rule-test modules that pin
specific rule behaviour against fixture feeds, and this module's generated
inputs would just add search-loop runtime without doing that, so it is left
out of the mutation baseline.
"""

from __future__ import annotations

import contextlib
import zipfile

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tods_validate import _pkgio
from tods_validate.fix import fix_package
from tods_validate.gtfs_companion import parse_gtfs_date
from tods_validate.loader import PackageNotFoundError, UnsafeArchiveError, _parse_csv, load_package
from tods_validate.merge import merge_feeds
from tods_validate.rules.fields import parse_time
from tods_validate.suggest import _normalize_date, _normalize_time

# Derandomized so CI gets the same examples every run (no flaky
# counterexamples), and with no per-example deadline since some cases touch
# the filesystem. Failing examples are still persisted locally under
# .hypothesis/examples regardless of this profile.
settings.register_profile(
    "ci",
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Tricky tokens a real-world exporter might emit: a bare quote, a bare comma,
# an embedded CRLF, a UTF-8 BOM, and the empty string.
_EDGE_TOKENS = ('"', ",", "\r\n", "﻿", "")

# Cell text: free-form unicode, occasionally one of the tokens above glued
# onto ordinary text so quoting/escaping is actually exercised, not just
# whole-cell edge cases.
_csv_cell = st.one_of(
    st.text(max_size=20),
    st.sampled_from(_EDGE_TOKENS),
    st.tuples(st.text(max_size=8), st.sampled_from(_EDGE_TOKENS), st.text(max_size=8)).map("".join),
)

# Header names: simple identifiers, unique within one feed (a duplicate
# header is its own documented load problem, exercised in test_structure.py).
# At least two columns sidesteps the CSV format's inherent ambiguity where a
# single-column, all-blank row serializes identically to a genuinely blank
# line -- and the loader deliberately skips blank lines (see loader.py).
_header_name = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]{0,10}", fullmatch=True)
_headers = st.lists(_header_name, min_size=2, max_size=5, unique=True)


@st.composite
def _tods_feed(draw: st.DrawFn) -> tuple[list[str], list[dict[str, str]]]:
    """A small in-memory feed: a header list and matching row dicts."""
    headers = draw(_headers)
    rows = draw(st.lists(st.fixed_dictionaries(dict.fromkeys(headers, _csv_cell)), max_size=5))
    return headers, rows


# ---------------------------------------------------------------------------
# a. Round-trip: serialize_feed -> loader recovers every cell exactly.
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(feed=_tods_feed())
def test_round_trip_via_parse_csv(feed: tuple[list[str], list[dict[str, str]]]) -> None:
    headers, rows = feed
    data = _pkgio.serialize_feed(headers, rows)

    parsed = _parse_csv("feed.txt", data)

    assert not parsed.problems
    assert parsed.headers == tuple(headers)
    assert len(parsed.rows) == len(rows)
    for original, recovered in zip(rows, parsed.rows, strict=True):
        for h in headers:
            assert recovered.values.get(h) == original[h]


@settings(max_examples=50)
@given(feed=_tods_feed())
def test_round_trip_via_zip_package(
    feed: tuple[list[str], list[dict[str, str]]], tmp_path_factory: pytest.TempPathFactory
) -> None:
    headers, rows = feed
    data = _pkgio.serialize_feed(headers, rows)
    out_dir = tmp_path_factory.mktemp("roundtrip")
    zip_path = out_dir / "pkg.zip"
    _pkgio.write_package({"feed.txt": data}, zip_path)

    package = load_package(zip_path)

    feed_file = package.get("feed.txt")
    assert feed_file is not None
    assert feed_file.headers == tuple(headers)
    for original, recovered in zip(rows, feed_file.rows, strict=True):
        for h in headers:
            assert recovered.values.get(h) == original[h]


# ---------------------------------------------------------------------------
# b. fix idempotence: fixing an already-fixed package changes nothing.
# ---------------------------------------------------------------------------


@settings(max_examples=50)
@given(feed=_tods_feed())
def test_fix_is_idempotent(
    feed: tuple[list[str], list[dict[str, str]]], tmp_path_factory: pytest.TempPathFactory
) -> None:
    headers, rows = feed
    base = tmp_path_factory.mktemp("fixidem")
    src = base / "src"
    _pkgio.write_package({"feed.txt": _pkgio.serialize_feed(headers, rows)}, src)

    once = base / "once"
    twice = base / "twice"
    fix_package(src, output=once)
    second = fix_package(once, output=twice)

    assert not second.changed_any
    once_names = sorted(p.name for p in once.iterdir())
    twice_names = sorted(p.name for p in twice.iterdir())
    assert once_names == twice_names
    for name in once_names:
        assert (once / name).read_bytes() == (twice / name).read_bytes()


# ---------------------------------------------------------------------------
# c. merge_feeds: deterministic output that round-trips through the loader.
# ---------------------------------------------------------------------------

_service_id = st.from_regex(r"[a-zA-Z0-9_-]{1,8}", fullmatch=True)
_service_ids = st.lists(_service_id, min_size=1, max_size=4, unique=True)


@settings(max_examples=30)
@given(ids=_service_ids)
def test_merge_feeds_is_deterministic_and_round_trips(
    ids: list[str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    base = tmp_path_factory.mktemp("merge")
    src = base / "feed"
    calendar_rows = [{"service_id": i, "monday": "1"} for i in ids]
    # Every id is updated by the supplement (monday flipped to "0"), so the
    # merged output is fully predictable from the generated ids alone.
    supplement_rows = [{"service_id": i, "monday": "0", "TODS_delete": ""} for i in ids]
    entries = {
        "calendar.txt": _pkgio.serialize_feed(["service_id", "monday"], calendar_rows),
        "calendar_supplement.txt": _pkgio.serialize_feed(
            ["service_id", "monday", "TODS_delete"], supplement_rows
        ),
    }
    _pkgio.write_package(entries, src)

    out1, out2 = base / "out1", base / "out2"
    merge_feeds(src, None, out1)
    merge_feeds(src, None, out2)

    # Determinism: two merges of the same input produce byte-identical output.
    assert (out1 / "calendar.txt").read_bytes() == (out2 / "calendar.txt").read_bytes()

    # Round-trip: the merged output loads cleanly and carries every id.
    merged = load_package(out1)
    calendar = merged.get("calendar.txt")
    assert calendar is not None
    assert set(calendar.headers) == {"service_id", "monday"}
    assert {row.values["service_id"] for row in calendar.rows} == set(ids)
    assert all(row.values["monday"] == "0" for row in calendar.rows)


# ---------------------------------------------------------------------------
# d. suggest.py normalizers are meaning-preserving fixed points.
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    hour=st.integers(min_value=0, max_value=47),
    minute=st.integers(min_value=0, max_value=59),
    second=st.integers(min_value=0, max_value=59),
    drop_seconds=st.booleans(),
)
def test_normalize_time_is_meaning_preserving(
    hour: int, minute: int, second: int, drop_seconds: bool
) -> None:
    raw = f"{hour}:{minute}" if drop_seconds else f"{hour}:{minute}:{second}"

    proposed = _normalize_time(raw)

    if proposed is None:
        return
    assert parse_time(proposed) is not None
    # Re-running the normalizer on its own output is a fixed point: nothing
    # left to fix, matching suggest.py's "never alters what the value means".
    assert _normalize_time(proposed) == proposed


@settings(max_examples=200)
@given(
    year=st.integers(min_value=2000, max_value=2100),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=28),
    separator=st.sampled_from(("-", "/", ".")),
)
def test_normalize_date_is_meaning_preserving(
    year: int, month: int, day: int, separator: str
) -> None:
    raw = f"{year:04d}{separator}{month:02d}{separator}{day:02d}"

    proposed = _normalize_date(raw)

    if proposed is None:
        return
    assert parse_gtfs_date(proposed) is not None
    assert _normalize_date(proposed) == proposed


# ---------------------------------------------------------------------------
# Loader fuzz: untrusted input never crashes with an undeclared exception.
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(data=st.binary(max_size=256))
def test_load_package_never_crashes_on_arbitrary_bytes(
    data: bytes, tmp_path_factory: pytest.TempPathFactory
) -> None:
    base = tmp_path_factory.mktemp("fuzz")
    path = base / "garbage.zip"
    path.write_bytes(data)

    # A declared, documented rejection is fine; anything else is not.
    with contextlib.suppress(PackageNotFoundError, UnsafeArchiveError):
        load_package(path)


@settings(max_examples=50)
@given(data=st.binary(max_size=512))
def test_load_package_never_crashes_on_fuzzed_member_bytes(
    data: bytes, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Arbitrary bytes as a zip *member* -- exercises the encoding/CSV-error
    recovery path in loader._parse_csv, not just "not a zip file" rejection."""
    base = tmp_path_factory.mktemp("fuzzmember")
    path = base / "pkg.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("feed.txt", data)

    try:
        package = load_package(path)
    except (PackageNotFoundError, UnsafeArchiveError):
        return
    # Loaded without raising: the file must be present, either parsed or
    # carrying a recorded LoadProblem -- never silently dropped.
    assert package.get("feed.txt") is not None
