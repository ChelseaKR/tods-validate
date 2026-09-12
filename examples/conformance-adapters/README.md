# Conformance adapters

An adapter tells `tods-validate conformance run` how to read rule identifiers
out of another validator's output. Two are here: the one that reads this
project's own JSON report, and a worked example for a validator that prints
prose.

`tods-validate.json` is the adapter `tests/test_conformance_harness.py` runs
against real fixtures, so it cannot drift from the report format it describes.

## Fields

| Field | Meaning |
| --- | --- |
| `name` | Whose output this reads. Appears in every report. |
| `strategy` | `json` or `regex`. |
| `source` | `stdout` (default), `stderr`, or `combined`. |
| `pointer` | `json` only. A path like `/findings/-/rule_id`, where `-` means every element of the array at that step. |
| `pattern` | `regex` only. One capture group, holding the identifier. |
| `no_findings_pattern` | `regex` only, and required. What the tool prints when it reports nothing. |
| `map` | Optional. That validator's identifiers to `TODS-` rule ids. Anything unmapped is compared as-is. |

## Why `no_findings_pattern` is not optional

A `json` adapter can tell "the validator found nothing" from "I could not read
this" structurally: `{"findings": []}` has the array, and a document without it
does not. A regular expression cannot. Both cases produce zero matches, and the
`valid` fixture expects zero rules — so without a second expression, an adapter
pointed at the wrong stream would report agreement on the one fixture where
reading nothing looks exactly like being right.
