# Data card: the TODS specification

**Tier:** L1 (public, non-sensitive)

| Field | Value |
| --- | --- |
| Source | The Transit Operational Data Standard, <https://tods-transit.org/spec/>. Published by MobilityData and the TODS Board; the repository is `MobilityData/transit-operational-data-standard`. |
| Licence | The spec text is published openly by MobilityData. This repository redistributes no spec text verbatim beyond short quoted field and file names in rule descriptions and `docs/spec-questions.md`; the file and field inventory in `schema.py` is a transcription of a published table, not a copy of the document. |
| Fetch/refresh cadence | Not fetched at runtime, ever: `SECURITY.md` records that validation makes no network requests. The transcription in `schema.py` is refreshed by hand when the upstream spec moves. `.github/workflows/spec-watch.yml` runs `scripts/spec_watch.py` weekly against the published spec and opens an issue on drift, or on a comparison it could not make. |
| Fetch timestamp | `docs/spec-versions.md` records which spec versions are supported and what changed between them. The weekly spec-watch run's output is the machine-readable half. |
| Known limitations | Eight ambiguities in the published text are unresolved; they are listed in `docs/spec-questions.md` with the interpretation this validator takes and why. Where two published documents disagree, the disagreement is reported rather than resolved. |
| Retention | Indefinite (L1). The transcription is source code. |
