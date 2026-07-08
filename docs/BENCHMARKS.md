# Throughput benchmarks

`scripts/benchmark.py` generates a synthetic TODS+GTFS feed and times a single
validation pass over it, so regressions in the validation path (and the effect
of new rules) are visible as a rows/second number instead of a vague "it feels
slower."

## Methodology

`build_feed(directory, trips)` writes a self-consistent synthetic feed: one
`calendar.txt` service, 100 stops, `trips` trips (`trips.txt`), one run event
per trip plus its paired deadhead in `run_events.txt`, and a vehicle +
assignment per block (`blocks = max(1, trips // 10)`). The feed exercises
every rule band; the point of the benchmark is throughput, not whether the
feed is clean.

`total_rows` is defined as `trips * 2` — `trips.txt` rows plus `run_events.txt`
rows are what dominates the row count as `trips` scales, so that sum is the
denominator for the throughput figure. `stops.txt`, `vehicles.txt`, and
`vehicle_assignments.txt` stay small or scale with `blocks` (`trips // 10`),
not `trips`, so they're not counted.

The run is single-threaded: `runner.run(feed)` is called once and wrapped in
`time.perf_counter()`. There's no warm-up iteration and no averaging across
repeated runs — the number reported is one cold run per scale. `findings` is
the count of results the run produced (informational only; it is not part of
the throughput calculation).

Invocation:

```
.venv/bin/python scripts/benchmark.py --trips <N>
```

## Environment

- Machine: Apple M1 Pro (arm64), Darwin 25.4.0
- Python: 3.12.13
- Package installed editable (`pip install -e .`) from a clean checkout, no
  optional extras

## Results

| trips | rows (trips × 2) | elapsed (s) | throughput (rows/s) |
| ---: | ---: | ---: | ---: |
| 1,000 | 2,000 | 0.04 | 54,478 |
| 10,000 | 20,000 | 0.38 | 52,924 |
| 50,000 | 100,000 | 2.54 | 39,320 |
| 100,000 | 200,000 | 6.42 | 31,129 |

Raw output for the three published scales:

```
$ .venv/bin/python scripts/benchmark.py --trips 10000
trips:           10000
findings:        20000
elapsed:         0.38s
throughput:      52,924 rows/s

$ .venv/bin/python scripts/benchmark.py --trips 50000
trips:           50000
findings:        100000
elapsed:         2.54s
throughput:      39,320 rows/s

$ .venv/bin/python scripts/benchmark.py --trips 100000
trips:           100000
findings:        200000
elapsed:         6.42s
throughput:      31,129 rows/s
```

## Reading the numbers

Throughput drops as `trips` grows (roughly 54k rows/s at 1k trips down to
~31k rows/s at 100k trips) rather than holding flat, which points to
super-linear cost somewhere in the validation path (rule checks that scan
already-seen rows, cross-referencing that isn't indexed, etc.) rather than a
fixed per-run overhead. That's a profiling lead for future work, not
something this pass investigates further — the goal here is a published,
repeatable baseline to catch regressions against, not a performance
optimization.

## Reproducing

```
.venv/bin/python scripts/benchmark.py --trips 1000
.venv/bin/python scripts/benchmark.py --trips 10000
.venv/bin/python scripts/benchmark.py --trips 50000
.venv/bin/python scripts/benchmark.py --trips 100000
```

Numbers will vary by machine; re-run and update this table when the
validation path changes materially (new rules, changed data structures) so
regressions show up as a diff against a real baseline instead of folklore.
