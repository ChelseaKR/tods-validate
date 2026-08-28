# 0007: a companion GTFS file that did not read in full is not available to resolve references

- Status: accepted (2026-08-27)
- Date: 2026-08-27
- Relates to: #125 (the unreadable-file half of the same defect), phase 2 of
  `docs/MULTIYEAR-PLAN.md`

## Context

The validator resolves TODS IDs against a companion GTFS feed. `loader.py`
splits the defects it can find in a CSV into two kinds:

- **Blocking** (`encoding`, `empty`, `csv_error`): parsing stopped, so the
  file has no headers and no rows. #125 established that a blocking defect in
  a companion base file makes that file *absent* rather than *present and
  empty*, because an empty table turns every real reference into a dangling
  one. `CompanionGTFS.unreadable` records the reason and TODS-W302 discloses
  it.
- **Degrading** (`ragged`, `duplicate_header`): parsing finished, but some
  values did not survive it. A ragged row's values do not line up with the
  header, so any field of that row may hold a neighbouring column's value or
  nothing. A duplicated column name means the second column's values were
  dropped.

The second kind was treated as a clean read. Nothing reported it and nothing
disclosed it: `TODS-E103`, `TODS-E104` and `TODS-E105` iterate
`context.tables`, which holds TODS files, so a defect in a *companion GTFS*
file is not a finding under any rule. The file still counted as `present`, so
every rule that reads it recorded `ran` in the coverage manifest.

The result was the repository's recurring failure shape, in both directions.
Given a `trips.txt` with one short row:

- If the truncation fell after `trip_id`, the trip survived with a blank
  `block_id`. The report said "No problems found", the coverage line said
  "Every applicable check ran", and the gate exited 0.
- If the truncation fell before `trip_id`, the trip vanished from the reader's
  view, and the run event naming it was reported as `TODS-E307`: an ERROR
  against the producer's *TODS* file, carrying the message "trip_id '103' does
  not exist in the companion GTFS trips.txt", which was false. It did exist.
  The reader had failed to read it.

Both were reported by rules whose recorded status was `ran`.

## Decision

A companion GTFS base file that is not fully read is not available to resolve
references against, exactly as an unreadable one already was not.

- `FeedFile.fully_read` is False when any `LoadProblem` was recorded. It is
  deliberately stricter than `readable`, and deliberately phrased over "any
  problem" rather than "any known degrading problem", so a problem code added
  later counts as incomplete until somebody decides otherwise.
- `gtfs_companion._resolve_base` returns None for such a file and records why
  in `CompanionGTFS.degraded`, a map kept separate from `unreadable` because
  the two ask the producer for different things: re-export the file, versus
  fix a named row or column.
- The file is therefore not in `CompanionGTFS.present`, so `missing_gtfs_tables`
  reports it missing, dependent rules are recorded
  `skipped:needs_gtfs_table` rather than `ran`, and the skip counts as
  unrequested, so `--require-complete-run` fails on it.
- `TODS-W302` gains a third message, distinct from the missing-file and
  unreadable-file wordings, quoting the loader's own message so the producer
  gets the row or column number.
- `loader.PROBLEM_CODES` closes the code space: `BLOCKING_PROBLEM_CODES` and
  `DEGRADING_PROBLEM_CODES` are disjoint and, per a test that reads the
  parser's own source, exhaustive. A new code cannot default to harmless.

## Why this is a compatibility decision, and why it lands before v1.0.0

This changes what a run does, not only what it says. Rules that used to run
now skip; a `TODS-E307` that used to fire now does not; a feed that used to
exit 0 now exits 0 with two warnings, or non-zero under
`--require-complete-run`. `docs/v1-contract-audit.md` puts rule behavior
inside the v1 stability promise, so after v1.0.0 this would be a major-version
change. Phase 2 of `docs/MULTIYEAR-PLAN.md` sequences it ahead of the contract
freeze for that reason.

## Consequences

- One malformed row in a large companion `stop_times.txt` disables the checks
  that read stop times, rather than silently reducing them. That cost is real
  and it is the honest one: the alternative is answering a question about IDs
  from a list the reader knows is short. The report names the file, the row,
  and every check that did not run, so the remedy is one line of output away,
  and MobilityData's gtfs-validator flags the same defect on the same file.
- The wording of `skipped:needs_gtfs_table` in the coverage manifest widens to
  cover all three cases. It previously said the feed "has none of the files the
  check reads", which was already inaccurate for #125's unreadable files: the
  file was there.
- `TODS-W302`'s title changes from "missing or unreadable" to "missing or was
  not read in full". The rule ID, severity and category are unchanged, so the
  contract snapshot in `docs/v1-contract-candidate.json` is unaffected.
- Structural defects in a companion GTFS feed are still not findings in their
  own right. Making them findings would mean this tool reporting on GTFS
  conformance, which `roadmap.md` puts out of scope. W302 reports the
  consequence for TODS validation, which is the part that is in scope.
