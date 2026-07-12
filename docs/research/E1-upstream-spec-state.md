# E1 — current state of the roster/runtime/charger proposals upstream

Research only. This documents external reality on the TODS spec repository
as of **2026-07-09** — not a decision this project has made, and not
something that will stay accurate indefinitely. Re-check the linked
issues/PRs before acting on this again; the "Recommendation" section at the
bottom is the only part meant to be durable.

`docs/RESEARCH-ROADMAP.md`'s E1 line reads: "Validate the adopted-next spec
additions behind `--enable experimental`: rosters (#45), runtimes (#42/#43),
chargers/electrification (#46)." This is that research. Every claim below
cites a fetched GitHub issue, pull request, or comment on
[`MobilityData/transit-operational-data-standard`](https://github.com/MobilityData/transit-operational-data-standard) —
nothing here is inferred from the field names alone.

## Summary

None of the three proposals are merged into the spec. Their real states are
not equivalent to each other:

| Proposal | Issue | Draft PR opened? | Last activity | State |
| --- | --- | --- | --- | --- |
| Rosters | [#45](https://github.com/MobilityData/transit-operational-data-standard/issues/45) | Yes — [#81](https://github.com/MobilityData/transit-operational-data-standard/pull/81) (closed, unmerged) | 2025-03-24 (PR #81 closed); [#87](https://github.com/MobilityData/transit-operational-data-standard/pull/87) merged 2025-05-06 | **Functionally superseded** by a narrower shipped file |
| Runtimes | [#42](https://github.com/MobilityData/transit-operational-data-standard/issues/42) | No | 2024-08-28 | **Open, unresolved design questions**, no draft spec text |
| `runtime_build_point` | [#43](https://github.com/MobilityData/transit-operational-data-standard/issues/43) | No | 2024-08-28 | **Open**, blocked on #42 |
| Chargers | [#46](https://github.com/MobilityData/transit-operational-data-standard/issues/46) | No | 2023-12-29 | **Dormant** (~2.5 years, no follow-up) |

## Rosters (#45) — functionally superseded, already covered

Issue #45 ("add rosters.txt", opened 2023-11-30) proposed a `rosters.txt`
file with one column per day of the week
(`monday_run`…`sunday_run`) and a `week_sequence` for multi-week rotations.
Discussion in the issue surfaced real problems with that shape (how to
handle a roster spanning multiple `service_id`s, whether duplicate primary
keys are allowed) that were never fully resolved on the issue itself.

The working group's actual resolution happened in two pull requests, not on
the issue:

- **[PR #81](https://github.com/MobilityData/transit-operational-data-standard/pull/81)**,
  "potential rosters and employee assignment spec" (opened 2024-09-20 per
  the underlying commit history, closed **unmerged** 2025-03-24), proposed
  four files: `rosters.txt`, `roster_dates.txt`, `employee_rosters.txt`, and
  `employee_run_dates.txt` — explicitly framed as "unifying #28 and #45."
  Extensive discussion (unique run IDs, multi-week rotations, a proposed
  `roster_groups` file) ran through late 2024 and into 2025, including a
  2025 working-group decision to *defer* multi-week roster support entirely
  ("this is likely a high priority for Euro operators, but adds a level of
  complexity that we are not currently prepared to consider").
- **[PR #87](https://github.com/MobilityData/transit-operational-data-standard/pull/87)**,
  "employee_run_dates.txt" (merged 2025-05-06), explicitly narrowed PR #81
  down to a single file: "A previous discussion (in #81) considered adding
  more files to be able to represent more details about rosters, but this
  PR is now our preferred approach... There's no more roster positions."

`employee_run_dates.txt` is one of the three TODS-specific files the
[revision history](https://tods-transit.org/spec/revision-history/) credits
to **TODS v2.1.0** (approved 2025-04-16; PR #87 itself merged 2025-05-06,
three weeks later — the spec text and the Board's version-approval date
evidently did not move in lockstep here, which this research does not
attempt to fully reconcile). It is already fully validated by this project
(`schema.EMPLOYEE_RUN_DATES`, rules
`TODS-E106`/`E201`/`E301`/`W302`/`W406`). Issue #45 itself is still open on
GitHub — it was never formally closed — but the working group's own record
(PR #87's description) treats the broader `rosters.txt` concept it asked
for as superseded, not as still-pending work. There is nothing left for
`--enable experimental` to add here that `--enable` (unconditionally, since
it is not opt-in) does not already check.

## Runtimes (#42) and `runtime_build_point` (#43) — open, unresolved

Issue #42 ("add runtimes.txt", opened 2023-11-30, last substantive comment
2024-08-28) proposes a file recording expected travel time between two
locations over a time-of-day window, for round-tripping schedule data
between network-planning and scheduling software. Issue #43 proposes a
companion `runtime_build_point` field, contingent on #42's `runtime_style`
enum.

Neither issue has a draft PR — a repository-wide PR search for
"runtime"/"roster"/"charger" against this repo returns only the four PRs
already discussed above (#80, #81, #85, #87); none touch runtimes or
chargers. The issue thread itself has real, unresolved field-level
questions as of the last comment (2024-08-28):

- Whether a `not_stopping`/"passing" concept is needed (raised by
  @jeffkessler-keolis; @BTollison proposed a `not_stopping` boolean or a
  4-value enum, with an explicit "I shall investigate if this applies to
  other parts of the world to ensure completeness" — i.e., acknowledged as
  unresolved).
- Whether `runtime_style = 1` (build-point-based distribution) belongs in
  the standard at all — @skyqrose's original objection ("this seems like an
  internal detail of the scheduling application... an implementation
  detail is still enshrining an implementation detail in the standard")
  was only ever downgraded to "a very weak objection," not withdrawn.
- The exact column set changed materially between the 2023 and the
  "Revised for TODS 2.0" 2024-08-28 version posted in the same issue
  (`is_deadhead` renamed `is_revenue` with inverted meaning; `from`/`to`
  redefined from "`stop_id` or `ops_location_id`" to "`stop_id` from either
  `stops.txt` or `stops_supplement.txt`" only, following the Supplement-file
  mechanism landing in the meantime).

There is no stable field list to transcribe. Any implementation today would
be encoding one commenter's most recent proposal, not a spec.

## Chargers (#46) — dormant

Issue #46 ("add chargers.txt", opened 2023-12-01) has three comments, the
last on 2023-12-29 — about two and a half years of no further activity as
of this research. The one substantive comment (@jeffkessler-keolis)
proposed generalizing the file to `power_stations.txt` to cover non-electric
fueling too, renaming `number_of_chargers` → `number_of_power_stands` and
`max_kw` → `max_output`; that rename was never responded to, so it is
unknown whether the working group would even agree on the file's name, let
alone its final fields.

## Recommendation

Do not implement `--enable experimental` rules for any of these three
proposals right now. The repo's own convention — never invent spec
details — applies as much to a moving proposal as to the adopted spec text:
encoding runtimes.txt's 2024-08-28 comment-thread shape as if it were a
stable target would produce a validator that claims a conformance the real
spec does not have, and that would need rewriting (or, worse, would
silently validate against a stale shape) the moment the working group
actually resolves the open questions above.

What would change this recommendation, in order of how close each is:

1. **Rosters**: nothing to do — already covered via `employee_run_dates.txt`.
   If issue #45 is ever formally closed as superseded, that is worth noting
   in `docs/spec-questions.md` or a roadmap update, but changes no code.
2. **Runtimes / `runtime_build_point`**: revisit once a PR is opened against
   the spec repository with a committed field table (not just an issue
   comment). A merged PR is a stronger signal than a draft one, but even a
   draft PR would give a citable, versioned target instead of "the most
   recent issue comment," which is what a proposal being litigated in an
   issue thread cannot offer.
3. **Chargers**: revisit if the issue sees any new activity at all — right
   now there is not even a settled file name to build against.

The `experimental` rule category already exists in
`src/tods_validate/rules/__init__.py` (`CATEGORIES`) and `--enable
experimental` is already a documented, accepted token — the scaffolding
this line item would use is real and ready. What is missing is spec text
mature enough to transcribe without guessing, which is a fact about the
standard's development, not about this validator.
