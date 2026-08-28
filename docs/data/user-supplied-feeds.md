# Data card: a user's own TODS feed

**Tier:** L3 (identity-sensitive) **by content, and not a source of this repository.**

This card exists to make a boundary explicit rather than to claim one. A user's
feed is the *input* to a local validator. This project does not fetch it, does
not store it, does not transmit it, and has no standing to state a licence, a
refresh cadence, or a retention policy over an agency's operational records.
Writing a card that asserted any of the three would be a governance claim over
somebody else's data.

| Field | Value |
| --- | --- |
| Source | The person running the tool. Never fetched by this project. |
| Licence | The feed owner's. Not this project's to state. |
| Fetch/refresh cadence | Not applicable. Nothing is fetched: `SECURITY.md` records that validation, merge, stats, and anonymize make no network requests, and CI has no test that would pass if one did. |
| Fetch timestamp | Not applicable. |
| Known limitations | The tool sees whatever the user points it at, including fields it has no rule for. `anonymize` reports every column it did **not** pseudonymize (`AnonymizeResult.carried_through`), because a residual-risk list the caller has to read is more honest than a claim of coverage. |
| Retention | **Not retained.** Process lifetime only. No cache, no telemetry, no accounts. |

## Which fields make this L3

Per the portfolio sensitive-field inventory, the direct-identity and
transit-identity rows:

| Field | File | Why |
| --- | --- | --- |
| `employee_id` | `employee_run_dates.txt` | Direct identity of a named worker, tied to a date and a run. |
| `license_plate` | `vehicles.txt` | Vehicle identity, correlatable to an operator via a roster. |
| `vehicle_label` | `vehicles.txt` | The painted fleet number: correlates 1:1 with a pseudonymized `vehicle_id` for anyone with a photograph of the bus. |

`anonymize` pseudonymizes all three, and its own documentation says
pseudonymization is not anonymity: correlation with other data may still
re-identify. `docs/RESPONSIBLE-TECH-AUDITS.md` section C carries the DPIA-lite,
including the threat model for the people in the data and the reason no
subject-access or deletion path applies (this tool holds no data of theirs).

## What would change this card

An agency sharing a real feed for #76. At that point the feed becomes something
this project *holds*, even briefly and even privately, and the retention line
above stops being true by construction and has to be made true by policy.
