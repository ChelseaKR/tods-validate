# Expansions

_Drafted 2026-07-01. Net-new relative to `docs/roadmap.md` and
`docs/RESEARCH-ROADMAP.md` (R1–R9, E1–E9); overlaps are cited and extended.
Effort tiers as in [`02-large-scale-fixes.md`](02-large-scale-fixes.md)._

## Horizon 1 — deepen the core

### EXP-01 — `tods-validate explain RULE_ID`
**Pitch:** an offline rule-detail command: description, severity rationale,
the `interpretation` note, the spec citation, and a worked before/after
example, straight from the registry.
**Impact:** the scheduler persona (P1) has two rule IDs in front of her and
`docs/rules.md` is 378 generated lines; `explain` is the two-ID-sized answer.
Complements R6 (worked examples in docs) by making the same content reachable
from the terminal, the LSP hover (`lsp.py` already renders hovers), and CI
logs. **Shape:** examples live as structured fields alongside the rule
(extend `Rule` in `rules/__init__.py` or a parallel `examples/` mapping keyed
by ID, reusing the conformance fixtures as the "before"); `explain --format
markdown` for pasting. `scripts/generate_rules_doc.py` consumes the same
source so docs and CLI cannot drift. **Effort:** M. **Risks/deps:** example
upkeep — the docs-drift CI check must cover them. **Excellent:** every core
rule has a worked example; `explain` output is tested; LSP hover and rules.md
render from the identical source.

### EXP-02 — `tods-validate drift OLD_GTFS NEW_GTFS --tods FEED`
**Pitch:** a first-class GTFS-drift analysis: given a TODS package and two
GTFS versions, report exactly which referenced trip/stop/service IDs
disappeared or changed block, with rename inference (1:1 candidates by
similarity) presented as review-grade hints.
**Impact:** goes beyond R8 (a static root-cause *hint* when W313/W302
cluster) to the actual diagnosis workflow for P2's recurring "GTFS moved
under my TODS" failure — the highest-frequency real-world breakage the
personas predict. **Shape:** reuse `build_companion()` on both GTFS versions;
set-diff the reference targets actually used by the TODS files; a
`--suggest`-style renames section that never auto-applies (honesty bar from
`suggest.py`). **Effort:** M–L. **Risks/deps:** rename inference must be
conservative; validate the heuristic on real feeds when R1 lands.
**Excellent:** on a synthetic renumbering scenario, drift names 100% of
broken references and proposes only correct renames.

### EXP-03 — Spec-watch: machine-diff the upstream spec against `schema.py`
**Pitch:** a script plus scheduled CI job that fetches the spec source
(`MobilityData/transit-operational-data-standard`, `docs/en/spec/index.md`),
parses the field tables, and diffs them against `schema.py`'s transcription,
opening an issue on drift.
**Impact:** `schema.py` is hand-transcribed ("If the spec and this file
disagree, the spec wins"). The standard is young and moving (v2.1.0 is ~14
months old; rosters/runtimes/chargers are live proposals). E1/E4 track
*adopted* changes; spec-watch is the earlier tripwire that makes falling
behind impossible to miss. **Shape:** `scripts/spec_watch.py` parsing the
spec's markdown tables into `FieldSpec`-shaped records; a weekly
`workflow_dispatch`+cron workflow (advisory, like `mutation.yml`); the diff
report doubles as the starting artifact for each new-version rule pass.
**Effort:** M. **Risks/deps:** upstream markdown format churn; network in CI
(keep it out of the merge gate). **Excellent:** a deliberate one-field change
in a forked spec copy is detected and rendered as a human-readable diff.

