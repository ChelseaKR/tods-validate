# Multiyear plan

_Drafted 2026-08-27, covering roughly 2026 Q3 through 2029._

Where the other planning documents sit one layer down, this one sequences
them. It does not invent a direction. Everything below is drawn from
[`roadmap.md`](roadmap.md), [`v1-contract-audit.md`](v1-contract-audit.md),
[`CONFORMANCE-GAPS.md`](CONFORMANCE-GAPS.md),
[`RESEARCH-ROADMAP.md`](RESEARCH-ROADMAP.md), the
[`ideation/`](ideation/) folder, and the open issues, and each phase says
which of those it is drawing on.

## How to read this

- **`roadmap.md` still wins.** It is the shipped, version-keyed product
  roadmap. This file arranges its remaining items into phases and adds the
  standards and stewardship work that has no version number attached.
- **Dates are intentions.** `roadmap.md` says so already; it applies here
  more, because the later phases are gated on other people.
- **Rejected work stays rejected.** Validating GTFS itself, GTFS-realtime
  correlation, feed editing beyond `merge` (`roadmap.md` "Out of scope"), a
  hosted dashboard, and LLM-generated finding explanations
  (`ideation/03-expansions.md` "Considered and rejected") are decisions with
  reasons attached. No phase below reopens one. The two that could be
  reopened, and what would have to be true first, are named in Phase 6.
