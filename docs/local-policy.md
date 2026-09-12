# Local policy: an agency's own operational limits

The TODS specification describes what a pick contains. It does not say how long
a run may last, how short a break may be, or how many days in a row one person
may be scheduled, because those are agreements between an agency and its
workforce and they differ from one agency to the next. `tods-validate` can check
a pick against them once the agency writes them down, in a `[policy]` table in
`tods-validate.toml`.

These checks carry `LOCAL-` IDs. They run only when a `[policy]` table sets
them, and every finding they produce ends with the sentence "This is agency
policy, not the TODS specification." Without a `[policy]` table nothing about
a run changes. [ADR 0009](adr/0009-local-policy-rules.md) records the design.

## An example

```toml
[policy]
max-run-minutes = 600
max-piece-minutes = 120
min-break-minutes = { limit = 30, severity = "error" }
max-spread-minutes = 300
max-consecutive-days-per-employee = 6
break-event-types = ["Break"]
```

With that file in the working directory, validating the project's own valid
fixture (`tods-validate tests/fixtures/valid/tods --gtfs tests/fixtures/valid/gtfs`)
reports:

```text
2 warnings:
  WARNING LOCAL-P002 [run_events.txt, row 6, field 'end_time']
    run_events.txt row 6: piece '10000-1' of run (service_id 'daily', run_id '10000') lasts 2h05m, from 09:45:00 (row 4) to 11:50:00. The agency's policy sets max-piece-minutes = 120 (2h00m), measured over the events that share this piece_id. This is agency policy, not the TODS specification.
  WARNING LOCAL-P004 [run_events.txt, row 10, field 'end_time']
    run_events.txt row 10: run (service_id 'daily', run_id '10000') spreads 5h30m, from 09:30:00 (row 2) to 15:00:00 (row 10). The agency's policy sets max-spread-minutes = 300 (5h00m), measured from the earliest start_time to the latest end_time in the run. This is agency policy, not the TODS specification.

By rule: LOCAL-P002 ×1, LOCAL-P004 ×1
Summary: 0 error(s), 2 warning(s), 0 info.
Rule-set coverage: 41 of 46 checks ran. Checks skipped: 5 opt-in rule not enabled (use --enable).
  Not run, opt-in rule not enabled (use --enable) (1 WARNING, 4 INFO): TODS-I501, TODS-I502, TODS-I601, TODS-I602, OPS-W001
  Local policy (agency thresholds, not the TODS specification): 5 of 5 ran.
  LOCAL-P001 (max-run-minutes = 600): 2 runs measured.
  LOCAL-P002 (max-piece-minutes = 120): 1 of 2 runs measured; 1 unmeasurable (no event in the run carries a piece_id, so it cannot be divided into pieces).
  LOCAL-P003 (min-break-minutes = 30): 1 break event measured.
  LOCAL-P004 (max-spread-minutes = 300): 2 runs measured.
  LOCAL-P005 (max-consecutive-days-per-employee = 6): 3 employees measured.
```

The coverage lines above the local band are unchanged by the policy. They
describe the rule set this project ships; the band below them describes the
agency's, and states for every setting how much of the pick it was able to
measure.

## The settings

| Setting | ID | What is limited |
|---|---|---|
| `max-run-minutes` | `LOCAL-P001` | Worked time: the time a run's events cover, leaving out events whose `event_type` is a declared break, with overlapping events counted once. The finding points at the event during which the total passes the limit. |
| `max-piece-minutes` | `LOCAL-P002` | The span of the events that share one `piece_id` within a run. An event with no `piece_id` belongs to no piece. |
| `min-break-minutes` | `LOCAL-P003` | The length of each event whose `event_type` is a declared break. A run with no break is not a finding here; `TODS-I601` is the advisory for that. |
| `max-spread-minutes` | `LOCAL-P004` | From a run's earliest `start_time` to its latest `end_time`, breaks included. |
| `max-consecutive-days-per-employee` | `LOCAL-P005` | Calendar days in a row on which `employee_run_dates.txt` assigns one employee. |
| `require-vehicle-assignment-for-revenue-events` | `LOCAL-P006` | Whether each revenue event's block has a `vehicle_assignments.txt` row on every day its trip's service operates. |