### EXP-04 — Reference-aware "did you mean" suggestions
**Pitch:** extend `suggest.py` with review-grade candidates for broken
references: when E307/E309/E303 fire and exactly one existing ID is within a
tight edit distance (or differs only by case/padding), propose it.
**Impact:** the largest class of errors with no suggestion today is the
reference band; schedulers fix these by eyeballing two files side by side.
**Shape:** new generators in `_GENERATORS` for E303/E307/E309 using the
companion sets already in `CompanionGTFS`; hard safety rails consistent with
the module's stated bar — never `auto`, only fire on a unique unambiguous
candidate, and say why ("differs only in case"). **Effort:** S–M.
**Risks/deps:** wrong suggestions are worse than none; measure false-positive
rate on real feeds before promoting beyond experimental. **Excellent:** on
the conformance fixtures plus synthetic typo corpora, zero wrong proposals
and ≥80% of single-typo breaks get the right one.

### EXP-05 — `tods-validate init`: a valid skeleton package
**Pitch:** scaffold a starter TODS package (headers from `schema.py`,
commented sample rows, a `tods-validate.toml`, a CI workflow stub) that
validates clean out of the box.
**Impact:** the standard is young; the first-export experience is currently
"read the spec, hand-build ten CSVs." A skeleton that already passes turns
the validator into the on-ramp, which is how a reference tool becomes
default infrastructure. **Shape:** generate from `TABLES` so it can never
drift from the schema; options for "runs only" vs "runs+vehicles" shapes;
sample rows lifted from `examples/sample-feed/`. **Effort:** S.
**Risks/deps:** none. **Excellent:** `init && validate` is green in one
command, and the generated workflow uses the pinned Action from FIX-11.

