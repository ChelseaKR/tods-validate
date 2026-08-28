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

## Phase 2: freeze the contract, ship v1.0.0 (2026 Q4 to 2027 Q1)

**Delivers.** The stability commitments `roadmap.md` reserves for v1.0.0:
semantic-versioning guarantees on rule IDs, exit codes, the public Python
exports, and the JSON report schema.

- Promote `docs/v1-contract-audit.md` from candidate to contract, after one
  conformance-only release has shipped with no unreviewed drift against
  `v1-contract-candidate.json`.
- Resolve the one open conformance decision that snapshot records: the
  `employee_run_dates.txt` primary key, and with it `TODS-E204` versus
  `TODS-W408`. Blocked on upstream PR #156 landing.
- Finish the remaining fail-open work that is a compatibility decision rather
  than a fix, chiefly the companion-GTFS reader's silent degradation and its
  effect on the coverage manifest. Doing this before the freeze is the point:
  after v1.0.0 it becomes a breaking change.
- Close the packaging and process gaps that should not cross a 1.0 boundary
  open: PEP 735 dependency groups (CQ-27, #145), the CHANGELOG heading format
  (DOC-07/REL-10), and the stray `v0` tag.
- Two small spec-cited rules exist as bounded, documented work with their
  contract already written down in `docs/authoring-rules.md`: a structure
  warning for a recognized-but-unexpected file (#143) and a second advisory
  rule (#144). Both are good first contributions and neither blocks the
  release.

**Depends on.** Upstream PR #156 (people, not engineering). The branch
ruleset (CQ-37 to 43, CICD-03/11-18) and the PyPI environment scoping
(CICD-06) both need live GitHub and PyPI settings changes that no automated
pass should make; they are prerequisites for the release *process* being what
`DEFINITION_OF_DONE.md` says it is, and they are one interactive session's
work whenever the maintainer chooses.

**Done when.** `v1.0.0` is tagged, annotated and signed; the contract
snapshot went one full release cycle unchanged before the tag;
`v1-contract-audit.md` no longer says "candidate"; and the branch ruleset is
committed as `docs/rulesets/main.json` rather than living as tribal
knowledge.

## Phase 3: scale readiness and triage quality (2027 Q2 to Q3)

**Delivers.** The answer to "what happens on a real agency's feed", to the
extent it can be answered without one.

- Published synthetic benchmark feeds, loudly labeled as synthetic
  (EXP-13). This is infrastructure for the rest of the phase as much as an
  expansion: it feeds the caching, memory, and HTML acceptance tests.
- Derived-state caching and the memory model (FIX-03, FIX-04), in that order,
  with the property and differential tests as the safety net.
- An HTML report that survives a feed with ten thousand findings (FIX-15).
- The Lighthouse and bundle baseline the performance section of
  `CONFORMANCE-GAPS.md` still lists as open, and a dated
  `docs/a11y/STATEMENT.md` with a named WCAG conformance target.
- Mutation kill-rate on the rules engine ratcheted from roughly 65% toward
  the 70% target (CQ-47). Ratchet, do not jump.

**Depends on.** Phase 2's contract freeze, so that performance work cannot
quietly change behavior. Final calibration depends on real feeds and will not
get it; the honest output is a documented ceiling labeled synthetic-verified
only.

**Done when.** A published, seeded benchmark corpus exists; the throughput
and memory ceilings are documented with the machine class they were measured
on; the HTML report is usable at ten thousand findings; and every claim in
this phase says whether it was verified against real data or synthetic.

## Phase 4: surfaces, and room for a second maintainer (2027 Q4 to 2028 Q1)

**Delivers.** The work that widens who can use and who can maintain this.

- Publish the VS Code extension to the Marketplace and Open VSX (EXP-10). CI
  already builds a reviewable VSIX; `editor/vscode/README.md` already says
  honestly that it is not published.
- The remaining reporting and workflow surfaces from
  `ideation/03-expansions.md` Horizon 2 that are not yet built.
- The standards work that is about operating a project rather than shipping
  code: the incident-response label convention, postmortem template and
  secret-exposure runbook; the data-governance data card and source
  inventory; the DORA quarterly review cadence (QM-11); the AI-development
  diagnostic baseline. All four are open rows in `CONFORMANCE-GAPS.md` with
  nobody assigned.
- `CODEOWNERS` already exists and is waiting for a second person. Solo
  self-review is a structural limitation no ruleset fixes, and that limit is
  what this phase is really about.

**Depends on.** Publisher accounts and human UI steps for the extension.
A second maintainer is a person, not a milestone; the phase delivers the
readiness for one either way.

**Done when.** The extension is installable from a marketplace, or the phase
records why it is not; and each of the four standards rows above is either
closed or has a dated decision saying it will not be.

## Phase 5: upstream standing (2028)

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

**Depends on.** Entirely on the TODS Board and MobilityData. This is the
phase this repository cannot execute alone, and saying otherwise would be the
same kind of overclaim the validator is built to refuse. The fallback, a
well-maintained third-party catalog, is what exists today and is already
useful.

**Done when.** At least one spec release cites rule IDs from this catalog,
whatever repository they live in by then; or the Board declines, and that is
recorded so nobody re-litigates it from scratch.

## Phase 6: only on a trigger (2028 H2 to 2029)

Two large bets, neither scheduled, each with a written trigger. A phase with
no trigger met is a phase that does not start.

- **Extract the engine (EXP-14).** The registry, findings, renderers, and
  gating contain almost nothing TODS-specific, so a validator for a second
  MobilityData-family spec would be a schema module rather than a new
  project. **Trigger:** a concrete second spec with a committed user. Not
  speculation, and not before v1.0's stability promise can absorb the split.
- **Planned versus actual, TODS against TIDES (EXP-16).** Explicitly parked.
  It crosses the spirit of the current out-of-scope line, and needs a
  documented scope decision, real TIDES data, and real operational partners.
  **Trigger:** real-feed adoption (#76) succeeding first, then an explicit
  decision to renegotiate the scope line.

## Standing work that no phase owns

These run across every phase and are gated on people. They are listed here
rather than scheduled because a date on them would be fiction.

| Work | Gate | What is honest meanwhile |
| --- | --- | --- |
| Real production feeds (#76) | An agency or vendor sharing a feed, privately is fine | Synthetic corpora, clearly labeled; `anonymize` exists to lower the sharing barrier, and its docs say it pseudonymizes rather than anonymizes |
| Screen-reader and keyboard walkthrough (#74) | A human with assistive technology, ideally a real AT user | The blocking axe and HTML_CodeSniffer gates are a floor; `docs/a11y/2026-08-21-automated-only-not-a-substitute.md` already records that automated checks are not evidence of usability |
| Confirming the deployed playground end to end (#146) | Recording browser, OS and date against the live page | `scripts/check-playground-boots.cjs` now boots the live page in a real browser and asserts a finding renders, which answers most of it; the dated record is the remainder |
| Spec additions upstream (rosters, runtimes, chargers) | Upstream adopting any of the three | `docs/research/E1-upstream-spec-state.md` records that all three are open and unmerged, one dormant since 2023; `spec_watch` is the tripwire for when that changes |

## What would tell us this plan is wrong

- A real feed arriving early and failing in a way none of Phases 1 to 3
  anticipated. Then #76 outranks the sequence, and the sequence changes.
- The TODS Board adopting a conformance annex of its own. Phase 5 becomes
  contributing to theirs rather than proposing one, which is a better outcome
  than the plan describes.
- A second maintainer joining. Almost every "gated on people" row above is
  really gated on one person's available hours.
