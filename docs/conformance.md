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
alongside the rule or fixture that motivates them. In the archive, `valid/`
holds the TODS and companion GTFS files in one flat directory, so each fixture
validates with a bare `tods-validate validate <fixture>/` plus the opt-in
category flags; the README inside the archive lists the exact commands. The
archive is byte-for-byte reproducible from the same source tree. Build it
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

## Comparing another validator against the corpus

The corpus is published so someone else can run it, and "run it and diff the
result against `expectations.json`" used to be left to each reader.
`tods-validate conformance run` is that step:

```sh
tods-validate conformance run \
  --command "other-validator --json {path}" \
  --corpus tods-conformance-corpus.zip \
  --adapter examples/conformance-adapters/text-output.json \
  --format markdown
```

Each fixture directory is executed as its own subprocess with `{path}`
substituted (the template is split into a word list first, so a path with a
space stays one argument; no shell is involved). The rule identifiers are read
back out of that command's own output through the adapter, and compared with
the fixture's entry in `expectations.json`.

Every report names the corpus digest it ran against, and states how many
fixtures were **compared** as well as how many agreed — `42 agree` and
`42 agree, 5 never ran` are different results.

### Outcomes and exit codes

| Outcome | Meaning |
| --- | --- |
| `agrees` | The reported rule set is exactly the expected one. |
| `disagrees` | Listed with what was reported and not expected, and expected and not reported. |
| `unreadable` | The adapter could not read that run's output, or the command could not be started. |
| `timed_out` | The command did not finish within `--timeout`. Only that fixture. |

Exit `0` only when every fixture was compared and every comparison agreed, `1`
when some fixture disagreed, and `2` when any fixture could not be compared at
all. A corpus that was not fully run has not been passed, so the third case is
its own code rather than folded into either of the others.

Nothing here judges which side is right. A disagreement is a question about one
implementation or about the spec text, and that is the signal the corpus exists
to give.

### Adapters

An adapter is a small JSON file saying how to get rule identifiers out of one
validator's output. Two worked examples ship in
[`examples/conformance-adapters/`](../examples/conformance-adapters/), whose
README documents every field.

The one rule worth repeating here: **an adapter that reads nothing reports
`unreadable`, never `agrees`.** The `valid` fixture expects no rules, so a
reader pointed at the wrong stream would agree with it by accident. A `json`
adapter separates the two structurally — `{"findings": []}` has the array, a
document without it does not — and a `regex` adapter is therefore required to
declare `no_findings_pattern`, matching what the tool prints when it is happy.

### Running it against tods-validate itself

The self-comparison is the harness's own sanity check, and it is one command:

```sh
python scripts/build_conformance_corpus.py dist/tods-conformance-corpus.zip
tods-validate conformance run \
  --command "tods-validate validate {path} --format json --enable coverage \
             --enable advisory --enable experimental --enable feasibility" \
  --corpus dist/tods-conformance-corpus.zip \
  --adapter examples/conformance-adapters/tods-validate.json
```

Measured on 2026-09-10 at 0.11.0: **47 of 47 fixtures compared, 47 agree**. The
test suite runs the same comparison over three fixtures rather than all
forty-seven, because each fixture is a subprocess and the suite is a merge
gate; the three include `valid`, which is the one the fail-closed rule is
about.

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
The maintainer's privacy-preserving evidence policy for feeds already used in
development is documented in
[`production-feed-validation.md`](production-feed-validation.md).
