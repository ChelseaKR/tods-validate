# Research-Backed Roadmap

_Assembled 2026-06-30 from the synthetic persona panel in
[`USER-RESEARCH.md`](USER-RESEARCH.md), triaged against the actual product and the
shipped plan._

## Framing — how this relates to `docs/roadmap.md`

[`docs/roadmap.md`](roadmap.md) is the product roadmap: it states intentions
(v0.5.0 spec tracking, v1.0.0 stability commitments) and an out-of-scope boundary
(no GTFS validation, no GTFS-realtime correlation, no editing beyond `merge`). This
document does **not** replace it. It is a *research-backed* layer: it takes the
frictions and wishes the persona panel surfaced, maps each to a real shipped
feature or an existing roadmap line, and sequences the work by leverage. Every item
is tagged:

- **[corroborates …]** — independently re-derived something already in
  `docs/roadmap.md`, the CHANGELOG, or a `docs/` file. Triangulation is a signal,
  not a new commitment.
- **[NET-NEW]** — surfaced only from the panel and not yet written down anywhere in
  the repo.

Nothing here crosses the project's out-of-scope line. Items that would (a fleet
*dashboard*, GTFS validation, feed editing) are either deferred, framed as artifacts
rather than apps, or noted as out of scope.

## Research basis / evidence (real sources, accessed 2026-06-30)