A limit is a whole number greater than zero. To set a severity, write it as a
table: `max-spread-minutes = { limit = 780, severity = "error" }`. Severity is
`warning` when it is not given. The last setting is `true` or `false`, or
`{ required = true, severity = "error" }`. In a file that `extends` a shared
policy, `false` switches off a `true` the shared file set.

Anything else is a configuration error and stops the run with exit code 2: an
unknown setting (a snake_case spelling of a real one gets a "did you mean"),
a limit of zero or less, a fraction, a boolean where a number belongs, or an
unknown severity. A limit is refused rather than adjusted, because a run that
quietly checked a different limit from the one written down would still look
as though the agency's rule had been applied.

**Revenue** in `LOCAL-P006` means an event that carries a `trip_id`, which is
the definition `stats` and `pickdiff` already use, so the three agree about
which events are revenue. Its block is the event's own `block_id` or else its
trip's block in the companion `trips.txt`, and the days it operates are the
days its trip's service runs in the supplemented calendars. A vehicle is
assigned to a block under the service its trips run on, so a supervisor's run
under one service that rides a trip under another is checked against the
trip's service. It needs the companion GTFS feed and a calendar; without them
it is reported as not run, never as passed.

## Breaks are declared, never guessed

The spec lets a producer name event types freely, so the policy has to say
which ones are breaks:

- `min-break-minutes` needs a non-empty `break-event-types`.
- `max-run-minutes` needs `break-event-types` declared at all. Write
  `break-event-types = []` if none of your event types is a break.
- `break-event-types` with neither of those set is refused, because it would do
  nothing.

Types match exactly after spaces are trimmed. If an export writes "Break" in
one place and "break" in another (`TODS-I602` reports that), list both.

## What cannot be measured

A limit checked against part of a pick is a pass nobody earned, so these are
counted as unmeasurable, with the reason, and never as having passed:

- a run with an event whose `start_time` or `end_time` does not parse, or that
  ends before it starts;
- a run with no `piece_id` at all, for `max-piece-minutes`;
- an employee with an unreadable date, for `max-consecutive-days-per-employee`,
  since the missing day could join two short streaks into a long one;
- a revenue event whose trip, block or operating days cannot be resolved, or
  whose block has an assignment row with an unreadable date;
- every unit in a file that was not read in full.

When there is nothing to measure at all, the line says so, for example
`LOCAL-P004 (max-spread-minutes = 600): 0 runs measured (the package has no
run_events.txt).`

`--require-complete-run` counts a configured local rule that could not run for
want of an input among the checks that could not run.

## Severity, `--ignore` and `[severity]`

A local rule's severity is set beside its limit. The `[severity]` table and
`--ignore` refuse `LOCAL-` IDs and say where the setting lives instead: to stop
checking a limit, remove it from the `[policy]` table. `--enable` does not turn
local rules on either; the setting does. A finding at `error` severity fails
the run like any other error; `--fail-on warning` makes `warning` fail it too.

Local findings never carry a fix suggestion. A policy finding is a scheduling
decision to revisit, and nothing here knows what the right schedule is.

## Where it applies

`validate` reads `[policy]`, including `validate --watch`.
`tods-validate explain LOCAL-P001` describes any local rule without a config.
`tods-validate rules --format json` lists local rules after the registry when a
config sets them, with the limit and severity it gives (`--config` names a file;
otherwise `tods-validate.toml` in the working directory is read).

`diff`, `batch` and the Python API do not read `[policy]` yet.

In the JSON report, local rules appear under `coverage.localPolicy`, beside
rather than inside the totals for the project's rule set, and only when a
policy was loaded. `docs/report.schema.json` describes the block.
