# Conformance corpus

`tests/fixtures/` is a small, growing corpus of TODS feeds an exporter or a
competing validator can test against:

- `tests/fixtures/valid/` — a complete, internally consistent feed (a TODS
  package plus its companion GTFS) that must validate with **zero** findings,
  however it is loaded (directory, zip, GTFS via `--gtfs` or alongside).
- `tests/fixtures/invalid/TODS-XXXX/` — one directory per rule, each a minimal
  feed crafted to trip exactly that rule.

The contract enforced in CI (`tests/test_conformance.py`):

1. There is exactly one fixture directory per registered rule, and vice versa.
2. Each `TODS-XXXX` fixture, validated with all opt-in categories enabled,
   produces the exact rule-ID set recorded in the committed
   `tests/fixtures/expectations.json` oracle. Cascading findings are therefore
   explicit and reviewed rather than silently accepted.
3. The valid feed produces no findings, even with opt-in rules enabled.

The release builder checks current results against that committed oracle and
refuses to build the archive if they differ. It does not generate expected
outcomes from the validator under test.

## Download

Each [GitHub release](https://github.com/ChelseaKR/tods-validate/releases)
attaches `tods-conformance-corpus.zip`: every fixture above, plus an
`expectations.json` mapping each fixture to the rule IDs it should produce, so
another validator can run the corpus and diff against expectations without
cloning this repo. Changes to expected outcomes are reviewed in source control
alongside the rule or fixture that motivates them. Build the same archive
locally with:

```sh
python scripts/build_conformance_corpus.py dist/tods-conformance-corpus.zip
```

## Using it to test your exporter

Point `tods-validate` at your own output and assert on the rule IDs you expect
(or expect none):

```python
from tods_validate import validate_feed

result = validate_feed("my-exporter/output/tods", gtfs="my-exporter/output/gtfs")
assert result.ok, [(f.rule_id, f.message) for f in result.errors]
```

For a drop-in pytest gate, `tods_validate.testing` wraps that pattern and raises
with the same human-readable report the CLI prints:

```python
from tods_validate.testing import assert_feed_valid, assert_feed_produces

def test_exporter_output_is_clean(tmp_path):
    my_exporter.write(tmp_path)
    assert_feed_valid(tmp_path / "tods", gtfs=tmp_path / "gtfs")

def test_dangling_trip_is_caught(tmp_path):
    my_exporter.write_with_dangling_trip(tmp_path)
    assert_feed_produces(tmp_path / "tods", "TODS-E307")
```

`assert_feed_valid` takes `fail_on="warning"` to gate on warnings too and
`ignore=[...]` for rule IDs you have decided to accept; `assert_feed_produces`
takes `exactly=True` to require the produced rule-ID set to match with nothing
extra. Both return the `ValidationResult` so a passing test can inspect further.
See [api.md](api.md#test-helpers).

## Contributing fixtures

Real-world feeds that expose gaps are the most valuable contribution. If you can
share one (privately is fine), please open an issue. Synthetic fixtures should
be minimal — just enough rows to trip the rule under test — and live under
`tests/fixtures/invalid/<RULE_ID>/`. Offering this corpus upstream as a shared
TODS conformance suite is tracked on the [roadmap](roadmap.md). The corpus and
a transfer or co-maintenance path have been offered to the TODS Board in
[MobilityData/transit-operational-data-standard#153](https://github.com/MobilityData/transit-operational-data-standard/issues/153).
Until the Board decides whether and where to adopt it, this remains a
downstream, validator-specific corpus rather than an official TODS suite.