The persona needs are grounded in the same sources cited in
[`USER-RESEARCH.md`](USER-RESEARCH.md#research-basis-real-sources-accessed-2026-06-30).
The evidence that most directly shapes the priorities below:

- **The standard is young and still moving.** v1.0.0 was approved 2022-05-03, v2.0.0
  on 2024-07-24, and **v2.1.0 only on 2025-04-16**
  ([revision history](https://tods-transit.org/spec/revision-history/)); management
  moved from Cal-ITP to **MobilityData under the TODS Board in January 2024**
  ([MobilityData announcement](https://mobilitydata.org/mobilitydata-to-assume-management-of-mdip-tides-and-ods/)).
  A reference validator is most valuable precisely while the spec is settling.
- **There are live, named open proposals.** rosters (#45), runtimes (#42) and a
  `runtime_build_point` field (#43), and chargers (#46) are open in the
  [TODS spec repo](https://github.com/MobilityData/transit-operational-data-standard/issues),
  matching the v0.5.0 roadmap line about "rosters, runtimes, and electrification
  files." One of the project's own spec questions is already filed upstream as
  **issue #148** (the undefined `Time` type).
- **A canonical validator anchors a standard's ecosystem.** MobilityData's
  [gtfs-validator](https://github.com/MobilityData/gtfs-validator) is used by Google
  Maps, Transit, and Moovit and defines the
  [ERROR/WARNING/INFO model](https://gtfs-validator.mobilitydata.org/rules.html)
  `tods-validate` mirrors; TODS has no equivalent yet. That is the opportunity and
  the bar.
- **Interoperability is the whole point of TODS.** ODS/TODS exists to let agencies
  move scheduled operations between scheduling and CAD/AVL systems and escape vendor
  lock-in
  ([Cal-ITP ODS announcement](https://www.calitp.org/press/cal-itp-announces-ods);
  [first vendor-to-vendor CAD/AVL integrations](https://www.tam-america.com/article/cal-itp-launches-first-vendor-to-vendor-ods-integrations-for-cad-avl-software);
  [MDIP interoperable procurement](https://www.interoperablemobility.org/procurement/)).
  That makes the vendor-exporter and CAD/AVL-consumer personas (P7, P10) the real
  adoption path.
- **Operational data is not yet a federal reporting requirement.** NTD newly collects
  *GTFS* for the National Transit Map, not TODS
  ([NTD RY2025/2026 changes](https://www.federalregister.gov/documents/2025/07/10/2025-12813/national-transit-database-reporting-changes-and-clarifications-for-report-years-2025-and-2026)),
  which is why the oversight persona (P11) has no regulatory hook and oversight
  features stay artifact-shaped, not mandate-shaped.

Priority: **P0** now · **P1** next · **P2** soon · **P3** opportunistic.
Effort: **S** ≈ an afternoon · **M** ≈ a day or two · **L** ≈ a week or more.

## Remediation backlog (close gaps in what already exists)

| ID | Remediation | Personas | Pri | Effort | Evidence / notes |
| --- | --- | --- | --- | --- | --- |
| R1 | **Recruit and validate real production TODS feeds** (privately is fine) and fold them into regression tests | P2,P4,P6,P7,P9,P11 | P0 | L | The single recurring blocker. **[corroborates roadmap v0.2.0 "still open: real-world feeds" and the v1.0 gate]** |
| R2 | **Accessibility pass on the HTML report + terminal**: semantic table headers/scope, contrast, landmarks; documented `--no-color` / `NO_COLOR`; a short a11y statement | P3 | P1 | M | `--format html` and ANSI color ship; a11y is a stated quality bar but unaudited. **[corroborates the no-color/pipe-readable quality bar · NET-NEW as explicit work]** ✅ Implemented 2026-06-30 (working tree, uncommitted) — HTML report landmarks/caption/scoped headers/viewport/contrast fix + README accessibility statement |
| R3 | **File the remaining `spec-questions.md` items upstream** as issues/PRs and track resolution | P4,P6,P7 | P1 | M | Eight documented; **#148 already filed**. **[corroborates `spec-questions.md` + the contribution play]** |
| R4 | **Contributor rule-authoring guide**: severity choice, scheduler-grade message style, spec citation, ID allocation, fixture + `expectations.json`; seed "good first issue" rules | P5 | P1 | S | Rules-as-data + the conformance contract exist; the *how-to* is undocumented. **[NET-NEW · corroborates `conformance.md`]** ✅ Implemented 2026-06-30 (working tree, uncommitted) — docs/authoring-rules.md, linked from README + conformance.md |
| R5 | **Keep the GitHub Action version current** in README and `merge` recipe (pinned at `@v0.4.0` while project is v0.6.0) and publish to the **Marketplace** | P8 | P1 | S | Version skew is a real friction in the docs today. **[NET-NEW]** ✅ Implemented 2026-06-30 (working tree, uncommitted) — README + merge recipe bumped `@v0.4.0`→`@v0.6.0`; Marketplace publish deferred (needs GitHub UI) |
| R6 | **Deepen "what good looks like"**: worked before/after examples for the highest-frequency rules, in `rules.md` and report hints | P1,P10 | P2 | M | Builds on by-rule grouping, root-cause hints, and path-to-green that already ship. **[corroborates existing report UX · NET-NEW examples]** ✅ Implemented 2026-07-03 (branch `roadmap/r6-worked-before-after-examples-for-high`) — `Rule.example` field on TODS-E104, E106, E307, E308, E309, E314, W206; surfaced in `docs/rules.md` (regenerated) and appended to cluster hints in `report.py` |
| R7 | **Ship and link the browser playground** (built in `web/`, runs via Pyodide, no upload) from the README | P1,P7 | P2 | S | `web/README.md` describes the deploy step; it is not yet linked. **[corroborates `web/` · NET-NEW: finish it]** |
| R8 | **"Your GTFS moved under your TODS" root-cause hint** when `TODS-W302`/`W313` cluster | P2,P10 | P2 | S | Extends the existing root-cause-hint mechanism to a known cluster. **[corroborates report hints · NET-NEW hint]** |
| R9 | **Validate throughput on real large feeds** with `scripts/benchmark.py` and document it | P8,P6 | P3 | S | The benchmark harness already exists; results are published in [`docs/BENCHMARKS.md`](BENCHMARKS.md). **[corroborates `benchmark.py`]** ✅ Implemented 2026-07-02 — `docs/BENCHMARKS.md` documents methodology and results at 1k/10k/50k/100k trips |

## Expansion backlog (new capability)

| ID | Expansion | Personas | Pri | Effort | Evidence / notes |
| --- | --- | --- | --- | --- | --- |
| E1 | **Validate the adopted-next spec additions** behind `--enable experimental`: rosters (#45), runtimes (#42/#43), chargers/electrification (#46) | P4,P6,P7 | P1 | L | Tracks live upstream proposals. **[corroborates roadmap v0.5.0]** |
| E2 | **Publish the conformance corpus upstream as the shared TODS conformance suite**, with a governance hand-off path to the TODS Board | P4,P5,P7 | P1 | M | `expectations.json` is already built to be consumed without cloning. **[corroborates roadmap v0.5.0 + `conformance.md`]** |
| E3 | **Reusable "test your exporter" GitHub Action / pytest helper** wrapping `validate_feed` + the corpus | P7,P8 | P1 | M | The API and corpus exist; the packaged exporter-CI surface does not. **[NET-NEW · builds on `api.md` + corpus]** ✅ Implemented 2026-06-30 (working tree, uncommitted) — `tods_validate.testing` pytest helpers (`assert_feed_valid`, `assert_feed_produces`), documented in api.md + conformance.md |
| E4 | **Multi-version maturity**: `--spec-version` for v1 vs v2 with documented deltas | P4,P7 | P2 | M | Flag exists; the v1 rule set and delta docs do not. **[corroborates roadmap v0.5.0]** |
| E5 | **Fleet/portfolio compliance artifact**: `batch` → one stamped report across agencies (artifact, not a hosted dashboard — stays in scope) | P11 | P2 | M | Extends `batch` + `--stamp`. **[NET-NEW]** ✅ Implemented 2026-07-03 — `batch --format markdown [--stamp]` renders a single fleet compliance report (`render_batch_markdown` in report.py) with a per-feed pass/fail/error summary table, fleet totals, and the same provenance footer as `validate --stamp` |
| E6 | **Strict "ingest-ready" consumer profile** as a named preset for CAD/AVL import gating | P10 | P2 | S | Profiles (`strict`/`lenient`) already exist as a mechanism. **[corroborates profile presets · NET-NEW preset]** |
| E7 | **Conformance-"level" definition** (what "passing" means agency-to-agency) for procurement and oversight | P11,P7 | P3 | M | Aligns with MDIP interoperable-procurement framing. **[NET-NEW]** |
| E8 | **Comparative / aggregate stats** across feeds (beyond per-feed descriptive) | P9,P11 | P3 | M | Extends `stats` + `batch`. **[NET-NEW]** ✅ Implemented 2026-07-03 (working tree, uncommitted) — `stats` accepts multiple PATHs and prints a cross-feed comparison table plus a totals/means/min/max aggregate summary (`tods_validate.stats.collect_cross_stats`, `aggregate_stats`, `render_comparison_text`/`_markdown`, `comparison_to_dict`); documented in README.md |
| E9 | **Propose a packaging/discovery convention upstream** (spec-questions #1) | P9,P4 | P3 | S | The spec defines filenames but no packaging/transport. **[corroborates `spec-questions.md` #1 · NET-NEW upstream]** |

## Sequenced roadmap

- **Now (P0–P1, the keystone and the cheap contribution wins).** R1 (recruit real
  feeds) runs in the background because it gates everything and v1.0. In parallel,
  ship the cheap, high-trust items that need no external input: R3 (file
  spec-questions upstream), R2 (accessibility pass), R4 + R5 (contributor guide +
  Action currency), and begin E2 + E3 (corpus upstream + exporter helper).
- **Next (P1–P2).** E1 (validate rosters/runtimes/chargers behind experimental) as
  those proposals advance upstream; R6 + R7 (worked examples + linked playground);
  E4 (`--spec-version` maturity); E6 (ingest-ready profile for P10).
- **Soon (P2–P3).** E5 (fleet compliance artifact), R8 (drift hint), R9 (done —
  throughput published in `docs/BENCHMARKS.md`), E8 (comparative stats).
- **Opportunistic (P3).** E7 (conformance level), E9 (packaging convention upstream).
- **v1.0 cut** stays gated, per `docs/roadmap.md`, on R1 succeeding (multiple
  production feeds) and no rule-ID churn for two releases.

## Recommended first sprint (highest leverage, mostly already-built infra)

The triage and the shipped roadmap converge on the same starting line. The theme:
**convert the tool into a contribution and make its own claims true**, while the
slow keystone (real feeds) runs in the background.

1. **R1 — start recruiting real feeds now.** It is the longest pole and gates v1.0,
   so begin outreach immediately: the TODS Working Group, a producing agency, and a
   vendor export team (the same audiences the project already targets). Everything
   else is faster.
2. **R3 — file the remaining spec-questions upstream.** Cheap, already started
   (#148), and it is the move that turns a validator into a recognized contribution
   to the standard. Highest reputational leverage per hour.
3. **R2 — accessibility pass on the HTML report + terminal.** An afternoon-to-a-day
   of work that makes a stated quality bar actually true, on a tool whose entire
   pitch is clear, actionable output.
4. **R4 + R5 — contributor guide + Action currency.** Both are small and both unblock
   other people: R4 lets a contributor land a rule in a day; R5 removes a live
   version-skew papercut and lists on the Marketplace.
5. **E2 + E3 — corpus upstream + exporter test helper.** The vendor-adoption lever:
   a blessed conformance suite plus a drop-in exporter-CI check is what makes a
   HASTUS/Optibus/Trapeze-class team trust and use the tool, which is also the path
   to the real feeds R1 needs.

## Traceability matrix (persona → findings)

| Persona | Remediations | Expansions |
| --- | --- | --- |
| P1 Scheduler / run-cutter | R6, R7 | — |
| P2 Agency data manager | R1, R8 | E5 |
| P3 A11y data analyst | R2 | — |
| P4 TODS steward | R1, R3 | E1, E2, E4, E9 |
| P5 OSS rule contributor | R4 | E2 |
| P6 Owner / maintainer | R1, R3, R9 | E1 |
| P7 Vendor export engineer | R1, R3, R7 | E1, E2, E3, E4, E7 |
| P8 CI / DevOps | R5, R9 | E3 |
| P9 Researcher / app dev | R1 | E8, E9 |
| P10 CAD/AVL integrator | R6, R8 | E6 |
| P11 DOT / NTD oversight | R1 | E5, E7, E8 |

## Validate with real users / risks

This roadmap is built on a synthetic panel, so its priorities are hypotheses. The
honest tests:

- **Talk to the TODS Working Group / MobilityData (P4).** The fastest way to learn
  whether the corpus and spec-questions are wanted upstream is to ask the Board and
  watch what happens to issue #148. **Risk:** the working group prefers to own a
  reference implementation directly; mitigation is to offer to transfer or
  co-maintain rather than hold the tool separately.
- **Get one producing agency and one vendor on a feed (P2, P7).** R1 is the whole
  ballgame; everything else is faster than this. **Risk:** TODS is typically a
  non-public operational layer, so feeds are hard to obtain even when they exist;
  mitigation is `anonymize` and accepting feeds privately.
- **Watch whether the spec keeps moving (P4, P7).** v2.1.0 is barely a year old and
  rosters/runtimes/chargers are open proposals. **Risk:** building E1 against
  proposals that change; mitigation is the `experimental` opt-in and not promising
  stability on them.
- **Confirm the oversight hook is real (P11).** TODS is not an NTD requirement.
  **Risk:** the state-DOT persona is the weakest because there is no mandate;
  oversight features stay artifact-shaped (E5) rather than assuming a regulatory
  driver that does not exist.

## Honest limits

The panel is simulated. It surfaces plausible gaps and re-confirms the existing
roadmap from several angles, which is useful, but it cannot tell you which needs are
real, how many agencies or vendors would adopt this, or whether TODS will grow
enough to sustain a third-party validator. It over-weights the author's mental model
of the ecosystem. Treat the sequencing as a starting hypothesis to test against the
real conversations above, not as a committed plan. Where this roadmap and
[`docs/roadmap.md`](roadmap.md) disagree, the shipped roadmap wins until a real user
says otherwise.