### EXP-06 — Accessible run timeline in the HTML report
**Pitch:** an opt-in visual timeline per run (SVG, inline, no assets) showing
events on a time axis with findings anchored to them — with a full text/table
equivalent so it adds nothing color- or vision-dependent.
**Impact:** W403/W404/E402/W409 are inherently spatio-temporal ("these two
events overlap", "the operator teleports"); schedulers reason on run diagrams
in every scheduling tool, and a picture of the gap is the fastest possible
explanation. Differentiates the report from every schema checker.
**Shape:** derives from the same `_events_by_run` view FIX-03 caches; render
into `render_html()` behind `--format html --timeline`; alt representation is
the existing findings table plus a per-run textual sequence list; palette and
patterns follow the report's AA constraints in both schemes (FIX-15).
**Effort:** L. **Risks/deps:** FIX-15 first; strict single-file discipline;
a11y review is the acceptance gate, not an afterthought. **Excellent:** a
screen-reader user gets the identical information from the text equivalent,
verified in the committed walkthrough.

## Horizon 2 — adjacent capabilities, audiences, integrations

### EXP-07 — A documented read API: `tods_validate` as the canonical TODS reader
**Pitch:** promote the internal model (`Package`, the supplemented
`CompanionGTFS` views, `merge_supplement`) into a small documented read API,
with an optional `pandas`-free `to_rows()` / opt-in dataframe extra.
**Impact:** researchers and app developers (P9) currently get validation and
`stats` but must hand-roll CSV reading to *consume* TODS; every consumer that
builds on this library deepens the reference-implementation position. The
loader, supplement logic, and safety limits already exist — this is exposure
plus a compatibility promise, not new machinery. **Shape:** `tods_validate.read`
namespace re-exporting a curated surface after FIX-01 stabilizes the
supplement module; docs page parallel to `docs/api.md`; extend the semver
promise to it explicitly. **Effort:** M. **Risks/deps:** widening the public
API widens the v1.0 stability commitment — curate hard. **Excellent:** a
third-party notebook can load a feed, apply supplements, and tabulate runs in
under ten lines without touching `csv`.

### EXP-08 — Stable per-rule web pages (rule browser on Pages) — done
**Pitch:** generate a static rule-catalog site from the registry — one URL
per rule ID with description, severity, interpretation, spec citation, worked
example, and fixture link — deployed alongside the playground.
**Impact:** gives SARIF `helpUri` (FIX-05), LSP hovers, CI annotations, and
working-group discussions a permanent deep link per rule; this is how
gtfs-validator's rules page anchors its ecosystem, and it is the natural
publication form if the corpus goes upstream (E2). **Shape:** extend
`scripts/generate_rules_doc.py` to also emit per-rule HTML into `web/rules/`;
`pages.yml` already deploys `web/`; URLs follow the never-renumbered rule-ID
contract so links are permanent. **Effort:** M. **Risks/deps:** EXP-01's
example source; keep generated pages in the docs-drift CI check.
**Excellent:** every rule ID in every output format resolves to a stable URL.
**Status (2026-07-03):** shipped, minus the worked-example/fixture link (still
depends on EXP-01's example source, not yet built). `generate_rules_doc.py`
now emits one `web/rules/<RULE_ID>.html` page per rule plus a
`web/rules/index.html` catalog grouped by band, id/title/severity/needs-GTFS
note/opt-in note/description/interpretation/spec link, self-contained
(inline `<style>`, no external assets), and `--check` fails on drift so CI
catches it. `report.py`'s SARIF `helpUri` now points at
`RULE_PAGE_BASE + "<id>.html"` (spec citation kept alongside as
`properties.specSection`), and the LSP hover text links both the rule page
and the spec. See `roadmap/exp-08-stable-per-rule-web-pages-on-page`.

### EXP-09 — Workspace mode with a run-history ledger — **Done**
**Status:** Implemented. `src/tods_validate/workspace.py` adds a
schema-versioned (`HISTORY_SCHEMA_VERSION`) `HistoryRecord`, built via
`build_record()` by reusing `report.summarize()`/`report.by_rule()` so the
ledger and the JSON report can never disagree about counts.
`batch --history DIR` (or `[workspace]` `history-dir` in
`tods-validate.toml`, CLI flag winning per the existing config precedence)
appends one JSON object per run to `DIR/history.jsonl` via `append_record()`
— append-only, artifact-shaped, no hosted service. A new `trend --history
DIR` command reads the ledger with `load_history()` (missing/foreign-schema
lines are skipped cleanly, not fatal) and prints `render_trend()`'s
text-first, sparkline-free Markdown: one table per source/agency, oldest run
first, with a Δ-errors and "new/worse rules" column so a regression is
visible without re-running anything. Tests: `tests/test_workspace.py` and
the `--history`/`trend`/`[workspace]` cases in `tests/test_config.py`,
including an explicit assertion that finding message text never reaches the
ledger. **Privacy constraint (kept):** a record stores only counts and rule
IDs, documented as load-bearing in `workspace.py`'s module docstring and in
`README.md`, never `Finding.message`/`suggestion` text.

**Pitch:** a `[workspace]` config listing feeds plus a local append-only
history (JSONL of report summaries per run), giving `batch` and `diff`
memory: trends, "which agency regressed this pick," time-to-green.
**Impact:** supplies the missing data layer under E5 (fleet compliance
artifact) and E8 (comparative stats) — both currently presume aggregates
that nothing persists. Stays artifact-shaped (files in the repo, no hosted
service), which keeps it inside the project's out-of-scope line. **Shape:**
`workspace.py`; `batch --history .tods-history/` appends schema-versioned
summary records (reusing the JSON report's summary block); a `trend`
renderer producing Markdown sparkline-free tables (text-first, accessible).
**Effort:** M. **Risks/deps:** privacy — history must store counts, never
finding messages that could carry IDs; document that. **Excellent:** a
state-DOT-shaped consumer can produce a quarter-over-quarter Markdown
compliance table from CI artifacts alone.

### EXP-10 — Ship the editor story: publish the VS Code extension
**Pitch:** publish `editor/vscode/` to the Marketplace and Open VSX, with
bundled server discovery (find `tods-validate-lsp` on PATH, offer pipx
install guidance when missing).
**Impact:** the LSP server, quick fixes, and hovers exist (`lsp.py`,
CHANGELOG) but reach zero users unpublished; an installable extension is the
lowest-friction surface for vendor engineers who live in editors. R5 covers
the *Action* marketplace only — the extension is unclaimed territory.
**Shape:** CI packaging job (`vsce package`) with the same SHA-pinning
posture as `pypi-publish.yml`; extension README documents the two-part
install honestly. **Effort:** S–M. **Risks/deps:** publisher account setup
(human gate); keep the extension thin so version skew with the server stays
harmless. **Excellent:** cold start from Marketplace install to first inline
diagnostic in under five minutes, documented with a walkthrough.

### EXP-11 — `tods-validate doctor`: one honest end-to-end pass

**Status: done (2026-07-03).** Implemented as `tods-validate doctor PATH`:
`doctor.py` runs validate → merge → (if java and a jar are already available
via `--gtfs-validator-jar`/`GTFS_VALIDATOR_JAR`, never downloaded) gtfs-validator
on the merged feed → stats in one pass, and `render_doctor_text`/
`render_doctor_markdown`/`doctor_to_dict` print one combined report where
every stage is explicitly labeled RAN, SKIPPED (with its reason), or FAILED —
a skipped merge or gtfs-validator stage says "merged-feed GTFS validity NOT
checked" rather than reading as a pass. `--format json` exposes a per-stage
`status` field for tooling; the exit code fails on validate findings at the
`--fail-on` severity or a FAILED gtfs-validator stage, never on a merely
skipped one.

**Pitch:** orchestrate the full publish-readiness sequence — validate → merge
→ (if Java present) gtfs-validator on the merged feed → stats — into one
command with a single combined report that clearly labels any skipped stage.
**Impact:** the README already teaches this as a four-step CI recipe; P2
wants it as one gate. The honesty mechanics matter: when gtfs-validator or
Java is absent, `doctor` must say "merged-feed GTFS validity NOT checked"
(same principle as FIX-02) rather than silently passing. **Shape:**
`doctor.py` composing existing modules; gtfs-validator integration is
invoke-if-present, never download-by-default (no surprise network);
`--format markdown` emits the combined stamped artifact. **Effort:** M.
**Risks/deps:** subprocess/Java variance across CI images; parsing
gtfs-validator's JSON report shape (pin the supported version range).
**Excellent:** one command, one artifact, every stage's ran/skipped status
explicit.

### EXP-12 — Verifiable exporter conformance attestations
**Pitch:** let an exporter turn "we pass the conformance corpus" into a
signed, machine-verifiable artifact: a JSON attestation (tool version,
corpus hash, expectations hash, result) attestable with the same
Sigstore/SLSA tooling the release pipeline already uses.
**Impact:** builds the tooling under E7 (conformance-level definition) and
gives E2 (corpus upstream) teeth: an agency evaluating a HASTUS/Optibus-class
exporter can verify the claim instead of trusting a README badge. This is
procurement-grade honesty — on-ethos and unclaimed by any roadmap item.
**Shape:** `tods-validate certify --corpus tods-conformance-corpus.zip`
producing the attestation payload; a documented GitHub Actions recipe using
`actions/attest-build-provenance` (already SHA-pinned in
`pypi-publish.yml`) to sign it; verification instructions in
`docs/conformance.md`. **Effort:** M–L. **Risks/deps:** meaningless until
the corpus has upstream legitimacy (E2) and a level definition (E7);
sequence after those conversations start. **Excellent:** a third party can
verify an attestation offline with public tooling and reproduce the result
from the pinned corpus.

### EXP-13 — Published synthetic benchmark feeds (clearly labeled)
**Pitch:** a generator (`scripts/generate_feed.py`) that produces realistic,
parameterized synthetic TODS+GTFS packages (N runs, M% deadheads, seeded
error injection), published as release artifacts next to the corpus.
**Impact:** while R1 (real feeds) pends, this gives the performance work
(FIX-03/04), the HTML-at-scale work (FIX-15), fuzzing (FIX-13), and
researchers (P9) something honest to chew on. The portfolio ethos is the
design constraint: every artifact is loudly labeled synthetic, never
presented as real-world evidence — it complements R1, it does not substitute
for it. **Shape:** deterministic seeded generation; profiles ("clean-100k",
"drifted-gtfs", "messy-export"); `scripts/benchmark.py` consumes them.
**Effort:** M. **Risks/deps:** synthetic realism is bounded by the author's
model of feeds — say so in the artifact README; recalibrate once real feeds
arrive. **Excellent:** benchmark results in docs cite exact generator seeds,
making every published number reproducible by anyone.

## Horizon 3 — transformative bets

### EXP-14 — Extract the engine: an operational-data validation core
**Pitch:** split the generic machinery (rule registry, findings, renderers,
gating, corpus contract, testing helpers) from the TODS-specific schema and
rules, so a sibling validator for another MobilityData-family spec (TIDES is
the obvious candidate) is a schema module, not a new project.
**Impact:** the registry in `rules/__init__.py`, `findings.py`, `report.py`,
and `testing.py` contain almost nothing TODS-specific today; the marginal
cost of a second validator is mostly schema transcription. A shared core
would make this portfolio the default toolkit for transit operational-data
QA rather than a single-spec tool. **Shape:** internal package split first
(no new distribution until a second consumer is real); the TODS distribution
stays exactly as it is for users. **Risks/deps:** premature abstraction is
the classic failure — the honest trigger is a concrete second spec with a
committed user, not speculation; v1.0's stability promise must not be
complicated by the split. **Effort:** XL. **Excellent:** a proof-of-concept
second-spec validator reaching parity with this repo's structure band in
under a week of work, without forking the engine.

### EXP-15 — Rules as a normative annex of the spec
**Pitch:** propose upstream that TODS requirements get normative,
machine-checkable rule IDs — this validator's catalog (IDs, severities,
interpretations) adopted or adapted as the spec's own conformance annex,
with the corpus as its test vector set.
**Impact:** the endgame beyond E2 (corpus upstream): gtfs.org referencing
gtfs-validator notices is the precedent. If the Board adopts a rules annex,
every future validator implements *these* semantics, and the eight
`spec-questions.md` ambiguities get decided as part of adoption — resolving
P7's "no authority to break the tie" objection at the root. **Shape:** a
written proposal to the TODS Board pairing each spec MUST/SHOULD with a rule
ID and interpretation note; governance offer consistent with `CLAUDE.md`'s
"adoption, not ownership." **Effort:** L (mostly writing and stewardship,
little code). **Risks/deps:** entirely a human/governance gate — the Board
may prefer to own semantics; the fallback (a well-maintained third-party
catalog) is still valuable. **Excellent:** at least one spec release cites
rule IDs from this catalog, whatever repo they live in by then.

### EXP-16 — Planned-vs-actual: TODS × TIDES reconciliation
**Pitch:** a reconciliation tool comparing planned operations (TODS runs,
vehicle assignments) against recorded operations (TIDES-style historical
data): unworked runs, unplanned vehicle swaps, systematic schedule deviation.
**Impact:** turns the validator into the front of an operational-quality
loop — the analysis layer agencies actually staff people for. It is the
largest plausible expansion of the project's audience (planning + operations
+ oversight). **Shape:** would build on EXP-07's read API and EXP-14's core;
consumes TIDES tables as a second package type. **Effort:** XL.
**Risks/deps:** this crosses the current out-of-scope line's spirit
(`docs/roadmap.md` excludes GTFS-realtime correlation; TIDES is adjacent to
that exclusion) — it requires an explicit, documented scope decision, real
TIDES data, and real operational partners. Flagged as a bet to *evaluate
after* R1 succeeds, not a plan. **Excellent:** a pilot with one agency's
real (or explicitly-labeled synthetic) week of data producing a
reconciliation report an operations manager acts on.

## Considered and rejected (for the record)

- **LLM-assisted finding explanations.** The findings *are* the product and
  are already written for humans; adding a nondeterministic paraphrase layer
  would trade the project's determinism and citability for nothing. Revisit
  only if real users report comprehension failures EXP-01 cannot fix.
- **A hosted dashboard/service.** Repeatedly implied by personas (P11),
  repeatedly and correctly kept artifact-shaped (E5, EXP-09). A service
  means uptime, auth, and custody of non-public operational data — the exact
  liabilities the zero-upload playground was built to avoid.
- **Re-validating GTFS.** Still out of scope (`docs/roadmap.md`);
  gtfs-validator exists and EXP-11 integrates it honestly instead.
