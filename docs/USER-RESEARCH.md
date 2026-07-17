# User Research — Synthetic Personas & Simulated Interviews

> [!WARNING]
> **These personas and interviews are synthetic.** They were assembled as a
> structured brainstorming device, *not* conducted with real people. No real
> scheduler, vendor, or standards steward said any of this. The panel exists to
> pressure-test `tods-validate` from every stakeholder angle at once; it is **not**
> evidence of demand and does **not** substitute for real discovery. Treat every
> "quote" as a hypothesis to validate, not a finding.
>
> The honest next step is real conversations with the TODS Working Group, a
> producing agency, and at least one scheduling-software vendor — the first of which
> is tracked as the v1.0 gate in [`docs/roadmap.md`](roadmap.md) ("the rule set
> proving out against multiple production feeds"). **Last assembled: 2026-06-30.**

> **Maintainer update, 2026-07-16:** the no-real-feed assumption in this
> historical synthetic panel is superseded. Multiple real, non-synthetic feed
> exports have been used privately; see
> [`production-feed-validation.md`](production-feed-validation.md). The persona
> text remains unchanged where it records the panel's original hypothesis.

## Why do this at all

`tods-validate` sits between several audiences who never share a vocabulary: a
run-cutter who thinks in pieces of work and reliefs, a vendor export engineer who
thinks in CSV contracts, a MobilityData steward who thinks in spec sections, and a
DevOps engineer who thinks in exit codes. Role-playing the full cast around the
*actual* tool surfaces gaps a single author misses and forces the question "who is
each feature for?" The synthesis at the end is tagged so it does not become a
wishlist:

- **[shipped]** — exists today (README, CHANGELOG, or `docs/`).
- **[roadmap]** — already named in [`docs/roadmap.md`](roadmap.md).
- **[blocked]** — needs an external input (a real feed, upstream governance, a
  vendor exporter).
- **[new]** — genuinely surfaced here.

Every "values today" line below maps to a real, shipped feature. No feature was
invented to make a persona happy, and no fact about TODS, its history, or its
governance was invented — the research basis is cited under Method.

## How to read a persona

Each card compresses a simulated interview to five lines: **Goal · Values today**
(the real features they lean on) **· Gets stuck · Wants next · Adopts (or walks)**.

---

## Method

- **Sampling frame.** Everyone who touches a TODS feed on its way from a scheduling
  system into operations and analysis, grouped by what they do with the validator:
  *Produce & Validate* (the scheduler who authors run events, the data manager who
  publishes the package, and an accessibility lens on the CLI and report), *Steward
  the Standard* (a MobilityData/Cal-ITP steward, an open-source rule contributor,
  and the owner/maintainer), *Integrate* (a scheduling-software vendor's export
  engineer and a CI/DevOps engineer), *Consume* (a transit researcher/app developer
  and a downstream CAD/AVL integration engineer), and *Operate & Oversee* (a state
  DOT / NTD oversight analyst).
- **Protocol.** For each persona: a goal, a walkthrough of the surfaces they would
  actually touch (CLI, GitHub Action, Python API, `merge`, the playground, the
  reports), what worked, where they stalled, and an open "what would make this a
  10/10" prompt. Frictions become **remediations**; wishes become **expansions** in
  [`RESEARCH-ROADMAP.md`](RESEARCH-ROADMAP.md).
- **Effort scale.** S ≈ an afternoon · M ≈ a day or two · L ≈ a week or more.

### Research basis (real sources, accessed 2026-06-30)

The product surfaces come from this repo (README, CHANGELOG, `docs/rules.md`,
`docs/conformance.md`, `docs/api.md`, `docs/getting-started.md`,
`docs/spec-questions.md`, `docs/report.schema.json`, `action.yml`, `web/README.md`).
The domain and stakeholder model are grounded in:

- **TODS standard & governance** — [About TODS](https://tods-transit.org/about/about/);
  [Spec reference](https://tods-transit.org/spec/);
  [Revision history](https://tods-transit.org/spec/revision-history/) (v1.0.0
  approved 2022-05-03; v2.0.0 2024-07-24; v2.1.0 adopted 2025-04-16);
  [Spec development process](https://tods-transit.org/about/spec-development/);
  [TODS spec repository](https://github.com/MobilityData/transit-operational-data-standard)
  (Apache-2.0 code / CC-BY-4.0 docs).
- **History: Cal-ITP ODS → MobilityData TODS** —
  [Cal-ITP ODS announcement](https://www.calitp.org/press/cal-itp-announces-ods);
  [MobilityData assumes management of MDIP, TIDES, and TODS](https://mobilitydata.org/mobilitydata-to-assume-management-of-mdip-tides-and-ods/)
  (board and management transition, January 2024);
  [first vendor-to-vendor ODS CAD/AVL integrations](https://www.tam-america.com/article/cal-itp-launches-first-vendor-to-vendor-ods-integrations-for-cad-avl-software).
- **What scheduling/operations data is, and who makes it** —
  [Transit scheduling & runcutting explained: blocks, runs, rosters](https://transitambassador.org/transit-scheduling-runcutting-explained-blocks-runs-and-rosters/);
  [TCRP Report 30, Transit Scheduling](https://onlinepubs.trb.org/onlinepubs/tcrp/tcrp_rpt_30-b.pdf);
  [Schedule Masters — Blocking and Runcutting](http://themasterscheduler.com/Blocking-and-Runcutting.html);
  [Optibus scheduling](https://optibus.com/product/scheduling/) (HASTUS is GIRO's
  scheduling product; Trapeze, Optibus, GIRO are the named platforms).
- **The validator-UX model: GTFS + gtfs-validator** —
  [MobilityData/gtfs-validator](https://github.com/MobilityData/gtfs-validator);
  [gtfs-validator rules](https://gtfs-validator.mobilitydata.org/rules.html);
  [GTFS static errors & warnings](https://developers.google.com/transit/gtfs/guides/static-errors-warnings)
  (the ERROR / WARNING / INFO severity model `tods-validate` mirrors).
- **Why standardization matters; oversight** —
  [Mobility Data Interoperability Principles / interoperable procurement](https://www.interoperablemobility.org/procurement/);
  [The role of data specifications in an interoperable system (SUMC)](https://learn.sharedusemobilitycenter.org/casestudy/the-role-of-data-specifications-in-creating-an-integrated-transportation-system/);
  [National Transit Database](https://www.transit.dot.gov/ntd);
  [NTD reporting changes for RY2025/2026 (GTFS collection)](https://www.federalregister.gov/documents/2025/07/10/2025-12813/national-transit-database-reporting-changes-and-clarifications-for-report-years-2025-and-2026).

---

## Persona roster

| # | Persona | Group | Primary goal | Top friction |
| --- | --- | --- | --- | --- |
| P1 | **Renata** — bus scheduler / run-cutter, mid-size agency | Produce & Validate | Fix a TODS export so dispatch ingests it cleanly | She is not a programmer; install + rules doc are a wall |
| P2 | **Marcus** — agency data manager publishing TODS over GTFS | Produce & Validate | Publish a clean overlay every pick, gated in CI | No second validator; GTFS drifts under the TODS package |
| P3 | **Yuki** — data analyst, screen-reader + high-contrast terminal | Produce & Validate | Triage findings non-visually | HTML report a11y unverified; color/`--no-color` undocumented |
| P4 | **Priya** — MobilityData / Cal-ITP TODS steward | Steward the Standard | Raise feed quality; resolve spec ambiguity | It is one author's reading, not blessed by the Board |
| P5 | **Diego** — open-source contributor adding a rule | Steward the Standard | Land a new check, get it merged | No "how to add a rule" guide; opaque conformance failures |
| P6 | **Chelsea** — owner / maintainer | Steward the Standard | Boring-reliable, useful upstream, credible work sample | v1.0 gated on real feeds she does not yet have |
| P7 | **Søren** — export engineer at a scheduling vendor (HASTUS/Optibus/Trapeze class) | Integrate | Ship a TODS exporter agencies trust | Spec ambiguities mean exporter and validator can disagree |
| P8 | **Ravi** — CI / DevOps engineer on the feed repo | Integrate | Gate every PR; annotate findings inline | Action version skew; not on the Marketplace |
| P9 | **Lena** — transit researcher / app developer consuming TODS | Consume | Analyze operational data across agencies | Almost no public TODS feeds exist to consume |
| P10 | **Tom** — CAD/AVL integration engineer ingesting TODS | Consume | Import an agency's TODS reliably | Receives feeds he did not make; needs a go/no-go |
| P11 | **Angela** — state DOT / NTD oversight analyst | Operate & Oversee | Oversee sub-recipients' data at fleet scale | TODS is not an NTD requirement; no conformance level |

---

## Interviews

### Group A — Produce & Validate

#### P1 — Renata, bus scheduler / run-cutter
- **Goal:** her agency's new TODS export keeps getting bounced by the CAD/AVL
  vendor; she wants to find and fix what is wrong before the next pick, in language
  about runs and reliefs, not foreign keys.
- **Values today:** the findings read like a scheduler wrote them — `TODS-E203`
  tells her to write `9:45` as `09:45:00` and explains `25:10:00` means 1:10 AM the
  next service day; `TODS-E401` (event ends before it starts), `TODS-E402` (one
  operator on two trips at once), `TODS-W404` (overlapping runs same day), and
  `TODS-W409` (consecutive events that do not connect in space — "an operator
  cannot teleport") match how she already reasons. `--suggest` offers the
  `09:45:00` rewrite as `review`. The non-developer
  [getting-started](getting-started.md) page and the zero-install Docker path mean
  she does not have to file an IT ticket.
- **Gets stuck:** `pipx install` still assumes a terminal she does not own;
  [`docs/rules.md`](rules.md) is long when she only has two error IDs in front of
  her; she cannot tell which warnings her agency is *allowed* to accept.
- **Wants next:** the browser playground (built in `web/`, runs entirely client-side
  via Pyodide) linked somewhere she can just open; more worked before/after examples
  per rule; the by-rule grouping and root-cause hint she already gets, surfaced
  first.
- **Adopts if** she can run it with no IT help and the messages keep speaking her
  language. **Walks if** a finding ever reads like a database error dump.

#### P2 — Marcus, agency data manager
- **Goal:** publish a TODS package as a clean overlay on the agency GTFS every
  service change, and gate it the same way he gates GTFS.
- **Values today:** `--gtfs` resolves run-event references *after* supplements are
  applied (`TODS-E307`/`E308`/`E309`/`E314`), so a trip added via
  `trips_supplement.txt` is a valid target; `merge` materializes the
  "TODS-Supplemented GTFS" and the README's recipe chains it into MobilityData's
  gtfs-validator; `tods-validate.toml` with `ignore`, `fail-on`, `profile`, and
  `extends` lets him encode a house policy; `diff old/ new/` and `--baseline`
  fail CI only on newly introduced errors; `--stamp` produces a citable Markdown
  artifact; `anonymize` lets him share a problem feed without exposing employee IDs
  or plates.
- **Gets stuck:** there is no independent second validator to cross-check him;
  when the GTFS feed drifts between picks, `TODS-W313` (supplement deletes a row
  that is not there) and `TODS-W302` cluster and he has to guess "stale export";
  coverage rules (`TODS-I501`/`I502`) are judgment calls he is unsure he should
  enable agency-wide.
- **Wants next:** a shared baseline / house policy across the org (the `extends`
  mechanism is the seed); a clearer "your GTFS moved under your TODS" signal; his
  *own* feed in the test corpus so regressions are caught.
- **Adopts if** it slots into his existing GTFS-publishing CI. **Walks if** it
  floods warnings he cannot suppress coherently.

#### P3 — Yuki, data analyst (screen-reader + high-contrast terminal)
- **Goal:** triage a report of findings without relying on color or on seeing the
  terminal.
- **Values today:** severity is spelled out as `ERROR`/`WARNING`/`INFO` in the text
  (no color-only signaling — a stated quality bar for this project), and the report
  stays readable piped to a file; `--quiet` and `--max-findings` keep the output
  bounded; every finding carries a stable machine `location` pointer
  (`run_events.txt#L4/end_time`) she can script against; `--format json` (validated
  by [`report.schema.json`](report.schema.json)), `--format markdown`, and
  `--format sarif` give her structured surfaces instead of scraping prose.
- **Gets stuck:** the standalone `--format html` report's accessibility is
  unverified — table header scope, contrast ratios, and landmarks are not audited;
  ANSI color in the terminal has no documented `--no-color` / `NO_COLOR` escape;
  `--watch` reprinting the whole report is noisy under a screen reader.
- **Wants next:** an audited-accessible HTML report (semantic table headers,
  sufficient contrast, document landmarks); a documented monochrome mode; a short
  accessibility statement for the output surfaces.
- **Adopts if** every output surface works in her screen reader. **Walks if** the
  HTML report is a div-soup or leans on color to convey severity.

### Group B — Steward the Standard

#### P4 — Priya, MobilityData / Cal-ITP TODS steward
- **Goal:** raise the quality of feeds in the wild and turn spec ambiguities into
  decisions, now that MobilityData manages TODS under the TODS Board.
- **Values today:** [`docs/spec-questions.md`](spec-questions.md) catalogs eight
  real ambiguities in v2.1.0 (the undefined `Time` type, padded example values, the
  `employee_run_dates` `Primary Key: *`, the per-row vs global reading of
  `vehicle_assignments.service_id`) with the permissive interpretation and the rule
  ID that implements it, so each decision is traceable; every rule cites an exact
  spec section; the validator is, in effect, a candid reference reading of v2.1.0;
  the downloadable conformance corpus with `expectations.json` is explicitly offered
  upstream; the license is Apache-2.0, matching the spec repo. One spec question is
  already filed upstream as
  [issue #148](https://github.com/MobilityData/transit-operational-data-standard/issues).
- **Gets stuck:** it is one contributor's reading, not blessed by the Working Group;
  the corpus is not yet adopted as the official conformance suite; there is no
  governance tie that would make the tool *the* reference; the open spec proposals
  (rosters #45, runtimes #42/#43, chargers #46) are not yet covered, so the tool
  could fall behind the standard.
- **Wants next:** the remaining spec-questions filed as issues or PRs; the corpus
  adopted as the shared TODS conformance suite; tracking of the next adopted files.
- **Adopts if** the Working Group can lean on it as the reference checker.
  **Walks if** it quietly forks an interpretation the Board would not endorse.

#### P5 — Diego, open-source contributor adding a rule
- **Goal:** add one check he cares about (a refinement of the deadhead-continuity
  logic) and get it merged in a sitting.
- **Values today:** rules are data plus small functions with stable IDs, not a
  plugin framework, so the shape is easy to read; `scripts/generate_rules_doc.py`
  plus a CI drift check keep [`docs/rules.md`](rules.md) honest; the conformance
  contract (one fixture per rule, asserted in `tests/test_conformance.py`, exported
  via `expectations.json`) tells him exactly what "done" means; pytest, ruff, and
  mypy are standard; rule IDs are promised never to be renumbered or reused.
- **Gets stuck:** there is no CONTRIBUTING guide for *how to add a rule* — how to
  choose severity, how to write a message a scheduler can act on, which spec section
  to cite, how to allocate the next ID, and how to add the fixture so conformance
  passes; a red CI run does not obviously say "your rule has no fixture."
- **Wants next:** a documented rule-authoring path and a few "good first issue"
  rules to start from.
- **Adopts if** his first rule PR is mergeable in a day. **Walks if** CI stays
  opaque about why his rule failed the conformance contract.

#### P6 — Chelsea, owner / maintainer
- **Goal:** keep the project boring and reliable, genuinely useful to the TODS
  community, and a credible work sample, while steering toward v1.0.
- **Values today:** the CI matrix (3.11–3.13), ruff and mypy strict, the conformance
  test, the generated rule catalog, `scripts/benchmark.py`, `SECURITY.md` with
  zip-bomb and path-traversal hardening, Dependabot/renovate, and the semantic-
  versioning promise on rule IDs, exit codes, and the JSON schema all exist; the
  playground and the contribution play (offer the corpus and spec-questions
  upstream) are in place.
- **Gets stuck:** v1.0 is gated on the rule set proving out against multiple
  production feeds, and she does not have those feeds; real adoption depends on
  vendors actually exporting TODS; she risks rule-ID churn before v1; she has to
  keep v1 and v2 readings straight as the spec evolves.
- **Wants next:** real feeds (privately is fine); upstream adoption of the corpus
  and the spec-questions; `--spec-version` maturity; a defensible v1.0 cut.
- **Frames her own risk** rather than adopting or walking: the project is only as
  real as the feeds it has seen.

### Group C — Integrate (vendors / CI)

#### P7 — Søren, export engineer at a scheduling-software vendor
- **Goal:** ship a TODS exporter from a HASTUS/Optibus/Trapeze-class scheduling
  product that agencies will accept, and regression-test it on every build.
- **Values today:** the public Python API (`validate_feed`, `suggest_fixes`,
  `ValidationResult`, `Finding`) drops straight into his test suite; the
  conformance corpus plus `expectations.json` lets him assert against rule IDs
  without cloning this repo; the bundled `examples/sample-feed` is a known-good
  target; the ERROR-vs-WARNING split tells him which findings are spec violations
  versus judgment calls; the `merge` → gtfs-validator round-trip proves the
  TODS-Supplemented GTFS his export implies is valid GTFS; `report.schema.json` and
  the rule-ID stability promise give him a contract he can build against.
- **Gets stuck:** the documented spec ambiguities mean his exporter and this
  validator can legitimately disagree (the `Time` type, padded values, the
  `Primary Key: *` question), and there is no authority to break the tie; there is
  no official conformance suite he can certify against; he wants a CI-pluggable
  "exporter conformance" check rather than wiring the API by hand.
- **Wants next:** an upstream-blessed conformance suite; a reusable exporter-test
  Action or pytest helper; the spec-questions resolved so behavior is deterministic.
- **Adopts if** passing the corpus credibly means "agencies will accept my export."
  **Walks if** the validator's reading of ambiguous spec text differs from his with
  no shared authority.

#### P8 — Ravi, CI / DevOps engineer
- **Goal:** gate the feed repository so every pull request is validated and
  findings show up inline.
- **Values today:** the composite GitHub Action is about six lines, emits
  `--format github` annotations, exposes `error-count`/`warning-count`/`info-count`
  outputs and an `enable` input, and pins `actions/setup-python` by SHA; the GHCR
  Docker image covers CI without Python; there is a pre-commit hook; `--format
  sarif` feeds code-scanning; `--baseline` fails only on new findings; exit codes
  0/1/2 are unambiguous; `--max-findings`/`--quiet` keep PR logs sane.
- **Gets stuck:** the README and `merge` recipe pin the Action at `@v0.4.0` while
  the project is already at v0.6.0 — version skew he has to reconcile; it is not on
  the GitHub Marketplace, so discovery and version-pinning are manual; large feeds
  have no caching story in CI.
- **Wants next:** the Action version references kept current; a Marketplace listing;
  `batch` usable in CI; a status badge.
- **Adopts if** it behaves like any other lint gate. **Walks if** it is slow or
  noisy on PRs.

### Group D — Consume

#### P9 — Lena, transit researcher / app developer
- **Goal:** study operational data across agencies and build tooling on top of it.
- **Values today:** `merge` hands her a standard GTFS dataset she can feed to the
  GTFS tools she already has; `stats --format json` reports run events, distinct
  runs, revenue vs non-revenue minutes, employees, vehicles, and GTFS coverage as
  facts (explicitly not a quality score); the `validate_feed` API with a stable
  `ValidationResult`/`Finding` shape and the JSON report schema make it scriptable;
  the opt-in coverage rules (`TODS-I501`/`I502`) gauge how complete a feed is;
  `batch` rolls up many feeds at once.
- **Gets stuck:** TODS is typically a non-public operational layer, so there are
  almost no feeds for her to consume in the open; `stats` are descriptive, not
  comparative across agencies; the spec itself never defines packaging or discovery
  (logged as spec-questions #1), so there is no convention for *finding* feeds.
- **Wants next:** more feeds; comparative/aggregate stats; an upstream packaging and
  discovery convention.
- **Adopts if** it lowers the cost of working with operational data. **Walks if**
  there is simply no data to consume.

#### P10 — Tom, CAD/AVL integration engineer
- **Goal:** ingest an agency's TODS package into a dispatch / CAD-AVL system without
  it breaking his importer.
- **Values today:** the reference rules guarantee that run events resolve to real
  trips, services, stops, and blocks after supplements (`TODS-E307`–`E312`),
  including `E310` where a run event's `block_id` must agree with the trip's block;
  the operational-consistency warnings `TODS-W315`/`W316` (a run event that works a
  trip end to end should start and end at the trip's first and last stop, at its
  scheduled times) catch problems no GTFS-only validator can see; `merge` gives him
  one validated feed to import; `anonymize` lets the agency share a failing feed
  safely.
- **Gets stuck:** he receives feeds he did not author, so when the agency's GTFS
  drifted he sees `TODS-W313` and has to interpret it; he wants a single go/no-go
  "is this safe to ingest" rather than reading severities.
- **Wants next:** a strict "ingest-ready" consumer profile; clearer detection of
  TODS-against-GTFS version drift.
- **Adopts if** a green run means safe to ingest. **Walks if** a passing feed still
  breaks his importer.

### Group E — Operate & Oversee

#### P11 — Angela, state DOT / NTD oversight analyst
- **Goal:** oversee operational-data quality across many sub-recipient agencies and
  tie it into existing federal data programs.
- **Values today:** `batch a/ b/ c/` validates many feeds and prints a roll-up
  table (`--format json` for tooling); `--stamp` turns a Markdown report into a
  citable compliance artifact; `--format html` and `markdown` are shareable;
  `stats` gives fleet-level metrics; stable rule IDs let her write policy against
  specific checks; a statewide house policy can be distributed via config `extends`
  and `profile`; `anonymize` keeps shared feeds clean.
- **Gets stuck:** TODS is not an NTD reporting requirement — NTD newly collects
  *GTFS* for the National Transit Map, not TODS — so she has no regulatory hook to
  mandate it; there is no fleet dashboard; there is no defined conformance "level"
  she could require in a grant agreement; coverage checks are advisory by design.
- **Wants next:** a fleet/portfolio roll-up artifact; a conformance-level
  definition she could cite; messaging that aligns TODS with NTD's GTFS collection.
- **Adopts if** it produces a defensible statewide compliance artifact. **Walks if**
  there is no policy hook to require it.

---

## Cross-cutting themes (what the cast agrees on)

1. **At assembly time, no real production feed was treated as the recurring blocker.** P2, P4, P6, P7, P9, and P11
   all hit the same wall from different sides: the validator's rules, the corpus,
   adoption, and v1.0 are all gated on feeds nobody has yet shared. This re-confirms
   the existing roadmap — proving against production feeds is *the* keystone, and
   most other wants are downstream of it. The 2026-07-16 maintainer update above
   supersedes that access assumption; regression capture is now the remaining work.
2. **Spec ambiguity is shared pain, and resolving it upstream is the highest-leverage
   contribution.** P4, P6, and P7 independently care that the eight items in
   `spec-questions.md` get decided, because the validator, the exporters, and the
   standard all converge only when they do. One is already filed
   ([issue #148](https://github.com/MobilityData/transit-operational-data-standard/issues));
   the rest are cheap to file and turn a tool into a contribution.
3. **Scheduler-language findings are the moat.** P1 and P10 value the same thing the
   canonical gtfs-validator does for rider-facing GTFS, but for *operations*: a
   message that names the file, row, and field and says what good looks like. This
   is the differentiator versus a generic schema checker; protect it as features are
   added.
4. **The conformance corpus wants to become shared infrastructure.** P4, P5, and P7
   each treat `expectations.json` as the thing that would let agencies, contributors,
   and vendors agree on what "passing" means. Upstream adoption converts the corpus
   from a test fixture into a standard.
5. **Each audience wants its own surface over one validation run.** A linkable
   playground (P1), inline CI annotations (P8), an exporter pytest helper (P7), a
   fleet roll-up (P11), an audited-accessible HTML report (P3). The engine is solid;
   several of the *views* are thin or unverified.
6. **Accessibility is asserted but not yet proven.** The project states a no-color,
   pipe-readable quality bar, and the text honors it, but P3 shows the HTML report
   and the color/monochrome behavior are unaudited. Making the claim true is cheap
   and on-brand for a tool whose whole pitch is clear, actionable output.

## Honest limits of this exercise

This is simulated. It can generate plausible needs and obvious gaps, but it cannot
tell you *which* are real, how many agencies or vendors would actually use this, or
whether TODS adoption will grow enough to matter. It over-represents the author's
mental model of the TODS ecosystem and will miss what only a real run-cutter or a
real vendor export team would surprise you with. **Do not prioritize a roadmap off
this alone.** Use it to design the questions for, and lower the cost of, real
conversations with the TODS Working Group, a producing agency, and a scheduling
vendor — the same audiences the project already aims to reach.

The triage, sequencing, and traceability that follow from this panel live in
[`RESEARCH-ROADMAP.md`](RESEARCH-ROADMAP.md), which complements the shipped plan in
[`docs/roadmap.md`](roadmap.md).