- **A phase is not scheduled until it can be worked.** The two largest
  open questions in this project, real production feeds (#76) and a real
  assistive-technology walkthrough (#74), are gated on people rather than
  engineering. They appear in "Standing work that no phase owns" rather than
  inside a phase, because putting a date on them would be pretending.

## The through-line

`ideation/04-impact-and-sequencing.md` closes on the judgement this plan is
built around: the existing roadmaps point outward at feeds, upstream
adoption, and new surfaces, and the highest-leverage unwritten work points
inward, at making the validator's own claims structurally true before real
feeds arrive to test them. Phases 1 to 3 finish pointing inward. Phases 4 to
6 turn outward, and are progressively less under this repository's control.

---

## Phase 1: gates that cannot lie (2026 Q3) [EXECUTED]

**Delivers.** Three checks that read a document produced outside this
repository could report success without having read it. Each now fails
closed and says what it did not read.

- `doctor`'s gtfs-validator stage counted notices out of a `report.json` it
  did not understand. A document that parsed as JSON but was shaped some
  other way yielded zero notices and `status="ran"`, rendering identically to
  a genuinely clean run (#147).
- `scripts/spec_watch.py`, the tripwire for `schema.py` drifting from the
  upstream spec, printed "schema.py is in sync with the upstream spec" and
  exited 0 for any document it could not parse, and for a partial parse where
  the tables it did read happened to match. Every report now names the tables
  it compared; a run that recognises nothing raises, and a partial run exits
  advisory. The weekly workflow opens an issue for a failed comparison, not
  only for drift, because a tripwire that fails silently is the failure it
  exists to catch.
- `scripts/check_npm_audit.py`, the merge-blocking Node advisory gate, has a
  cross-check for reports it cannot parse, guarded by a count that returned
  zero whenever it could not be read. A report that degraded in both halves
  at once disarmed the guard and passed.

**Depends on.** Nothing external. This phase was chosen to go first for that
reason.

**Done when.** Each of the three refuses the shape it used to accept, each
still passes the report it does understand, and every new test has been shown
to fail against the pre-change code rather than merely to pass against the
new code. All three are done.

**Not in this phase.** `doctor`'s `stats` stage failing does not change the
exit code. That is documented behavior (README, `doctor`'s docstring), not an
oversight, and changing it is a contract decision that belongs in Phase 2.
The larger instance of this same defect class, the companion-GTFS reader in
`gtfs_companion.py`, is Phase 2 work: it touches rule semantics and the
coverage manifest, so it is a compatibility decision, not a bug fix.

## Phase 2: freeze the contract, ship v1.0.0 (2026 Q4 to 2027 Q1) [PARTLY EXECUTED]

**Delivers.** The stability commitments `roadmap.md` reserves for v1.0.0:
semantic-versioning guarantees on rule IDs, exit codes, the public Python
exports, and the JSON report schema.

Executed, in the order the compatibility constraint requires:

- **The companion-GTFS fail-open, first, because it is a compatibility
  decision.** A companion GTFS base file that parsed but did not read in full
  (a ragged row, a duplicated column) counted as a clean read: it stayed in
  `CompanionGTFS.present`, every rule reading it recorded `ran`, and nothing
  reported the defect, because `TODS-E103`/`E104`/`E105` scan the TODS package
  and never the companion feed. One short row therefore either left the run
  reporting "No problems found" and exit 0, or reported `TODS-E307` against
  the producer's `run_events.txt` for a trip that does exist. Such a file is
  now unavailable to resolve references against, exactly as an unreadable one
  already was. See [ADR 0007](adr/0007-companion-gtfs-partial-read-is-not-a-read.md).
- **The fail-open in the contract gate itself.** `pythonExports` was compared
  against each module's `__all__`, a declaration of the export list rather
  than the list. A rename that left `__all__` behind passed
  `scripts/check_public_contract.py` and the entire test suite with
  `tods_validate.suggest_fixes` gone. Promoting the audit document without
  this would have frozen the verification defect along with the contract.
- **PEP 735 dependency groups** (CQ-27, #145), with `tests/test_packaging.py`
  as the AUTO-GATE the code-quality standard asks for.
- **The CHANGELOG heading format** (DOC-07/REL-10), with the release gate's
  own grep now run against the file by `tests/test_changelog.py`, so the two
  cannot drift apart without the test suite saying so.
- **The branch ruleset as an artifact**, [`rulesets/main.json`](rulesets/main.json),
  with `tests/test_branch_ruleset.py` keeping its required checks in step with
  the checks the workflows report. Writing the prose down as a file found a
  defect in the prose: it named `zizmor`, which is path-filtered on
  `pull_request` and would therefore have blocked every pull request that
  touched no workflow file.

Not executed, and why:

| Item | Blocked on |
| --- | --- |
| Promoting `v1-contract-audit.md` from candidate to contract | A conformance-only release shipping first. `v0.10.0` disqualified itself, and `Unreleased` changes behavior again, so the earliest qualifying release is two releases away. Only the maintainer can cut one. The preconditions are now written down and dated in that document. |
| The `employee_run_dates.txt` primary key, `TODS-E204` versus `TODS-W408` | Upstream PR #156, open and last updated 2026-07-17. Freezing on it today would freeze this repository's reading of an issue thread as though it were published text. |
| Tagging `v1.0.0` | The maintainer. Signed, annotated tags are not something an automated pass creates. |
| ~~Enabling the branch ruleset (CQ-37 to 43, CICD-03/11-18) and the PyPI environment scoping (CICD-06)~~ | Both done 2026-09-01. `protect-main` requires sixteen checks with no bypass actors, and `docs/rulesets/main.json` is its export; the `publish` job is scoped to a `pypi` environment PyPI now names. |
| Deleting the stray `v0` tag | The maintainer. `docs/CONFORMANCE-GAPS.md` already records that deleting a published ref is out of scope for a file-editing pass, and the two commands to do it. |
| #143 (structure warning for a recognized-but-unexpected file) and #144 (a second advisory rule) | Nothing, except that both need a spec citation chosen and defended, both are labelled `good first issue` deliberately, and the plan already says neither blocks the release. Left open for a contributor rather than absorbed. |

**Depends on.** Upstream PR #156 (people, not engineering), and a
conformance-only release, which only the maintainer can cut. The two settings
prerequisites are no longer among them: both were applied on 2026-09-01, and
what applying them found is recorded in `docs/CONFORMANCE-GAPS.md` — the
committed ruleset had never been compared with the live one, and the review
requirement it asked for could not have been satisfied by a repository with
one code owner.

**Done when.** `v1.0.0` is tagged, annotated and signed; the contract
snapshot went one full release cycle unchanged before the tag; and
`v1-contract-audit.md` no longer says "candidate". The branch-ruleset half of
this line is done: it is enabled live and `docs/rulesets/main.json` is its
export.

## Phase 3: scale readiness and triage quality (2027 Q2 to Q3) [PARTLY EXECUTED]

**Delivers.** The answer to "what happens on a real agency's feed", to the
extent it can be answered without one.

Two of this phase's items turned out to be already built, and saying so is
part of the work: **FIX-03** (derived-state caching) is done, as
`ValidationContext.events` / `.events_by_run` / `.run_pairs` cached properties
that `semantics.py` and `coverage.py` read; **FIX-15** (an HTML report that
survives ten thousand findings) is done and tested at exactly that scale,
grouping, filtering, dark scheme and no-JavaScript fallback included. Neither
needed doing again.

Executed:

- **EXP-13, published.** The generator existed; nothing published its output,
  so every performance number in this repository cited a feed a reader could
  not obtain. `release-corpus.yml` now builds one archive per profile on every
  release, prints their checksums, and attaches them. Publishing them first
  required making them worth publishing: zip entries carried build-time
  mtimes, so two runs of one seed produced identical contents inside archives
  with different checksums, against a docstring promising bit-for-bit
  reproduction.
- **FIX-04, measured and half closed.** Peak memory was an estimate ("roughly
  an order of magnitude") nobody had checked. Measured, it was **36.6x the
  input bytes**, which makes the loader's 512 MiB and 2 GiB limits describe
  packages needing 18 and 72 GiB. A per-file value pool took it to **30.9x**
  at no throughput cost; `scripts/check_memory_budget.py` gates it at 1.03x
  growth, and `SECURITY.md` now states the real ceiling next to the limits it
  contradicts. The per-row `dict[str, str]` that accounts for the rest is
  still open, now with a number and a gate attached.
- **The bundle baseline**, `perf/bundle-baseline.json`, over the playground
  page, the whole published tree, the page count, and a report at ten thousand
  findings, which is the one that can grow silently at 235 bytes a finding.
- **A dated `docs/a11y/STATEMENT.md`** naming WCAG 2.1 AA as the target and
  deliberately making no conformance *claim*, since the only evaluation run is
  automated. Writing its surface table found an unaudited surface: the 44
  rule-catalog pages `pages.yml` publishes had never had a runner pointed at
  them. Entering the gate they failed with 141 contrast errors and 43
  link-distinguishability errors, from one stylesheet that declared
  `color-scheme: light dark` and painted neither scheme. Fixed.
- **CQ-47, re-measured and ratcheted.** The documented ~65% was recorded
  against 280 mutants and the engine has grown to 330; re-run, it was 57.6%.
  Sixteen survivors sat in a helper added the same week, and killing twelve of
  them took the rate to **62.2%**. The weekly workflow also carried
  `continue-on-error: true` on the job plus `|| true` on every step, so a rate
  that halved rendered identically to one that did not move; it now fails
  below the floor in `perf/mutation-baseline.json`.

Not executed, and why:

| Item | Blocked on |
| --- | --- |
| FIX-04's compact row representation (`Row.values` as a view over a tuple) | Nothing external, but it is L-to-XL work touching every rule's data access, and it wants the differential corpus as a safety net. Deferred deliberately rather than started; the budget gate means it can be attempted later against a number. |
| A Lighthouse baseline | A judgement the maintainer should make, not an agent. It means a new npm toolchain on top of the one already carrying an unpatchable high-severity advisory (`extract-zip` via puppeteer via `pa11y-ci`), for a metric that overlaps what axe and HTML_CodeSniffer already gate. The bundle half of that gap is closed; this half is stated rather than quietly ticked. |
| Final calibration of any of these against real data | #76. Every number in `docs/BENCHMARKS.md` says synthetic, because it is. |

**Depends on.** Phase 2's contract freeze, so that performance work cannot
quietly change behavior. That freeze is blocked on a release cycle, so this
phase honoured the constraint instead of the schedule: the one behavioural
change here (the value pool) is byte-for-byte identical in output, and the
whole suite plus the conformance corpus pass unchanged.

**Done when.** A published, seeded benchmark corpus exists; the throughput
and memory ceilings are documented with the machine class they were measured
on; the HTML report is usable at ten thousand findings; and every claim in
this phase says whether it was verified against real data or synthetic.

## Phase 4: surfaces, and room for a second maintainer (2027 Q4 to 2028 Q1) [PARTLY EXECUTED]

**Delivers.** The work that widens who can use and who can maintain this.

The surfaces half turned out to be almost entirely built already, and checking
that was the work rather than a formality. Every Horizon 2 item in
`ideation/03-expansions.md` except EXP-10 and EXP-12 ships today: EXP-07's read
API is in the v1 contract as `tods_validate.read`, EXP-08's rule catalog is
deployed, EXP-09's workspace ledger is the `trend` command, EXP-11's `doctor`
is a subcommand. `tods-validate --help` lists fourteen commands. EXP-12 belongs
to phase 5.

Executed:

- **All four stewardship rows**, each closed as a *checked* contract rather
  than a document, because the portfolio defines AUTO-GATE as merge-blocking
  with no `|| true`:
  - **Incident response.** `.github/labels.yml` declares the `incident`,
    `sev1` to `sev4`, `deploy-caused` convention; `docs/incidents/TEMPLATE.md`
    carries every section IR-07 names; `docs/runbooks/secret-exposure.md` works
    IR-10 to IR-14 in order with a per-credential revocation table.
    `scripts/check_incident_contract.py` gates all of it, plus IR-15 (no
    wildcard `git add` in unattended automation) and IR-16 (no scripted commit
    without a secret scan). Both of those were already clean, so each reports
    what it scanned: a guard with nothing to catch and a guard that is not
    looking otherwise render identically.
  - **Data governance.** Five sources classified under the v2.0.0 tiers with a
    card each, and `scripts/check_data_cards.py` failing in both directions.
    The user-feed card is written to decline ownership rather than assert it.
  - **DORA quarterly review (QM-11).** `docs/DORA-2026-Q3.md` plus a JSON
    snapshot and a collector. Three of five metrics come back breached and one
    N/A, which is the point of measuring.
  - **AI-development measurement.** The `AI-DEV-MEASUREMENT: APPLIES`
    declaration, the diagnostic share measured and stated as never-gating, and
    two BASELINE counterweights each carrying a dated graduation decision of
    2026-11-30.
- **The extension's non-publication recorded as steps rather than an excuse**,
  in `docs/runbooks/publish-vscode-extension.md`. The VSIX builds, type-checks,
  audits, and verifies its own contents in CI today; what is missing is an
  Azure DevOps publisher and an Eclipse Contributor Agreement, both signed by a
  person.

Three past events would have been `incident` issues had the convention existed:
`v0.9.1` tagged but never released, leaving the deployed playground unable to
boot for three weeks (#136); the playground drift oracle comparing against an
immutable tag, so it could never go green (#150); and three gates that could
report a pass they had not earned (#147). None is backfilled into
`docs/incidents/`, because reconstructing a timeline nobody recorded would
invent the one thing a postmortem exists to hold. They are counted in the DORA
review, where the evidence is the changelog and the tag dates rather than a
memory.

Not executed, and why:

| Item | Blocked on |
| --- | --- |
| Publishing the extension to the Marketplace and Open VSX (EXP-10) | Two publisher accounts and a legal acceptance: an Azure DevOps organisation with a Marketplace-scoped PAT, and an Eclipse Foundation account with the Contributor Agreement signed. Neither is something a repository can hold. The runbook is written so this is one session's work. |
| Creating the six incident labels | They are declared in `.github/labels.yml`, not created; `gh label list` shows none exist. Creating them is a repository change, with the command in that file's header. IR-02's live check needs them first. |
| A second maintainer | A person, not a milestone. `.github/CODEOWNERS` has been ready since it landed. The measured consequence is now written down rather than felt: 113 of 118 merged pull requests had zero review. |

**Depends on.** Publisher accounts and human UI steps for the extension.
A second maintainer is a person, not a milestone; the phase delivers the
readiness for one either way.

**Done when.** The extension is installable from a marketplace, or the phase
records why it is not; and each of the four standards rows above is either
closed or has a dated decision saying it will not be.

## Phase 5: upstream standing (2028) [NOT STARTED, GATE VERIFIED 2026-08-27]

**Delivers.** The position `CLAUDE.md`'s "adoption, not ownership" framing
has always pointed at, and which `ideation/03-expansions.md` calls the
endgame.

- The conformance corpus adopted upstream, or a recorded decision that it
  was not (MobilityData issue #153, already filed).
- Verifiable exporter conformance attestations (EXP-12), which only mean
  something once the corpus has upstream standing.
- Rules as a normative annex of the spec (EXP-15): each spec MUST and SHOULD
  paired with a rule ID and an interpretation note, with the eight open
  ambiguities in `docs/spec-questions.md` decided as part of adoption.

**Gate state, re-read 2026-08-27.** MobilityData issue #153, "Would the TODS
Board like to adopt a shared conformance corpus?", is **open with no comments,
last updated 2026-07-12**. Nothing has been declined and nothing has been
adopted; the question has not been answered.

Nothing in this phase has been started, and starting it would be the overclaim
the plan already warns against. Attestations that nobody upstream recognises
are a certificate this project issues to itself, and an annex proposed to a
board that has not answered the smaller question first is a worse version of
asking it. The fallback, a well-maintained third-party catalog, is what exists
today and is already useful; every rule already has a permanent URL, a spec
citation, and a fixture.

What *is* new is that the gate is now watched rather than remembered.
[`docs/phase-gates.json`](phase-gates.json) records the state, and
`scripts/check_phase_gates.py` re-reads it monthly, because "a phase is not
scheduled until it can be worked" is only honest if somebody would notice when
it can be.

**Depends on.** Entirely on the TODS Board and MobilityData. This is the
phase this repository cannot execute alone, and saying otherwise would be the
same kind of overclaim the validator is built to refuse.

**Done when.** At least one spec release cites rule IDs from this catalog,
whatever repository they live in by then; or the Board declines, and that is
recorded so nobody re-litigates it from scratch.

## Phase 6: only on a trigger (2028 H2 to 2029) [NEITHER TRIGGER FIRED, CHECKED 2026-08-27]

Two large bets, neither scheduled, each with a written trigger. A phase with
no trigger met is a phase that does not start.

- **Extract the engine (EXP-14).** The registry, findings, renderers, and
  gating contain almost nothing TODS-specific, so a validator for a second
  MobilityData-family spec would be a schema module rather than a new
  project. **Trigger:** a concrete second spec with a committed user. Not
  speculation, and not before v1.0's stability promise can absorb the split.

  **Not fired.** There is no second spec and no committed user; no issue in
  this repository asks for one. The second half of the trigger is also unmet
  by construction: v1.0 is not released, so there is no stability promise for
  a split to be absorbed by. Two independent reasons, either sufficient.

- **Planned versus actual, TODS against TIDES (EXP-16).** Explicitly parked.
  It crosses the spirit of the current out-of-scope line, and needs a
  documented scope decision, real TIDES data, and real operational partners.
  **Trigger:** real-feed adoption (#76) succeeding first, then an explicit
  decision to renegotiate the scope line.

  **Not fired.** #76 is open, last updated 2026-08-21, with one comment and no
  feed. The trigger is explicitly two-stage and the first stage has not
  happened, so the second is not a question anyone has to answer yet.

Both remain unbuilt, which is the correct state and not a shortfall. A trigger
manufactured to justify starting is worse than a phase that has not started,
because it spends the one thing this repository trades on. `docs/phase-gates.json`
watches #76 for the second; the first has nothing to watch, which is itself the
honest answer.

## Standing work that no phase owns

These run across every phase and are gated on people. They are listed here
rather than scheduled because a date on them would be fiction.

Every row's gate is recorded in [`phase-gates.json`](phase-gates.json) and
re-read monthly by `scripts/check_phase_gates.py`, which opens an issue when a
state moves **or when it could not read one**. The states below were verified
live on **2026-08-27**; all eight gates were still open.

| Work | Gate | What is honest meanwhile |
| --- | --- | --- |
| Real production feeds (#76) | An agency or vendor sharing a feed, privately is fine. Open, updated 2026-08-21 | Synthetic corpora, clearly labeled; `anonymize` exists to lower the sharing barrier, and its docs say it pseudonymizes rather than anonymizes. Every number in `BENCHMARKS.md` says synthetic |
| Screen-reader and keyboard walkthrough (#74) | A human with assistive technology, ideally a real AT user. Open, updated 2026-08-21 | The blocking axe and HTML_CodeSniffer gates are a floor; `docs/a11y/STATEMENT.md` names WCAG 2.1 AA as the target and deliberately makes no conformance claim, because automated checks are not evidence of usability |
| Confirming the deployed playground end to end (#146) | Recording browser, OS and date against the live page. Open, updated 2026-08-23 | `scripts/check-playground-boots.cjs` now boots the live page in a real browser and asserts a finding renders, which answers most of it; the dated record is the remainder |
| Spec additions upstream: rosters (#45), runtimes (#42, #43), chargers (#46) | Upstream adopting any of the four. All open; #45 last touched 2024-08-26, #42 and #43 2024-08-28, #46 2023-12-29 | `docs/research/E1-upstream-spec-state.md` records that none is merged and one has been dormant for over two and a half years; `spec_watch` is the tripwire for the spec text, `check_phase_gates.py` for the proposals themselves |
| Two good first rules (#143, #144) | A contributor, or a maintainer deciding to absorb them. Open, updated 2026-08-23 | Both are labelled `good first issue` on purpose and neither blocks the v1.0.0 release; `docs/authoring-rules.md` carries the contract, fixture requirement, and doc-regeneration step for each |

## What would tell us this plan is wrong

- A real feed arriving early and failing in a way none of Phases 1 to 3
  anticipated. Then #76 outranks the sequence, and the sequence changes.
- The TODS Board adopting a conformance annex of its own. Phase 5 becomes
  contributing to theirs rather than proposing one, which is a better outcome
  than the plan describes.
- A second maintainer joining. Almost every "gated on people" row above is
  really gated on one person's available hours.
