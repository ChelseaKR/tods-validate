# Data Governance Standard

The single owning standard for data rules that were previously scattered across four documents with no one accountable for the whole: `QUALITY-AND-METRICS-STANDARD.md` §10 (data cards, lineage), `RELEASE-AND-VERSIONING-STANDARD.md` §2 (dataset versioning), `RESPONSIBLE-TECH-FRAMEWORK.md` §C (DPIA method, retention commitments), and `OBSERVABILITY-STANDARD.md` §3 (PII-in-logs). Those documents keep the *mechanism* they already own — the DPIA audit method, the log-redaction gate, the tag-and-CHANGELOG mechanics — and now point here for the *policy*: what counts as sensitive data, how long it lives, where it's backed up, and what license/provenance an ingested civic dataset must carry. This is "reference, don't repeat" applied to data the same way it's already applied to security and accessibility.

**Why this exists.** Transit PII, rider/trip data, and identity-sensitive material require one explicit retention, lineage, and backup floor. A portfolio whose signature strength is responsible-tech rigor cannot leave the data floor itself unowned. Current per-project holdings and gaps live in the private data registry.

---

## 0. Scope, data classification, and applicability

Every repo classifies each data source/store it touches into exactly one tier. A repo with no data beyond its own source code declares `N/A` with that one-line reason; everything else picks a tier per source.

| Tier | Definition | Illustrative examples | Applies |
|---|---|---|---|
| **L0 — No data** | Repo processes no external or user data; source code and public docs only | documentation-only or source-only repository | Declares N/A with reason. |
| **L1 — Public, non-sensitive** | Openly licensed reference data with no personal or identity content | GTFS static feeds, public transit schedules, open civic datasets | §1–2 (data cards, lineage) apply; §3 retention is "keep as long as useful," no forced deletion; §4 backup applies. |
| **L2 — Aggregated / de-identified** | Derived data with direct identifiers removed but re-identification risk not zero | scored/aggregated ridership metrics, eval-harness benchmark results | Full standard; §5 (PII controls) applies defensively even though direct PII isn't stored. |
| **L3 — PII / identity-sensitive** | Direct personal data, rider trip/location data, or data whose exposure could out, deanonymize, or endanger a real person | rider trip endpoints, identity-sensitive records, or subject-monitoring data | Full standard, maximum rigor: encryption at rest, minimum retention, DPIA (via `RESPONSIBLE-TECH-FRAMEWORK.md` §C), breach-notification review (§6). |

**N/A is a declaration, not a default**, matching every other standard in this set. A repo declaring L0 states the reason in its README conformance table; silent omission is a defect.

---

## 1. Data cards — provenance, license, and lineage

Every ingested data source — not just AI training/eval data — gets a committed **data card**. This generalizes the model/dataset-card discipline `AI-EVALUATION-STANDARD.md` and `RESPONSIBLE-TECH-FRAMEWORK.md` §D already require for AI datasets to *every* ingest source, AI or not: GTFS feeds, civic open-data pulls, scraped or API-sourced reference data.

| Field | Requirement |
|---|---|
| Source | URL/API/publisher, and the legal entity responsible for it |
| License | SPDX identifier where applicable (`CC-BY-4.0`, `ODbL-1.0`, public-domain, or a plain-language statement where no SPDX id fits civic open-data terms) |
| Fetch/refresh cadence | How often re-pulled, and the staleness SLA (data older than the SLA is flagged, not silently served as current) |
| Fetch timestamp | Recorded per ingest run, machine-readable (not just "last updated" prose) |
| Tier | L0–L3 per §0 |
| Known limitations | Coverage gaps, known-stale segments, publisher caveats |
| Retention | Points to §3 for this source's specific retention line |

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Data card exists per ingest source [DG-01] | one committed `docs/data/<source>.md` (or a `data_cards/` directory) per distinct source | file-presence check in CI, enumerated against the repo's declared source list | AUTO-GATE |
| Every record traceable to source + fetch timestamp [DG-02] | schema includes a source + timestamp field on ingest | ingest-validation test asserts field presence and non-null | AUTO-GATE |
| Schema-validated on ingest [DG-03] | ingested records validated against a committed schema before use | schema-validation test (`jsonschema`/`pydantic`) in the ingest pipeline | AUTO-GATE |
| Staleness alarm [DG-04] | ingest older than the card's stated SLA raises a warning, surfaced in the app/report, not silently served as current | staleness check wired into the ingest job or `/readyz` | AUTO-GATE |
| License compatibility [DG-05] | ingested license compatible with the repo's own license and intended reuse (no closed-license civic data redistributed under an open repo license without carve-out) | REVIEW-GATE checklist item at the time a new source is added | REVIEW-GATE |

