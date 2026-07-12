# Impact × effort and sequencing

_Drafted 2026-07-01. Covers FIX-01…FIX-15
([`02-large-scale-fixes.md`](02-large-scale-fixes.md)) and EXP-01…EXP-16
([`03-expansions.md`](03-expansions.md)). This sequence deliberately goes
beyond `docs/roadmap.md` and `docs/RESEARCH-ROADMAP.md`; it does not replace
either — where they collide, the shipped roadmap wins until a real user says
otherwise._

## Impact × effort matrix

Impact here = leverage on the project's two strategic goals: being
trustworthy at production scale, and becoming the standard's reference
tooling. Judgments are the author-agent's reading of the code, not measured
demand.

| | **Effort S** | **Effort M** | **Effort L–XL** |
| --- | --- | --- | --- |
| **High impact** | FIX-10 (playground integrity), FIX-14 (make verify + audit doc), EXP-05 (init) | FIX-01 (one supplement engine), FIX-02 (assurance manifest), FIX-03 (derived-state caching), FIX-05 (structured findings), FIX-06 (one gating policy), FIX-13 (property tests), EXP-02 (drift), EXP-03 (spec-watch), EXP-08 (rule URLs), EXP-13 (synthetic benchmark feeds) | FIX-04 (memory model), EXP-14 (engine extraction), EXP-15 (rules-as-annex) |
| **Medium impact** | FIX-11 (Action supply chain), FIX-12 (anonymize hardening), EXP-04 (did-you-mean) | FIX-07 (baseline fingerprints), FIX-08 (cascade suppression), FIX-09 (severity remap), FIX-15 (HTML at scale), EXP-01 (explain), EXP-07 (read API), EXP-09 (workspace ledger), EXP-10 (publish VS Code ext), EXP-11 (doctor), EXP-12 (attestations) | EXP-06 (run timeline), EXP-16 (TODS×TIDES) |

No low-impact items were kept; candidates that fell below the line went to
"considered and rejected" in `03-expansions.md`.

## Dependency notes

- **Schema-bump cluster:** FIX-02 + FIX-05 (+ FIX-08's `caused_by`) should
  land as one report-schema 1.2.0 release — the add-only policy in
  `report.py` makes repeated bumps cheap but consumer churn is not.
- **FIX-05 → FIX-07** (fingerprints need structured params) **→ better
  `diff`/`--baseline`** across the board.
- **FIX-01 → FIX-03 → FIX-04**, in that order: unify the logic, then cache
  it, then change the memory representation under it. FIX-13's differential
  property test is the safety net for all three; write it first.
- **FIX-06** unblocks honest behavior for EXP-09 and EXP-11 (both compose
  subcommand verdicts and need one gating semantics).
- **FIX-15 → EXP-06** (timeline builds on the hardened HTML report).
- **EXP-01 → EXP-08** share the worked-example source; build the source once.
- **EXP-13** feeds FIX-03/04/15 acceptance tests and FIX-13 corpora — it is
  infrastructure for the fixes as much as an expansion.
- **E2/E7 (existing roadmap) → EXP-12 → EXP-15**: attestation and the
  normative annex only mean something once the corpus has upstream standing.
- **R1 (real feeds — existing roadmap keystone)** recalibrates EXP-13's
  generator, validates EXP-02's rename heuristics and EXP-04's
  false-positive bar, and gates v1.0 as already documented.

## Suggested sequence (beyond the existing roadmaps)

**Now — make the tool's own claims airtight (no external inputs needed):**
1. FIX-13 (property tests first — the net under everything that follows)
2. FIX-01 (one supplement engine, proven equivalent)
3. FIX-02 (assurance manifest — the honesty gap; pairs with the schema work
   in FIX-05)
4. FIX-05 (structured findings + SARIF enrichment; one schema bump with
   FIX-02)
5. FIX-06 (one gating policy), FIX-10, FIX-11, FIX-12, FIX-14 (small,
   independent, all close observed integrity gaps)

**Next — scale readiness and the diagnosis workflow:**
6. EXP-13 (synthetic benchmark feeds, loudly labeled) → FIX-03 (caching) →
   FIX-15 (HTML at scale), with FIX-04 (memory model) started if benchmarks
   justify it
7. FIX-07 (baseline fingerprints) and FIX-08 (cascade suppression) — the
   triage-quality pair
8. EXP-02 (drift command) and EXP-04 (did-you-mean) — the "GTFS moved"
   workflow, the personas' most-predicted real failure
9. EXP-03 (spec-watch) — cheap insurance on a moving spec
10. EXP-01 + EXP-08 (explain + stable rule URLs, one example source)

**Later — audience and position (mostly gated below):**
11. EXP-05 (init), EXP-10 (publish the extension), EXP-11 (doctor),
    FIX-09 (severity remap), EXP-07 (read API), EXP-09 (workspace ledger)
12. EXP-12 (attestations) once E2/E7 conversations have traction
13. EXP-14 (engine extraction) only on a concrete second-spec trigger
14. EXP-15 (rules-as-annex) as the long-game governance proposal
15. EXP-16 (TODS×TIDES) only after an explicit scope decision and real data

## Items gated on humans or real data — deferred honestly

The portfolio rule: defer and report, never fake. These cannot be completed
from this repo alone, and nothing above should be presented as satisfying
them.

| Item | Gate | What can honestly be done meanwhile |
| --- | --- | --- |
| R1 (existing) — real production feeds | An agency or vendor shares a feed (privately is fine) | EXP-13 synthetic feeds, clearly labeled; `anonymize` hardened by FIX-12 to lower the sharing barrier |
| FIX-04 final calibration | Real feed scale/shape | Synthetic benchmarks with published seeds; state that memory ceilings are synthetic-verified only |
| EXP-02 rename inference, EXP-04 suggestion precision | Real messy exports to measure false positives | Ship conservative; label heuristics unvalidated-on-real-data in docs |
| EXP-10 Marketplace / R5 listing | Publisher accounts, human UI steps | Package and document; mark "not yet published" honestly (as `editor/vscode/README.md` does today) |
| EXP-12, EXP-15, E2/E7 (existing) | TODS Board / MobilityData engagement and governance decisions | Write the proposals; track upstream issues (#148 already filed); take no "blessed" posture until granted |
| EXP-16 scope decision | Maintainer decision to renegotiate the out-of-scope line, plus operational partners and TIDES data | Nothing — explicitly parked; revisit only after R1 succeeds |
| Screen-reader walkthroughs (FIX-10, FIX-15, EXP-06 acceptance) | A human with assistive tech (ideally a real AT user, per P3) | Automated checks (axe-style) as the floor; record that automated ≠ verified |

## One-line closing judgment

The existing roadmaps already point outward (feeds, upstream adoption,
surfaces); this layer points inward — the highest-leverage unwritten work is
making the validator's *own* claims (equivalence, completeness of checking,
machine-consumability, scale) structurally true before real feeds arrive to
test them.
