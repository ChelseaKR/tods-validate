# Synthetic persona research: remediations and expansions

A structured, synthetic user-research exercise for `tods-validate`. The goal
is breadth: assemble a wide range of plausible users across the TODS / GTFS
transit-data ecosystem, "interview" each on how they would use the validator
today and what they would want next, then consolidate everything into a
prioritized backlog of **remediations** (fixes and gaps inside the current
scope) and **expansions** (new scope).

> **Method and honesty note.** These personas are *synthetic* — composites
> assembled by reasoning about the real TODS/GTFS ecosystem and the actual
> state of this codebase (`README.md`, `docs/rules.md`, `docs/roadmap.md`,
> `docs/spec-questions.md`, `src/tods_validate/`). They are not real
> interviews and carry no empirical weight. Treat the output as a structured
> idea-generation and triage artifact: a way to pressure-test the roadmap from
> many angles, not as evidence of demand. Every item is cross-referenced to
> the current product so it can be checked against reality. Validate the
> highest-priority items with real users before committing engineering time.

Current product baseline (v0.3.0, as read from the repo on 2026-06-20):

- CLI `tods-validate` with `validate` (default), `merge`, and `rules`
  subcommands; `--gtfs`, `--format {text,json,markdown,github}`, `--fail-on`,
  `--ignore`, `--config`.
- 35+ rules across structure (x1xx), field values (x2xx), references (x3xx),
  and semantics (x4xx); stable IDs; generated `docs/rules.md`.
- `merge` materializes the "TODS-Supplemented GTFS" for handoff to
  MobilityData's gtfs-validator.
- Distribution: PyPI/pipx, GHCR Docker image, composite GitHub Action,
  pre-commit hook. Targets a single spec version (TODS v2.1.0).
- Explicitly out of scope today: validating GTFS itself, GTFS-realtime
  correlation, feed editing/repair beyond `merge`, multiple spec versions.

---

## 1. Persona roster

Sixteen personas spanning producers, consumers, toolmakers, and governance.
Each row notes the lens they bring.

| # | Persona | Role / context | Technical depth | Primary relationship to the tool |
|---|---------|----------------|-----------------|----------------------------------|
| P1 | **Dana, the scheduler** | Runs-and-blocks scheduler at a mid-size bus agency; lives in HASTUS/Trapeze | Low (spreadsheets, not code) | Wants plain-language findings she can act on without an engineer |
| P2 | **Marcus, the GTFS data engineer** | Owns the agency's GTFS + TODS export pipeline | High (Python, CI) | Wires the validator into CI; cares about exit codes, JSON, performance |
| P3 | **Priya, the transit-tech vendor dev** | Builds a scheduling product that exports TODS | High | Wants a library API and conformance fixtures to test her exporter |
| P4 | **Sofia, the small-agency generalist** | One-person data shop at a rural transit district; no Python | Low–medium | Needs the Docker/Action path and zero-setup usage |
| P5 | **Raj, the CI/platform engineer** | DevOps for a regional transit data warehouse | High | Cares about reproducibility, pinning, SARIF, machine output, supply chain |
| P6 | **Lena, the MobilityData spec steward** | Helps maintain the TODS spec | High (domain) | Cares about spec-version fidelity, ambiguities, conformance suite |
| P7 | **Tom, the gtfs-validator maintainer** | Maintains the downstream GTFS validator | High | Cares about clean handoff, the merge contract, non-overlap of concerns |
| P8 | **Aisha, the open-data analyst / journalist** | Audits agency open data for a watchdog | Medium | Wants to point-and-check public feeds and read a human report |
| P9 | **Carlos, the consultant** | Implements TODS for many agencies | High | Runs the tool across many feeds; wants batch, comparison, config sharing |
| P10 | **Yuki, the QA / test engineer** | QA on the agency data team | High | Wants determinism, golden files, diff-friendly output, regression safety |
| P11 | **Ben, the procurement / compliance lead** | Writes RFP language and acceptance criteria | Low | Wants a "pass/fail" gate and a citable compliance report |
| P12 | **Nadia, the academic researcher** | Studies crew scheduling and labor data | Medium | Consumes TODS at scale; wants stats, not just pass/fail |
| P13 | **Omar, the accessibility & equity reviewer** | Checks that operational data supports paratransit/equity analysis | Medium | Wants semantic completeness checks, not just syntax |
| P14 | **Greta, the multimodal/rail planner** | Works rail + bus; pushing for roster/electrification files | Medium–high | Wants the validator to track upcoming spec files (chargers, energy, runtimes) |
| P15 | **Iris, the i18n / localization lead** | Agency operates in a non-English, multi-byte-encoding region | Medium | Cares about encoding, locale, translated messages |
| P16 | **Sam, the security / OSS-supply-chain reviewer** | Vets OSS the org adopts | High | Cares about SBOM, signing, zip-bomb/path-traversal safety, license |

