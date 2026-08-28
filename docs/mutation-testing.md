# Mutation testing (advisory)

Line coverage tells you which code ran during the tests. It does not tell you
whether the tests would notice if that code were wrong. Mutation testing fills
that gap: it makes small edits to the source (a `<` becomes `<=`, an `and`
becomes `or`, a constant changes) and reruns the suite. A mutant that the tests
still pass is a *survivor* — a change to behaviour that no test caught.

This is run with [mutmut](https://github.com/boxed/mutmut) and scoped to the
validation rules engine (`src/tods_validate/rules/`), the code that decides
which TODS-E/W/I findings a feed produces. It is **advisory**. It is not part of
the CI gate and never blocks a pull request. The gate stays
`ruff` + `mypy` + `pytest --cov-fail-under=90` +
`generate_rules_doc.py --check`.

## Baseline

Measured on the rules engine (`src/tods_validate/rules/*`):

| Metric | Value |
| --- | --- |
| Mutants generated | 280 |
| Killed | 181 |
| Survived | 99 |
| Mutation score | ~65% |

The score is a signal to read, not a target to chase. Many survivors are
effectively equivalent mutants (see below), so 100% is neither reachable nor
the goal. The number to watch is a sudden drop, which means a test stopped
pinning down behaviour it used to pin down.

## What gets mutated, and what does not

mutmut 3 does not mutate functions that carry a decorator: a decorator runs at
definition time, and mutmut's rewrite would re-execute it (see
`mutmut/mutation/file_mutation.py`). Every check in the rules engine is
registered with the `@rule(...)` decorator, so the **check bodies themselves are
not mutated**. What *is* mutated is the un-decorated engine underneath them:

- the parsing and validation helpers (`_is_valid_date`, `_required_fields`),
- the reference-resolution helpers (`_run_pairs`, `_uses_trip_ids`,
  `_trips_available`, `_calendar_available`, `_supplement_groups`, ...),
- the registry dispatch (`rule`, `_is_enabled`, `validate`).

`parse_time` and the run-event model builders (`_Event`, `parse_events`,
`events_by_run`) moved to `src/tods_validate/run_events.py` as part of FIX-03
(cached once per validation on `ValidationContext` instead of re-derived per
rule call — see `docs/ideation/02-large-scale-fixes.md`). That module sits
outside `src/tods_validate/rules/`, so it is outside `only_mutate` and no
longer part of this mutation run at all.

These are where a silent bug would let an invalid feed pass or flag a valid one,
so they are worth pinning down. The check bodies stay covered the usual way: the
line-coverage gate plus the repo's convention of a passing and a failing fixture
per rule.

## Notable survivors, and what was done

Two high-value survivors from the first run were killed by adding one targeted
test each (kept in the passing/failing fixture style the rest of the suite
uses):

- **`_is_valid_date`: `and` → `or`.** An eight-digit string that is not a real
  date (for example `20260231`, February 31st) passes the `YYYYMMDD` regex but
  fails the calendar check. With `or` the calendar check no longer mattered and
  a bogus date validated clean. Killed by
  `tests/test_fields.py::test_impossible_calendar_date_is_flagged`.
- **`_uses_trip_ids` forced to always return `False`.** This helper decides
  whether TODS-W302 warns that the companion GTFS has no `trips.txt` when run
  events reference trips. Neutralised, the warning disappeared silently. Killed
  by
  `tests/test_references.py::test_trip_reference_without_companion_trips_warns_w302`.

Remaining survivors are mostly two kinds, both low value:

- **Dead defaults.** `row.values.get("service_id", "")` mutated to a different
  default. The fixtures always declare the column, so the default is never
  reached; these are equivalent mutants.
- **Under-exercised fallback branches**, such as `_calendar_available`
  resolving through `calendar_supplement.txt` when the fixtures supply
  `calendar.txt` directly.

## Running it

Mutation testing is not installed by the default `dev` extra. Install it on
demand:

```sh
pip install -e . --group mutation
mutmut run          # generate and test mutants (a few minutes)
mutmut results      # list survivors
mutmut show <id>    # see the exact source change for one survivor
```

Configuration lives in `pyproject.toml` under `[tool.mutmut]`: the whole package
is copied so imports resolve, only `src/tods_validate/rules/*` is mutated, and
the rule test modules drive the mutants. mutmut writes its working copy to
`mutants/` (git-ignored); delete it to force a clean run.
