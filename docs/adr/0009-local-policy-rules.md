# 0009: an agency's own limits are LOCAL- rules, evaluated outside the registry

- Status: proposed (2026-09-11)
- Date: 2026-09-11
- Relates to: #189 (the feature), ADR 0008 (which expected #189 to reuse
  `OPS-`), ADR 0004 (rules as a registry), ADR 0007 (a partial read is not a
  read)

## Context

A labour agreement says how long a run may last, how short a break may be, and
how many days in a row one person may be scheduled. The TODS specification says
none of this and cannot: these are agreements between an agency and its
workforce, and they differ from one agency to the next. Scheduling tools know
them and drop them at export, so a pick that breaks one reaches dispatch
without anything saying so.

#189 asks for those limits as declarative settings in `tods-validate.toml`,
evaluated deterministically, in their own ID namespace and their own band of the
coverage manifest. Its first acceptance criterion is a no-op guarantee: with no
`[policy]` table, the coverage manifest has no local band and every report is
byte-identical to one produced without the feature.

ADR 0008, written the day before #189 was filed, said #189 "should reuse `OPS-`
rather than opening a third namespace." Building it showed that it cannot.

## Decision

### 1. A third namespace, `LOCAL-P0xx`

Three things separate these rules from `OPS-W001`, and any one of them would be
enough.

- **They are not always present.** An `OPS-` rule is registered. It has a
  fixture in the conformance corpus, a row in every coverage manifest, a page in
  the published catalog, and a project default. A local rule has none of those
  unless an agency configures it, and #189's no-op guarantee depends on that.
- **Their severity is the agency's.** The letter after `TODS-` or `OPS-` is the
  rule's severity, and `tests/test_registry.py` holds it to that. A local rule's
  severity is set in the policy table, so an ID that encoded one would be wrong
  for every agency that chose another. The letter here is `P`, for policy, and
  it never changes.
- **They are someone else's judgement.** An `OPS-` finding is this project's
  judgement about what a person can physically do, with a default the project
  chose and defends in ADR 0008. A `LOCAL-` finding is the agency's own rule
  applied to its own schedule. A reader of a report, or of a CAD/AVL ingest
  log, should be able to tell from the ID alone whose rule fired.

Every `LOCAL-` finding ends with the sentence "This is agency policy, not the
TODS specification." Its citation is this ADR, and the renderers label it as a
decision record rather than as the specification.

### 2. Evaluated outside the registry

`src/tods_validate/local_policy.py` holds the six definitions and their checks.
Nothing in it calls `rules.rule`, so nothing in it reaches `REGISTRY`,
`docs/rules.md`, `web/rules/`, the conformance corpus, or `rules.validate`.
`runner.run_with_coverage` calls it after the registry has run, and only when a
policy was loaded. With no policy the function is never entered.

`explain LOCAL-P001` works without a config: it reads the static definitions.
`rules --format json` lists local rules only when a loaded config sets them,
with the severity and limit that config gives.

### 3. Declarative, and every limit names the quantity it limits

| ID | `[policy]` key | limits |
|---|---|---|
| `LOCAL-P001` | `max-run-minutes` | worked time: the time the run's events cover, leaving out declared breaks, with overlapping events counted once |
| `LOCAL-P002` | `max-piece-minutes` | the span of the events that share one `piece_id` within a run |
| `LOCAL-P003` | `min-break-minutes` | the length of each event whose `event_type` is a declared break |
| `LOCAL-P004` | `max-spread-minutes` | the first `start_time` to the last `end_time` of a run, breaks included |
| `LOCAL-P005` | `max-consecutive-days-per-employee` | calendar days in a row on which `employee_run_dates.txt` assigns one employee |
| `LOCAL-P006` | `require-vehicle-assignment-for-revenue-events` | whether each revenue event's block has a vehicle on every day its service operates |

A limit is a whole number greater than zero, or an inline table
`{ limit = 660, severity = "error" }`. The flag is `true`, or
`{ required = true, severity = "error" }`. Keys are kebab-case like every other
key in the file. An unknown key, an impossible limit, a non-integer, or a
boolean where a number belongs is a config error and exits 2, in the same way
ADR 0008's speed ceiling is refused rather than clamped.

`LOCAL-P006` uses the definition of revenue that `stats` and `pickdiff` already
share (an event carrying a `trip_id`) rather than a fourth one. That definition
counts a pull-out that references a deadhead trip as revenue. This rule inherits
the imprecision rather than disagreeing with the two reports beside it; changing
it is a change to all three.

### 4. Breaks are declared, never guessed

`TODS-I601` recognises a break by an `event_type` containing "break", "lunch"
or "meal", and it can afford to because it is advisory. A limit an agency
enforces cannot rest on a guess about the agency's own vocabulary, and the spec
lets a producer name event types freely. So:

- `min-break-minutes` refuses to load without a non-empty `break-event-types`;
- `max-run-minutes` refuses to load without `break-event-types` declared at all,
  where an empty list is a statement that no event type is a break;
- `break-event-types` with neither of those set is refused, because a setting
  that nothing reads is a setting someone believes is doing something.

Types match exactly after trimming spaces. `TODS-I602` exists because one export
can spell a value two ways, and the policy has to list every spelling it means.

### 5. What cannot be measured is reported, never passed

Each configured rule's line in the local band states its denominator, including
when it is zero and why. A run with an untimed event, a run with no `piece_id`,
an employee with an unreadable date, and a revenue event whose block or service
days cannot be resolved are unmeasurable, with the reason. A file that was not
read in full makes every unit that depends on it unmeasurable, for the reason
ADR 0007 gives about the companion feed. `LOCAL-P006` is skipped, and disclosed
as skipped, when there is no companion feed or it has no calendar.

`--require-complete-run` counts a configured local rule that could not run for
want of an input among the checks that could not run.

### 6. Where it applies

`[policy]` is read by `validate`, including `validate --watch`, which is the one
verb that reads `max-implied-speed-kph` today. `diff`, `batch` and the Python API
do not read it. Extending it to `batch` also means deciding what the run-history
ledger stores for a rule outside the registry, which is its own change.

## Consequences

- `docs/report.schema.json` admits `LOCAL-P` IDs and an optional
  `coverage.localPolicy` block. Neither appears in a report without a policy.
- Suggestions stay `TODS-` only. No local finding carries a `suggestion`, and
  `fix` never changes anything because of one.
- The `[severity]` table and `--ignore` do not accept `LOCAL-` IDs, and say
  where the setting lives instead. Severity is set beside the limit.
- `local_policy.py` sits outside `src/tods_validate/rules/`, so it is outside
  the mutated set `docs/mutation-testing.md` describes. That is a consequence of
  keeping it out of the registry, not a reason for it, and adding it to the
  mutated set is a separate decision about the mutation budget.

## Alternatives considered

**Reuse `OPS-`.** Rejected for the three reasons in section 1.

**Register the rules, disabled by default.** Rejected. Every report would then
list six `skipped:disabled` rules that most agencies will never configure,
breaking the no-op guarantee, and each would need a corpus fixture asserting a
threshold nobody chose.

**An expression language.** Rejected, as ADR 0004 rejects plugins: every
expression form is surface to keep stable, and six named limits cover the
issue's users.

**Infer breaks from keywords.** Rejected in section 4.