---

## 2. Synthetic interviews

Each interview is a short Q&A on (a) current use and (b) future wants. Items
referenced as `R-nn` (remediation) and `X-nn` (expansion) are defined in
sections 4 and 5.

### P1 — Dana, the scheduler

**How would you use it today?** "Someone set up the GitHub Action so I get
red Xs on my pull request. The messages are honestly the best part — `E203`
told me `9:45` should be `09:45:00` and even gave the after-midnight example.
That I can fix myself."

**What's missing?** "When I have forty `E307` errors because the GTFS export
ran a day behind, the list is a wall. I want them grouped, and I want it to
say 'these 40 trips are all missing — probably a stale GTFS export' instead of
40 identical-looking lines." → `R-01` (grouping/dedup), `R-02` (root-cause
hints). "Also a one-line summary at the top: 'You're 2 fixes away from green.'"
→ `R-03`. "Could it tell me *which row in my source spreadsheet*? I don't
think in `run_events.txt` row numbers." → `X-01` (source mapping, aspirational).

### P2 — Marcus, the GTFS data engineer

**Today?** "It's in CI behind `--fail-on error`. JSON output feeds our
dashboard; the published `report.schema.json` means I'm not scraping text.
Exit codes are clean (0/1/2)."

**Wants?** "Performance numbers on big feeds — our run_events is ~2M rows and I
don't know if this is O(n) or O(n²)." → `X-02` (benchmarks; already roadmapped
for v0.4). "A `--quiet`/`--max-findings` so logs don't explode." → `R-04`.
"Stable machine identifiers for *locations* — line/column or a JSON pointer —
so I can deep-link." → `R-05`. "Let me point `--gtfs` at a URL, not just a
local path." → `X-03`. "A `--baseline` file so newly-introduced findings fail
CI but the pre-existing backlog doesn't." → `X-04`.

### P3 — Priya, the transit-tech vendor dev

**Today?** "I shell out to the CLI in my test suite and parse JSON. It works
but it's clunky from inside Python."

