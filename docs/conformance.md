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
   produces a finding with rule ID `TODS-XXXX`.
3. The valid feed produces no findings, even with opt-in rules enabled.

## Using it to test your exporter

Point `tods-validate` at your own output and assert on the rule IDs you expect
(or expect none):

```python
from tods_validate import validate_feed

result = validate_feed("my-exporter/output/tods", gtfs="my-exporter/output/gtfs")
assert result.ok, [(f.rule_id, f.message) for f in result.errors]
```

To regression-test that a known-bad input still trips the right rule, compare
the set of rule IDs against a recorded expectation.

## Contributing fixtures

Real-world feeds that expose gaps are the most valuable contribution. If you can
share one (privately is fine), please open an issue. Synthetic fixtures should
be minimal — just enough rows to trip the rule under test — and live under
`tests/fixtures/invalid/<RULE_ID>/`. Offering this corpus upstream as a shared
TODS conformance suite is tracked on the [roadmap](roadmap.md).
