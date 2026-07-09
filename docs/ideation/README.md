# Ideation — large-scale fixes and expansions

_Drafted 2026-07-01._

This folder is the layer **above** the existing planning documents: extensive
ideation on deep structural fixes and larger expansions that are *not* already
written down anywhere in this repo. It was produced from a fresh read of the
source, tests, CI, and docs on 2026-07-01.

## How this relates to the existing documents

- [`docs/roadmap.md`](../roadmap.md) is the shipped product roadmap (v0.5.0
  spec tracking, the v1.0.0 stability gate, the out-of-scope line). Nothing
  here restates it.
- [`docs/RESEARCH-ROADMAP.md`](../RESEARCH-ROADMAP.md) (2026-06-30) triaged the
  synthetic persona panel in [`docs/USER-RESEARCH.md`](../USER-RESEARCH.md)
  into remediations R1–R9 and expansions E1–E9. Nothing here restates those
  either; where an idea builds on one, it cites the ID (e.g. "extends E6") and
  says what is new beyond it.
- Everything in this folder is **net-new**: it comes from reading the actual
  code (`src/tods_validate/`), the test suite, and the CI workflows, and from
  asking what a validator that intends to anchor a young standard needs
  structurally, not just feature-wise.

## Contents

| File | What it holds |
| --- | --- |
| [`01-deep-dive.md`](01-deep-dive.md) | Current-state assessment: architecture map with file paths, genuine strengths, structural debt actually observed, strategic position in the portfolio |
| [`02-large-scale-fixes.md`](02-large-scale-fixes.md) | FIX-01…FIX-15 — deep structural fixes: engine design, correctness, security, accessibility, performance, operability |
| [`03-expansions.md`](03-expansions.md) | EXP-01…EXP-16 — expansion ideas across three horizons (deepen the core, adjacent capabilities, transformative bets), plus considered-and-rejected ideas |
| [`04-impact-and-sequencing.md`](04-impact-and-sequencing.md) | Impact×effort matrix over all FIX/EXP IDs, dependencies, a Now/Next/Later sequence beyond the existing roadmaps, and the human/real-data gates |

## Honest framing

These are **ideas for evaluation, not commitments**. None of them has been
sized against real user demand — the repo's single biggest known unknown is
still that no real production TODS feed has been validated (R1 in the research
roadmap, and the v1.0 gate in the product roadmap). Several items below are
explicitly gated on that, and [`04-impact-and-sequencing.md`](04-impact-and-sequencing.md)
separates them out rather than pretending they can be finished from synthetic
fixtures alone. Where a claim about the code is uncertain, the text says so.
