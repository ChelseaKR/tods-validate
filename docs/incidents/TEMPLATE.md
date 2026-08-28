# Incident: one-line description of what happened - YYYY-MM-DD

**Severity:** SEV1 | SEV2 | SEV3 | SEV4
**Status:** Resolved | Monitoring | Postmortem-only (near-miss)
**Related issue:** #NN

## Summary

Two or three sentences: what happened, what was affected, how it ended.

## Timeline (UTC)

| Time | Event |
| --- | --- |
| YYYY-MM-DD HH:MM | Detected |
| YYYY-MM-DD HH:MM | Acknowledged |
| YYYY-MM-DD HH:MM | Contained or mitigated |
| YYYY-MM-DD HH:MM | Resolved |

## Impact

Who or what was affected, and for how long. For anything data-adjacent, state
whether data was exposed; that answer triggers the breach-notification review
in `docs/standards/DATA-GOVERNANCE-STANDARD.md`, so it is never left implicit.

## Detection

How this was found. "Found by accident" is a valid answer and is itself an
action item: it means no gate was watching.

## Root cause

Five Whys or equivalent, framed systemically. What made this possible, not who
did it.

## What went well

- 

## What went poorly

- 

## Action items

| Action | Owner | Due | Tracking issue |
| --- | --- | --- | --- |
|  |  |  |  |

## Related

The `incident` issue, the pull requests, the affected release or tag, and for a
leaked credential the rotation record from
[`../runbooks/secret-exposure.md`](../runbooks/secret-exposure.md).