**Wants?** "A documented, importable Python API — `validate(package, gtfs) ->
Findings` — so I can unit-test my exporter without subprocesses." → `X-05`.
"The fixture feeds in `tests/fixtures` are gold. Publish them as a versioned
conformance corpus I can run my exporter against." → `X-06` (roadmapped v0.5).
"A way to assert 'this feed should produce exactly these rule IDs' for my own
regression tests." → `X-07`.

### P4 — Sofia, the small-agency generalist

**Today?** "No Python here. The Docker one-liner in the README is how I run it.
It works but I had to learn `-v "$PWD/feed:/feed:ro"` the hard way."

**Wants?** "A hosted/web drop-zone where I upload a zip and get the report —
no install." → `X-08` (web UI; big). "Better first-run errors: when I pointed
at the wrong folder it said the package couldn't be read; tell me *what it
looked for*." → `R-06`. "A 'getting started for non-developers' doc." → `R-07`.

### P5 — Raj, the CI/platform engineer

**Today?** "Action pinned by SHA. The GitHub annotation format is nice inline."

**Wants?** "**SARIF output** so findings land in GitHub code-scanning and our
security dashboard, with history and dismissal tracking." → `X-09`. "Pin the
Docker image by digest and publish provenance/SBOM." → `X-10`, `R-08`.
"Reproducible runs: a `--seed`-free guarantee that output ordering is
deterministic across platforms." → `R-09`. "Let the Action expose outputs
(`error-count`, `report-path`) for downstream steps." → `R-10`.

### P6 — Lena, the MobilityData spec steward

**Today?** "`docs/spec-questions.md` is genuinely useful — those eight
ambiguities are real and we should fold several into errata. The Run-as-
Directed example bug (`event_sequence` 30 twice) is a known one."

**Wants?** "A `--spec-version` flag so a feed can be checked against v1 *or*
v2; agencies still ship v1." → `X-11` (roadmapped v0.5). "Make explicit, per
rule, which spec sentence it enforces and which interpretation it took where
the spec is ambiguous — you already cite sections; add the
'permissive/strict' stance as metadata." → `R-11`. "Contribute the fixtures
upstream as the conformance suite." → `X-06`. "A machine-readable map from
rule ID → spec anchor, so the spec site can link back." → `R-12`.

### P7 — Tom, the gtfs-validator maintainer

**Today?** "The `merge` subcommand is the right boundary — you build the
TODS-Supplemented GTFS and hand it to us. The README is clear that you don't
re-validate GTFS. Good."

**Wants?** "Guarantee the merged zip is byte-stable and gtfs-validator-clean
on your own fixtures, in *your* CI, so the handoff doesn't rot." → `X-12`.
"Emit a machine-readable merge manifest (what changed, per file) so we can
correlate." → `R-13`. "Agree on a shared notion of 'entity added by
supplement' so our messages don't double-count." → `X-13` (coordination).

### P8 — Aisha, the open-data analyst / journalist

**Today?** "I run the Docker image against agencies' published feeds and read
the Markdown report. The plain-language findings are quotable."

**Wants?** "A `--summary`-only mode and a shareable HTML report with the
agency name, date, counts, and a severity chart." → `X-14`. "A 'feed health
score' so I can compare agencies." → `X-15` (use with care — easy to
misread). "Batch a directory of feeds and get one comparison table." → `X-16`.

### P9 — Carlos, the consultant

**Today?** "I run it across ~30 agencies. The `tods-validate.toml` per-repo
policy is exactly right — each agency encodes its accepted warnings."

**Wants?** "A shareable *base* config I can `extends = "..."` from, so my house
policy is one file." → `X-17`. "Batch mode + a CSV/JSON roll-up across feeds."
→ `X-16`. "A `--diff` between two runs of the same feed so I can show a client
'you fixed 12, introduced 2.'" → `X-18`. "Profiles: `--profile strict` vs
`--profile lenient` presets." → `X-19`.

### P10 — Yuki, the QA / test engineer

**Today?** "Output is deterministic enough to golden-file. `rules --format
json` lets me assert the catalog didn't change unexpectedly."

**Wants?** "An explicit ordering contract for findings (by file, row, rule)
documented and tested, so golden files are stable across versions." → `R-09`,
`R-14`. "A `--no-color`/`NO_COLOR` honor for clean captures." → `R-15`.
"Snapshot the JSON schema version in the report payload." → `R-16`.

### P11 — Ben, the procurement / compliance lead

**Today?** "I put 'must pass tods-validate with zero errors' in our RFP. The
exit code is the gate."

**Wants?** "A signed/citable compliance report (PDF or stamped Markdown) with
tool version, spec version, timestamp, and feed hash for the contract file." →
`X-20`. "A documented, stable definition of what 'pass' means that I can
reference in legal language." → `R-17`. "Clarity that warnings ≠ failure
unless configured." → `R-07` (docs).

### P12 — Nadia, the academic researcher

**Today?** "I consume many TODS feeds. I mostly use it to filter out broken
feeds before analysis."

**Wants?** "Descriptive *stats*, not just validity: counts of runs, events,
deadhead vs revenue minutes, employees, distinct blocks — a `stats`
subcommand." → `X-21`. "Anonymization helper for `employee_*` data so I can
share derived datasets." → `X-22` (privacy-sensitive). "Stable JSON for
programmatic ingest at scale." → already served; reinforce `X-05`.

### P13 — Omar, the accessibility & equity reviewer

**Today?** "I check that the operational layer supports the analyses we need —
e.g., that deadheads and run structures are present enough to study operator
workload and service equity."

**Wants?** "Completeness/coverage *info* checks: 'X% of GTFS trips have no
run_event referencing them' or 'blocks with no vehicle assignment.'" → `X-23`
(coverage as INFO, not error). "Flag suspicious labor semantics, e.g. runs
with no break across a long span — as INFO/advisory." → `X-24` (advisory,
opt-in).

### P14 — Greta, the multimodal / rail planner

**Today?** "We're adopting TODS for rail. The validator covers the core ten
files well."

**Wants?** "Track the spec's open proposals — rosters, runtimes, and
electrification files (chargers, energy consumption). When they land, I want
validation day one." → `X-25` (roadmapped v0.5). "An experimental/opt-in mode
for not-yet-ratified files so we can pilot." → `X-26`.

### P15 — Iris, the i18n / localization lead

**Today?** "Our IDs and stop names are multi-byte. The UTF-8 requirement is
fine, but `E103` just says 'not UTF-8' when an exporter emits Latin-1."

**Wants?** "Detect and name the likely encoding in `E103`, and offer
`--encoding` as an escape hatch." → `R-18`. "Translatable finding messages
(message catalog / `--lang`)." → `X-27`. "BOM handling spelled out." → `R-19`.

### P16 — Sam, the security / OSS-supply-chain reviewer

**Today?** "Apache-2.0, clean deps (just `click`). Low risk on paper."

**Wants?** "Confirm zip handling is hardened against zip-bombs and path
traversal (the tool ingests untrusted `.zip` feeds)." → `R-20` (security).
"Publish an SBOM and sign releases + the Docker image (Sigstore/cosign)." →
`X-10`. "Document a security policy / `SECURITY.md` and a resource-limit
story for huge inputs." → `R-21`. "Pin the Action's runtime and avoid
network calls during validation." → `R-08`.

---

## 3. Cross-cutting themes

Patterns that surfaced across multiple personas (strongest signal first):

1. **Output ergonomics at scale.** P1, P2, P8, P9 all hit "wall of findings."
   Grouping, summaries, root-cause hints, `--max-findings`, and diff/baseline
   modes recur. (`R-01..R-04`, `X-04`, `X-18`.)
2. **Machine-consumability & CI fit.** P2, P5, P10 want SARIF, stable
   location identifiers, deterministic ordering, Action outputs, schema
   versioning. (`R-05`, `R-09`, `R-10`, `R-16`, `X-09`.)
3. **A real library API.** P3, P12, and indirectly P9 want to call the
   validator in-process rather than shelling out. (`X-05`.)
4. **Spec-version fidelity & conformance.** P6, P3, P14 want `--spec-version`,
   a published conformance corpus, and upstream contribution. (`X-06`,
   `X-11`, `X-25`.) Already on the v0.5 roadmap.
5. **Zero-setup access for non-developers.** P4, P8, P11 want Docker polish, a
   web drop-zone, and citable reports. (`X-08`, `X-14`, `X-20`.)
6. **Beyond pass/fail: stats & coverage.** P12, P13, P10 want descriptive
   statistics and coverage INFO checks. (`X-21`, `X-23`.)
7. **Supply-chain & input-safety hygiene.** P5, P16 want SBOM/signing,
   zip-bomb/path-traversal hardening, SECURITY.md. (`R-08`, `R-20`, `R-21`,
   `X-10`.)
8. **Localization & encoding robustness.** P15 (and any non-US agency) wants
   encoding detection and translatable messages. (`R-18`, `X-27`.)

---

## 4. Remediations — fixes and gaps *inside* current scope

These improve what the tool already does (validation, reporting, distribution)
without expanding its mission. Roughly ordered by value-to-effort.

| ID | Remediation | Drivers | Effort | Notes |
|----|-------------|---------|--------|-------|
| R-01 | **Group/deduplicate findings** by rule and likely common cause in text/markdown output (e.g. "37× E307 in run_events.txt"). | P1,P8,P9 | S | Pure reporting layer; no rule changes. |
| R-02 | **Root-cause hints** for clustered failures (e.g. many E307/E308 → "GTFS may be stale or service IDs renamed"). | P1 | M | Heuristic banner when a rule's count crosses a threshold. |
| R-03 | **Top-line summary** ("N errors, M warnings; X distinct rules; here's the shortest path to green"). | P1,P8 | S | Extend existing `summarize`. |
| R-04 | **`--max-findings N`** (and `--quiet` = summary only) to cap noisy output. | P2 | S | CI log hygiene. |
| R-05 | **Stable machine location identifiers** in JSON: keep file+row, add a JSON-pointer-style `path` and, where known, byte/line offset. | P2,P5 | M | Additive schema field; bump schema version. |
| R-06 | **Better "package could not be read" diagnostics**: list what was searched for and where. | P4 | S | Improve `PackageNotFoundError` message. |
| R-07 | **Docs: non-developer quickstart + a precise "what 'pass' means"** (exit codes, warnings≠failure). | P4,P11 | S | Pure docs. |
| R-08 | **Pin Action runtime & Docker base by digest; assert no network during validate.** | P5,P16 | S | Supply-chain hygiene. |
| R-09 | **Document & test a deterministic finding-ordering contract** (file, then row, then rule ID), stable across platforms. | P5,P10 | S | Lock down for golden files. |
| R-10 | **Expose GitHub Action outputs** (`error-count`, `warning-count`, `report-path`). | P5 | S | `action.yml` change. |
| R-11 | **Per-rule interpretation metadata** ("permissive"/"strict" where the spec is ambiguous), surfaced in `rules --format json`. | P6 | M | Ties `spec-questions.md` to rules programmatically. |
| R-12 | **Machine-readable rule→spec-anchor map** export. | P6 | S | Falls out of existing `spec_section`. |
| R-13 | **Merge manifest**: write a `merge-report.json` alongside the merged feed. | P7 | S | `merge` already computes per-file stats. |
| R-14 | **Document the JSON report ordering & field-stability guarantees.** | P10 | S | Docs + a test. |
| R-15 | **Honor `NO_COLOR` / `--no-color`.** | P10 | S | Capture-friendly output. |
| R-16 | **Embed report-schema version in the JSON payload.** | P10 | S | Forward-compat for consumers. |
| R-17 | **Publish a stable, citable definition of "conformant" / pass semantics.** | P11 | S | Docs; supports procurement. |
| R-18 | **Encoding detection in E103** (name the likely encoding) + optional `--encoding`. | P15 | M | Helps non-UTF-8 exporters. |
| R-19 | **Define BOM handling explicitly** (strip UTF-8 BOM; document it). | P15 | S | Common exporter quirk. |
| R-20 | **Harden zip ingestion** against zip-bombs (size/ratio limits) and path traversal (reject `..`/absolute members). | P16 | M | Tool ingests untrusted archives. |
| R-21 | **Add `SECURITY.md` + resource-limit story** (max file size, row caps with clear errors). | P16,P5 | S | Governance + DoS safety. |

### 4a. Spec-ambiguity remediations (from `docs/spec-questions.md`)

The existing spec-questions are themselves a remediation backlog. Each should
be (a) filed upstream as an issue/erratum and (b) reflected as explicit rule
interpretation metadata (`R-11`). Concrete items:

| ID | Item | Source |
|----|------|--------|
| R-22 | File the Run-as-Directed example PK violation (`event_sequence` 30 twice) upstream as an erratum. | spec-Q2 |
| R-23 | File the `start_mid_trip` vs `mid_trip_start` naming inconsistency. | spec-Q4 |
| R-24 | Propose explicit time bounds / GTFS-time semantics for `start_time`/`end_time`. | spec-Q5 |
| R-25 | Propose packaging/distribution conventions (zip vs dir; discovery). | spec-Q1 |
| R-26 | Clarify CSV value-trimming (padded example values → W206). | spec-Q3 |
| R-27 | Clarify `employee_run_dates.txt` "Primary Key: `*`" duplicate semantics. | spec-Q6 |
| R-28 | Clarify how strictly supplement-added rows must satisfy GTFS-required fields. | spec-Q7 |
| R-29 | Confirm per-row reading of `vehicle_assignments.service_id`. | spec-Q8 |

---

## 5. Expansions — new scope

These grow the product's mission. Several are already on the roadmap (noted);
the rest are net-new candidates. Effort is rough order of magnitude.

| ID | Expansion | Drivers | Effort | Roadmap? |
|----|-----------|---------|--------|----------|
| X-01 | **Source-row mapping**: trace a finding back to the producing system's row (vendor-specific; likely a plugin/adapter point). | P1 | XL | No — aspirational |
| X-02 | **Performance benchmarks** on large feeds + complexity guarantees. | P2 | M | Yes (v0.4) |
| X-03 | **Accept URLs** for `--gtfs` and the feed path (fetch + cache). | P2 | M | No |
| X-04 | **`--baseline` file**: fail only on findings new since a baseline. | P2,P9 | M | No |
| X-05 | **Documented, stable Python API** (`validate(...) -> Findings`). | P3,P12 | M | No |
| X-06 | **Published conformance corpus** from `tests/fixtures`, versioned; offer upstream. | P3,P6 | M | Yes (v0.5) |
| X-07 | **Expected-findings assertion mode** for exporter regression tests. | P3 | S | No |
| X-08 | **Hosted web drop-zone** (upload zip → report); no install. | P4,P8 | XL | No |
| X-09 | **SARIF output format** for GitHub code-scanning & security dashboards. | P5 | M | No — high value |
| X-10 | **SBOM + signed releases/images** (Sigstore/cosign), provenance. | P5,P16 | M | No |
| X-11 | **`--spec-version` flag** (validate against v1 or v2). | P6,P14 | L | Yes (v0.5) |
| X-12 | **CI guarantee that merged fixtures pass gtfs-validator** (self-test the handoff). | P7 | M | Partly (CI recipe exists) |
| X-13 | **Coordinate "supplement-added entity" semantics** with gtfs-validator. | P7 | M | No — coordination |
| X-14 | **Shareable HTML report** (agency, date, counts, severity chart). | P8 | M | No |
| X-15 | **Feed "health score"** (use cautiously; document limits). | P8 | S | No — risk of misuse |
| X-16 | **Batch mode**: validate many feeds, emit a roll-up table (CSV/JSON). | P8,P9 | M | No |
| X-17 | **Config inheritance** (`extends`) for shared base policy. | P9 | S | No |
| X-18 | **`--diff` between two runs** of a feed (fixed/new/persisting findings). | P9 | M | Overlaps X-04 |
| X-19 | **Named profiles/presets** (`--profile strict|lenient`). | P9 | S | No |
| X-20 | **Citable compliance report** (stamped Markdown/PDF: tool ver, spec ver, feed hash, timestamp). | P11 | M | No |
| X-21 | **`stats` subcommand**: descriptive feed metrics (runs, events, deadhead vs revenue minutes, employees, blocks). | P12,P8 | M | No |
| X-22 | **Anonymization helper** for `employee_*` data (privacy-preserving exports). | P12 | M | No — privacy-sensitive |
| X-23 | **Coverage INFO checks**: GTFS trips with no run_event; blocks with no vehicle assignment; etc. | P13,P10 | M | No |
| X-24 | **Advisory labor-semantics checks** (opt-in INFO: long spans without break, etc.). | P13 | M | No — opt-in only |
| X-25 | **Validate new spec files** as adopted: rosters, runtimes, electrification (chargers, energy consumption). | P14,P6 | L | Yes (v0.5) |
| X-26 | **Experimental/opt-in mode** for not-yet-ratified files. | P14 | M | No |
| X-27 | **Translatable finding messages** (message catalog, `--lang`). | P15 | L | No |
| X-28 | **GTFS-realtime / AVL correlation** (do runs/blocks match observed operations?). | (latent) | XL | No — currently out of scope |
| X-29 | **Editing/repair beyond merge** (auto-fix suggestions, patches). | (latent) | XL | No — currently out of scope |

> X-28 and X-29 are listed for completeness because they are natural "what's
> next" questions, but both are explicitly **out of scope** in the current
> roadmap. Recommend keeping them out until the core conformance story is
> locked at v1.0; revisit only with strong, repeated real-world demand.

---

## 6. Prioritized synthesis

A pragmatic ordering that respects the existing roadmap (v0.4 distribution
surfaces → v0.5 spec tracking → v1.0 stability) and front-loads high
value-to-effort items.

**Now / quick wins (mostly small, mostly reporting & hygiene):**
R-01, R-03, R-04, R-06, R-07, R-09, R-10, R-13, R-15, R-16, R-17, X-17, X-19.
Plus filing the spec-questions upstream (R-22..R-29) — cheap, high goodwill,
and it de-risks v1.0.

**Next (clear demand, medium effort, strengthens the two biggest themes —
CI/machine fit and library use):**
X-05 (Python API), X-09 (SARIF), R-05 (stable locations), R-11 (interpretation
metadata), X-04/X-18 (baseline/diff), X-02 (benchmarks, already v0.4),
R-20/R-21/X-10 (input safety + supply chain).

**Roadmap-aligned (v0.5 spec tracking):**
X-11 (`--spec-version`), X-06 (conformance corpus), X-25 (new spec files),
X-26 (experimental mode), R-12 (rule→anchor map).

**Bigger bets (validate demand first):**
X-08 (web UI), X-14/X-20 (rich/citable reports), X-21 (stats), X-16 (batch),
X-27 (i18n). Keep X-28/X-29 parked as out-of-scope.

**Guardrails worth stating in the roadmap:**
- Keep validation and GTFS-validation concerns separate (P7's boundary is a
  feature, not a gap).
- Treat "scores" and labor-semantics checks as advisory/opt-in to avoid
  misuse (P8, P13).
- Anything touching `employee_*` data is privacy-sensitive (P12, X-22) — design
  for least exposure.

---

## 7. How to read this artifact

This is a divergence-then-convergence exercise, not a mandate. The honest next
step is to take the top 6–10 items (especially X-05, X-09, R-01, R-05, and the
v0.5 spec-tracking cluster) to **real** TODS producers and consumers — agencies
running the Action, vendors exporting TODS, and the MobilityData spec group —
and confirm the demand before building. The personas here are a map of the
*possible* user space; only real users can tell you which roads are paved.
