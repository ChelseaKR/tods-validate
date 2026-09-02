# Incidents

One committed postmortem per closed `incident` issue, as
`YYYY-MM-DD-<slug>.md` in this directory. Not a GitHub issue comment: a
comment is not diffable, not reviewable, and not there when the issue is.

`docs/standards/INCIDENT-RESPONSE-STANDARD.md` is the contract. The short
version:

- **Required sections** (IR-07): Summary, Severity, Timeline (UTC), Impact,
  Detection, Root cause, What went well, What went poorly, Action items with
  owner and due date, and Related links. `scripts/check_incident_contract.py`
  fails on a file in this directory missing any of them, so a postmortem
  cannot be half-written and still committed.
- **Cadence** (IR-06): SEV1 and SEV2 within 7 days of resolution, SEV3 within
  14, SEV4 optional and encouraged as a one-paragraph near-miss note.
- **Blameless** (IR-08): no individual named as a cause. Systemic framing.
- **Backfills are allowed** and must say so. Unknown fields stay explicitly
  unknown rather than being invented.

Start from [`TEMPLATE.md`](TEMPLATE.md). For a leaked credential, work
[`../runbooks/secret-exposure.md`](../runbooks/secret-exposure.md) first and
write the postmortem after; rotation comes before documentation.

## What is here

Nothing yet, and that is a statement rather than an absence: no incident
meeting the SEV1 to SEV4 bar has been opened since this repository adopted the
convention on 2026-08-27. Three past events would have qualified had it
existed then, and are named in
[`../MULTIYEAR-PLAN.md`](../MULTIYEAR-PLAN.md) phase 4 rather than backfilled
here, because backfilling a timeline nobody recorded would invent the one
thing a postmortem is for.
