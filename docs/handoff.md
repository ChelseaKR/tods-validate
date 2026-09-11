# Handoff records: a go/no-go a receiver can check

A CAD/AVL integrator receives feeds they did not make. The `ingest-ready`
profile answers whether one should be imported, and `--stamp` says which tool
version answered, but neither ties the answer to the bytes that were handed
over. A handoff record does, and `handoff verify` checks it offline.

```sh
tods-validate handoff exports/tods --gtfs exports/gtfs --profile ingest-ready --out handoff.json
```

```text
tods-validate handoff: decision accept for exports/tods
  wrote handoff.json
```

The record carries the SHA-256 of every file in the package and its companion,
the settings the decision was made under, the coverage manifest, the merge
manifest, and the decision with the rule IDs behind it. The receiver checks it
against what they were sent:

```sh
tods-validate handoff verify handoff.json exports/tods --gtfs exports/gtfs
```

```text
verified: the record describes these bytes, and re-running under its settings reproduces it, decision 'accept'.
```

Change one time in one row and the same command says so, before any question
of validity arises:

```text
hashes differ: the record does not describe the bytes it was given.
package: run_events.txt differs (record 44b9be90…, given 9922a480…)
```

## What "accept" requires

Two things: nothing at or above the settings' `fail-on` severity, and every
check that wanted an input got one. The second is why a record made without a
companion GTFS feed is a reject even when the feed is clean:

```text
tods-validate handoff: decision reject for exports/tods
  17 check(s) could not run because an input was missing: OPS-W001, TODS-E205,
  TODS-E307, TODS-E308, TODS-E309, TODS-E310, TODS-E311, TODS-E312, TODS-E314,
  TODS-E405, TODS-I501, TODS-I502, TODS-W313, TODS-W315, TODS-W316, TODS-W406,
  TODS-W407
```

Those seventeen checks resolve references into the companion feed. A go/no-go
record that said "go" about references nobody resolved would be a confident
answer to a question nobody asked. This is `validate --require-complete-run`'s
rule, and a handoff always applies it.

## What is in the record

| key | what it is |
|---|---|
| `inputs.package.files`, `inputs.companion` | every top-level file, with its SHA-256 and size. `companion` is `null`, `{"source": "package"}` when the GTFS files sit beside the TODS ones, or `{"source": "flag", "files": [...]}` |
| `settings` | `failOn`, `enable`, `ignore`, `specVersion`, `encoding`, `severityRemap`, `maxImpliedSpeedKph`, and the profile's name. Resolved, because a profile is a preset this tool may change, and a record has to keep meaning what it meant |
| `coverage` | the report's coverage manifest, so a skipped check is visible in the record itself |
| `merge` | the supplement merge's per-file accounting and a digest of each file it writes, or why no merged feed could be produced |
| `decision`, `decisionBasis` | `accept` or `reject`, with `blockingRules` and `checksNotRun` |
| `summary` | error, warning and info counts |

`docs/handoff.schema.json` describes it. There is **no timestamp**: the record
is a function of the input bytes, the settings and the tool version, so
verification recomputes it and compares rather than trusting it.

## Exit codes

`handoff` exits 0 when the decision is accept and 1 when it is reject. The
record is written either way, so a rejected feed still comes with the artifact
saying why.

`handoff verify` exits:

- **0** the record matches: same bytes, and re-running its settings reproduces it;
- **1** not reproduced. Its decision was changed, or something else it states
  is not what these bytes produce. Everything but the tool block is compared,
  so a record whose decision was left alone and whose coverage was edited to
  hide a skipped check fails here too;
- **2** the files differ from the ones it hashed, the record cannot be read, or
  a requested signature does not verify.

A record written by one version of `tods-validate` and checked by another can
legitimately differ, because the rules may have changed. Verification says so
in a note rather than hiding it.

## Signing a record

Optional, and it uses the same SSH convention as the release tags, in a
namespace of its own (`tods-validate-handoff`) so that a tag's signature can
never be replayed as a signature over a record:

```sh
tods-validate handoff exports/tods --gtfs exports/gtfs --out handoff.json --sign-key ~/.ssh/id_ed25519
tods-validate handoff verify handoff.json exports/tods --gtfs exports/gtfs \
  --allowed-signers signers.txt --signer alice@example.org
```

`signers.txt` is an `ssh-keygen` allowed-signers file, and its entry should
name the namespace:

```text
alice@example.org namespaces="tods-validate-handoff" ssh-ed25519 AAAAC3Nza...
```

The signature is checked before anything else, so a tampered record fails as a
signature problem rather than as a decision difference.

## What this is not

A handoff record is a file the sender delivers. There is no registry, no
server, and nothing phones home. It is not a conformance certificate either:
it says what this validator decided about these bytes under stated settings,
which is a different claim from the TODS Board's.
