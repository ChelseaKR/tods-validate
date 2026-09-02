# Data cards

One card per data source this repository *ingests and ships*, per
`docs/standards/DATA-GOVERNANCE-STANDARD.md` DG-01. Each states its tier (L0 to
L3), licence, refresh cadence, known limitations, and retention line.

`scripts/check_data_cards.py` enumerates the declared source list in
[`sources.json`](sources.json) against the cards in this directory and fails
the build when they disagree, in either direction. DG-01 is an AUTO-GATE, and
the portfolio's definition of that (`QUALITY-AND-METRICS-STANDARD.md`) is
merge-blocking in CI with no `|| true` and no `continue-on-error`.

## The boundary this repository has to be careful about

The interesting data here is the data this repository **does not** hold.

A user's TODS feed is the input to a validator that runs locally, holds it for
the lifetime of one process, and writes nothing back. That feed can carry
`employee_id`, `license_plate`, and `vehicle_label`, all of which the sensitive
-field inventory classifies **L3**. It is not a source of this repository and
it gets no card here, because a card asserts a licence, a refresh cadence, and
a retention line, and this project has no standing to assert any of the three
about somebody else's operational data. Claiming otherwise would be a
governance claim over an agency's records.

What the project does say about that data lives where it belongs:
`SECURITY.md` (no network, no retention), `docs/RESPONSIBLE-TECH-AUDITS.md`
section C (the DPIA-lite and its threat model), and the `anonymize` command,
whose own documentation says it pseudonymizes rather than anonymizes.

[`user-supplied-feeds.md`](user-supplied-feeds.md) records that reasoning as a
card-shaped document anyway, so the boundary is explicit rather than an
omission. It is the one entry whose Retention line reads "not retained".