Applies in full to civic data products, monitoring pipelines, public maps, and
any civic RAG repository. Untrusted external inputs, including archives and
subprocess boundaries, additionally carry a Safety + Security note per
`QUALITY-AND-METRICS-STANDARD.md`'s ISO 25010 taxonomy — this standard owns the
data-card/license/lineage floor; the subprocess-sandboxing control itself is
owned by `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`.

---

## 2. Retention schedules

The floor every other document deferred. A retention line is not optional prose — it is a number (or "indefinite, with reason") per data tier, enforced by a scheduled deletion job where the tier requires it.

| Tier | Default retention | Deletion mechanism | Gate |
|---|---|---|---|
| **L1 — Public reference data** [DG-06] | Indefinite (it's the product) unless the publisher revokes/relicenses it, in which case removed within 30 days of notice | manual, tracked | REVIEW-GATE |
| **L2 — Aggregated/de-identified** [DG-07] | 24 months rolling, unless a repo states a longer research/audit justification in its data card | scheduled deletion job, tested | AUTO-GATE (job presence + test) |
| **L3 — PII/identity-sensitive** [DG-08] | **Minimum necessary, stated per source** — e.g., a rider query is retained only as long as needed to serve the response and any explicitly-consented history feature; default with no stated feature need is **do not retain past the request** | scheduled deletion job **required**, tested; no `|| true` on the deletion job any more than on a security gate | AUTO-GATE |
| **Backups of any tier** [DG-09] | Backup retention never exceeds live-data retention by more than one full backup cycle (§4) — a backup is not a loophole around a deletion promise | backup-rotation config asserts a max-age matching the tier | AUTO-GATE |

Retention lines are recorded in the repo's data card (§1) and its `docs/RESPONSIBLE-TECH-AUDITS.md` DPIA (methodology owned by `RESPONSIBLE-TECH-FRAMEWORK.md` §C — that document performs the privacy audit; this section is the retention-number floor it audits against). Deletion-on-request (subject-access/deletion path) for L3 data is a `RESPONSIBLE-TECH-FRAMEWORK.md` §C commitment; this standard requires the retention *schedule* that makes "deletion" a bounded, testable operation rather than an open-ended promise.

---

## 3. Backup & disaster-recovery expectations (local-first repos)

Local-first design can be a privacy feature, but it is not an excuse to skip
disaster recovery. "Local-first" means the *primary* copy is local; it does not
mean the *only* copy is local.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Backup existence [DG-10] | every repo with a persistent local data store (SQLite/DuckDB/on-disk index) documents a backup mechanism — even if that mechanism is "user-initiated export," it must be **documented and tested**, not assumed | README/docs section presence + an integration test exercising export/import round-trip | AUTO-GATE (round-trip test) |
| Encryption at rest for L3 backups [DG-11] | any backup containing L3 data is encrypted (age/GPG for file-based, sqlcipher for embedded DB) | test asserts the backup artifact is not plaintext-readable | AUTO-GATE |
| Recovery is tested, not assumed [DG-12] | a restore-from-backup path is exercised at least once per release cycle, not left as untested disaster-recovery theater | CI job or documented manual release-checklist step that restores into a scratch environment | REVIEW-GATE (or AUTO-GATE where automatable) |
| RPO/RTO stated [DG-13] | each deployed service states a Recovery Point Objective and Recovery Time Objective, even a generous one ("RPO 24h, RTO 48h" is a legitimate answer for a solo-maintainer civic tool) | `ROADMAP.md` Metrics row | REVIEW-GATE |
| No single point of failure for the standards system itself [DG-14] | standards and conformance artifacts are committed and replicated to an approved remote rather than existing only in one worktree | `git log` and the scheduled job show the artifact committed and replicated on the stated cadence | AUTO-GATE |

A local-first tool that stores nothing durable beyond ephemeral session state (a pure CLI filter, a stateless calculator) declares this section N/A with that reason.

---

## 4. PII, sensitive-data classification, and the log-redaction interface

`OBSERVABILITY-STANDARD.md` §3 owns the **mechanism** — structured logging, the `jq`-asserted no-secrets-no-PII gate, the OWASP Top 10:2025 A09 hard rule against logging passwords/tokens/PII. This standard owns the **classification**: what counts as PII/sensitive in this portfolio, so the observability gate has a definition to enforce rather than an ad hoc field-name list re-derived per repo.

**The portfolio PII/sensitive-field inventory (baseline — extend per repo, never narrow):**

| Category | Fields/examples | Tier |
|---|---|---|
| Credentials | passwords, session/access tokens, API keys, encryption keys, DB connection strings | L3 |
| Government/financial IDs | SSN, government ID numbers, payment-card data | L3 |
| Direct identity | name + contact combined with any of the below, email, DOB | L3 |
| Transit/location identity | rider trip endpoints, query history, precise location traces | L3 |
| Identity-inference-sensitive | any field that could out or deanonymize a subject even without a direct identifier; no-outing and no-identity-inference invariants are mandatory examples | L3 |
| Aggregated/derived | route-level ridership counts, benchmark scores with no individual trace | L2 |

`OBSERVABILITY-STANDARD.md`'s AUTO-GATE (`bandit` + custom `semgrep` rules asserting zero log calls pass a variable named from this list) is the enforcement; this table is the source of truth it's checked against. When a repo adds a new sensitive field, it is added here (or in the repo's own data card extension) *before* the observability gate can be expected to catch it — an unlisted field is a gap in this standard, not a false negative in the scanner.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Sensitive-field inventory current [DG-15] | every L3 field the repo processes appears in its data card or this table | REVIEW-GATE checklist at data-card authoring time | REVIEW-GATE |
| Log-redaction gate references this classification [DG-16] | `OBSERVABILITY-STANDARD.md` §3's field list is a superset of this table, not a divergent one | cross-document consistency, checked at doc-review time (no automated cross-file lint yet — tracked as a future `automation/` script) | REVIEW-GATE |

---

## 5. Dataset versioning — the policy layer over `RELEASE-AND-VERSIONING-STANDARD.md`

`RELEASE-AND-VERSIONING-STANDARD.md` §2 owns the *mechanism*: a `data-vN` tag or `dataset_version` field, versioned independently of code SemVer. This standard owns the *policy* that mechanism serves: **a dataset version is immutable and re-derivable.** Once `data-v3` is tagged, its contents never change; a correction ships as `data-v4` with a changelog line explaining what changed and why (matching the "no re-publish of a version" rule `RELEASE-AND-VERSIONING-STANDARD.md` already applies to code). The data card (§1) for a versioned dataset records the version, not just the source.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Dataset version tagged/fielded on every published data product [DG-17] | `data-vN` tag or `dataset_version` field present | presence check | AUTO-GATE (owned mechanically by `RELEASE-AND-VERSIONING-STANDARD.md` §2) |
| Dataset version is immutable [DG-18] | a published `data-vN` is never overwritten; corrections increment | registry/tag-protection check | AUTO-GATE |
| Data-card version linkage [DG-19] | the data card (§1) names the current dataset version and links prior versions' change notes | doc presence | REVIEW-GATE |

Applies to any repository that publishes a dataset as a consumable artifact
rather than using it only as internal ingest state.

---

## 6. Breach & unexpected-exposure review — the interface to `INCIDENT-RESPONSE-STANDARD.md`

When an incident (per `INCIDENT-RESPONSE-STANDARD.md`) involves L2/L3 data exposure, that standard's postmortem template's Impact section cross-references this one: the postmortem states which tier was exposed, whether the retention/backup controls in §2–3 held or failed, and whether a subject-notification obligation exists (a DPIA finding owned by `RESPONSIBLE-TECH-FRAMEWORK.md` §C, triggered by this section). This standard does not duplicate the incident process — it supplies the data-specific questions that process must answer when data, not just a credential, is what leaked.

---

## 7. What goes in each repo (reference, don't repeat)

1. **Data cards** (§1) under `docs/data/` per ingest source, each stating tier, license, retention line, and current dataset version where applicable.
2. **`ROADMAP.md` Metrics rows** for data-card presence, retention-job status, and backup round-trip test — owner named, gate stated.
3. **The README conformance table** carries a `Data Governance` row: `Applies`, `Applies — gap tracked in #NN`, or `N/A — <reason>` (L0 repos only).
4. **DPIA findings** stay in `docs/RESPONSIBLE-TECH-AUDITS.md` (methodology: `RESPONSIBLE-TECH-FRAMEWORK.md` §C) — this standard supplies the retention numbers and classification table that audit checks against, not a second copy of the audit itself.

---

Last verified: 2026-07-08 · Recheck cadence: on any change to a data source's license/terms, on any L3 field addition, after any data-exposure incident (§6), or quarterly.
