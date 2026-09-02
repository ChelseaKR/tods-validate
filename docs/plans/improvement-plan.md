# Improvement plan and running log

Opened 2026-08-28. Working notes for an audit pass whose brief was: read the
open issues and pull requests, produce a v1.0.0 readiness assessment with
evidence, check the validator's own falsifiability rule by rule, fix the real
defects, and name what is blocked.

The readiness assessment is the headline and lives in
[`v1.0.0-readiness.md`](v1.0.0-readiness.md). This file is the plan, the log,
and the provenance.

**Nothing in this pass is committed.** Every change is left unstaged in the
working tree by instruction. This file is the durable record; the working tree
is not.

## Working-tree provenance (read this first)

The checkout this pass ran against is **behind the published `main`**:

| Ref | Commit | Contains |
| --- | --- | --- |
| local `HEAD` / `main` | `a019bbe` | up to #141, `v0.10.0` |
| local `origin/main` | `fed1cf1` | + #142, #150, #151, #152 |
| GitHub `main` (read through the API) | `7a25056` | + #153 |

`git fetch`, `pull`, `checkout` and every other HEAD-moving command were out of
scope for this pass, so the tree could not be advanced. Consequences, and how
they were handled:

- Anything landed in #142/#150/#151/#152/#153 is **absent from this tree** and
  would look like an open defect if audited naively. Every candidate finding
  was therefore re-checked against `git show origin/main:<path>` and, for
  #153, against the GitHub contents API before being called a defect. Two
  fail-opens found during the audit (`spec_watch.py` treating an unrecognised
  document as "in sync"; `check_npm_audit.py` disarming its own cross-check on
  an unparseable report) turned out to be **already fixed on `main` by #151**,
  and are not re-fixed here.
- Fixes are written against `a019bbe`. Files also changed upstream are noted
  per change below, so the merge is not a surprise.
- Three open pull requests (#154 and #155, stacked, and draft #79) were read
  and deliberately not touched. #154/#155 already report `CONFLICTING` against
  `main`; nothing here edits a file they add.

## Issue triage

| Issue | Classification | Note |
| --- | --- | --- |
| #146 playground boots on 0.10.0 | Real, open, human-gated | Needs a browser, an OS and a date recorded against the live page. #150 added `scripts/check-playground-boots.cjs`, which answers most of it mechanically; the dated human record is the remainder. |
| #145 PEP 735 dependency groups | **Already fixed** | Landed in #152, absent from this checkout. Do not re-do; close it against that PR. |
| #144 second advisory rule | Aspiration, correctly parked | `good first issue`, needs a spec citation chosen and defended. Does not block v1.0.0. |
| #143 structure warning for a recognized-but-unexpected file | Aspiration, correctly parked | Same shape as #144. |
| #76 production-feed feedback | Real, open, gated on people | Named in the multiyear plan as standing work with no owner and no date, which is the honest state. |
| #74 VoiceOver walkthrough | Real, open, gated on people | Was blocked by the stale playground pin; #142 removed that blocker, so it is workable now but still needs a human with assistive technology. |

Two issue texts did not survive checking. #145's body describes work that is
done. #146's premise ("this has never been confirmed end to end") predates
#150, which now boots the live page in a real browser and asserts a finding
renders; what remains is narrower than the issue says.

## The plan, ranked by value

Ranked by "what would be worst to ship at v1.0.0", not by effort.

| Phase | Item | State |
| --- | --- | --- |
| 1 | Falsifiability census: enumerate every rule by AST, prove each fires, prove none fires on a clean feed, prove each finding is caused by its own check | **Done** |
| 2 | The secret-scan gate cannot see the working tree | **Done** |
| 3 | The published package ships no type information | **Done** |
| 4 | The perf gate's failure is unreachable from below | **Done** |
| 5 | `mypy` does not cover the scripts that are the gates | **Done** |
| 6 | The README claims a flag that does not exist, under a conformance assertion | **Done** |
| 7 | `make verify` green on a tree CI would reject | **Done** |
| 8 | Two v1-contract exports exercised by no test | **Done** |
| 9 | API docs incomplete, and half of them outside the currency gate | **Done** |
| 9b | A rule threshold no test exercised at its boundary | **Done** |
| 10 | The v1.0.0 readiness assessment itself | **Done** |
| 11 | Branch ruleset, PyPI environment, upstream PR #156, a conformance-only release | **Blocked, named** |

Phase 11 is the whole of what is left, and none of it is code in this
repository.

## Change log, file by file

Every fix below was broken and restored, and both directions were observed.
Logs are under `/private/tmp/tods-audit/`.

### `Makefile`

Two changes.

**`secrets` recipe.** Was one line, `gitleaks detect --source . --redact
--exit-code 1`, under a comment claiming "working tree + history". `gitleaks
detect --source .` walks commits and is blind to an uncommitted file. Measured
on this repository with a root-level file holding an AWS key pair, a GitHub
PAT and a Slack bot token, never added to the index:

| Command | Result |
| --- | --- |
| `gitleaks detect --source .` (the gate as it was) | `283 commits scanned` / `no leaks found`, **exit 0** |
| `gitleaks detect --no-git --source .` | `leaks found: 1`, **exit 1** |
| `--no-git` on the clean tree | `no leaks found`, exit 0 |

It now runs both, each reporting its own PASS/FAIL, neither able to
short-circuit the other, for the same reason `verify` does not stop at its
first failing gate. `make secrets` on a tree with the planted file: **exit 2,
"gitleaks working tree: FAIL"**. On the clean tree: **exit 0, both PASS**.

**Header.** It enumerated CI-only work as "the composite action's self-test,
CodeQL, Semgrep and zizmor" and omitted two `pull_request` jobs with no `make`
equivalent: `perf`, and the VS Code extension `package` job (path-filtered to
`editor/vscode/**`, which is why it went unnoticed). Both are named now, and
the paragraph is checked against the workflows.

Upstream note: identical at `origin/main`, so both hunks apply cleanly.

### `.gitleaks.toml` (new)

Scopes the working-tree scan away from `.venv/`, `node_modules/` and build
caches. Not cosmetic: `.github/workflows/verify.yml` runs `uv sync` and
`npm ci` before `make verify`, so without this the release gate scans about
29 MB of third-party code whose test fixtures are a standing source of
findings this project cannot fix. Measured: 28.74 MB in 2.34s without it,
2.12 MB in 0.30s with it, same verdict on the planted secret.

### `tests/test_secret_scan_gate.py` (new)

Five tests. Two read the recipe and always run, so deleting the working-tree
half goes red in every job that runs pytest. Two drive the real binary against
a planted secret and against a clean control (the control matters: a scanner
that failed on everything would satisfy the first without it). One checks that
the `.gitleaks.toml` allowlist covers only dependencies and build output, so it
cannot become a way to stop scanning `src/`.

Break: against the pre-fix one-line recipe, **2 failed, 3 passed**. Restore:
**5 passed**.

The planted values are assembled from string fragments rather than written out
whole. Written as literals, the file was itself a finding: `make secrets`
reported `leaks found: 1` against `tests/test_secret_scan_gate.py:39`. The
honest answer to that is an inert file, not an allowlist entry exempting the
file that exists to defend the scan.

### `src/tods_validate/py.typed` (new) and `tests/test_typing_marker.py` (new)

The package had no PEP 561 marker, here or on `main`. `mypy --strict` runs over
`src/` on every pull request and the v1 contract reserves stability guarantees
for the public exports, and neither reached a caller: a five-line consumer
importing `validate_feed` got

```
error: Skipping analyzing "tods_validate": module is installed, but missing
library stubs or py.typed marker  [import-untyped]
```

exit 1, and with the marker "Success: no issues found", exit 0. Confirmed the
file ships: `uv build --wheel` produces a wheel containing
`tods_validate/py.typed`.

Break: with the marker removed, **all three tests fail**. Restore: **3 passed**.

### `pyproject.toml` and `scripts/spec_watch.py`

`[tool.mypy] files = ["src"]` became `["src", "scripts"]`. `ruff check src
tests scripts` already covered the scripts; `mypy` did not, so the
merge-blocking gates (`check_public_contract.py`, `check_npm_audit.py`,
`generate_rules_doc.py`, `spec_watch.py`) were the least verified code in the
repository. 34 files checked became 44.

This only became cheap once `py.typed` existed: 16 of the 17 errors were
`import-untyped` against the package's own modules. The seventeenth was real
and is fixed in `spec_watch.py`, where `resp.read().decode("utf-8")` returns
`Any`, so the function's `-> str` was a promise mypy had never checked.

Break: with the annotation reverted, `make typecheck` **exit 2**, one error.
Restore: **exit 0, 44 files**.

Upstream note: the same construct is at `origin/main:scripts/spec_watch.py`
line 159, in a file #151 changed heavily; expect to re-apply this one-line hunk
by hand.

### `scripts/check_perf_budget.py` and `tests/test_perf_budget.py`

The gate measured `rows / cpu` where `rows = trips * 2`, an **assumed**
constant, and discarded the result of the timed `run(feed)` entirely. A
throughput budget can only fire on slowness, so doing less work makes it
greener: a validator that had quietly stopped reading the feed would burn
almost no CPU, report an enormous rate, and pass further inside the budget than
a correct one. Its failure was unreachable from below. Nothing noticed, because
every existing test stubs `measure` out.

Now each repetition counts the rows the loader actually parsed, refuses to
report a rate below the floor the generator writes, and refuses when two
repetitions of the same feed disagree about the count. The rate's *denominator*
is deliberately left as the fixed unit of work: the real count is about 10%
higher (110,101 rows for 50,000 trips, not 100,000), and switching would raise
every published number by that margin and make the committed baseline look like
a speedup nobody made.

Also bounded `maxRegressionFactor`, which was read unbounded from the same data
file as the baseline. A large enough value there does not loosen the gate, it
retires it, and retiring a gate belongs in a reviewed change rather than a data
edit.

Break: with the three guards removed, **5 tests fail**. Restore: **17 passed**.
End to end on a real 300-trip feed: `761 rows parsed`, within budget, exit 0.

### `README.md`, `docs/CONFORMANCE-GAPS.md`, `tests/test_readme_claims.py` (new)

The README declared `Observability: Tier C ... Opt-in --log-format json only`
and, two paragraphs later, asserted conformance with that tier in the Standards
Conformance table. `--log-format` exists nowhere in `src/`, and no row in the
gaps ledger recorded that. `OBSERVABILITY-STANDARD.md` section 3 defines Tier C
as "an opt-in `--log-format json` flag backed by `structlog`".

Nothing under `src/` imports `logging` at all, so there is no stream for such a
flag to format. The section now says that, links the new
`CONFORMANCE-GAPS.md#observability` row, and the row sets out both ways to
close it (restate the tier, or add `structlog` as a second runtime dependency
to a tool that deliberately has one) without picking.

The durable half is the test: every `--flag` the README names must exist in the
CLI, unless it is another program's flag (three entries, each attributed) or is
recorded as documented-absent (one entry) **and** linked to the gap that tracks
it. Both allowlists are themselves checked for dead entries.

Break, against the README and ledger exactly as at `HEAD`: **2 failed**.
Restore: **5 passed**.

Two smaller README corrections in the same pass: "16 reference checks" became
"the 16 checks that read GTFS files" (6 of the 16 are field, semantic or
coverage rules), and the `ingest-ready` paragraph now says it currently
resolves to the same settings as `strict`, which it does, byte for byte.

### `tests/test_ci_gate_parity.py` (new)

Pins the Makefile header's promise against the workflows: every job in a
`pull_request` workflow either runs a `make verify` gate or is named in the
header as something CI does on its own.

Two parser bugs were found and fixed while writing it, both of the kind the
test exists to catch. Slicing job bodies with `str.index` over the whole file
resolved a job id to an earlier occurrence, so one job's body ran on into the
next. And a job's slice ends where the *next* job's leading comment block
begins, so the `perf` job looked as though it ran `make a11y`, because the
paragraph introducing the accessibility job says so. A check that matched prose
instead of commands would have passed while measuring nothing.

Break, against the header as it was: **`vscode-extension.yml:package` and
`ci.yml:perf` reported**. Restore: **3 passed**.

### `tests/test_contract_surface.py` (new)

`tods_validate.read.to_dataframe` and `tods_validate.__version__` are in
`docs/v1-contract-candidate.json` and were named in **none** of the 52 existing
test modules. A 90% line-coverage floor cannot see an export nothing imports.

Both are covered now. `to_dataframe` gets its documented no-pandas
`ImportError` (pandas is deliberately not a dev dependency, so that was the
path most callers would hit first and the one nothing checked), plus a
happy-path test through a stub module. `__version__` is pinned to
`pyproject.toml` and asserted not to be the `0.0.0+unknown` fallback.

Underneath both, a floor: every contract export must be named somewhere in the
suite. Pointed at the 52 pre-existing modules it returns exactly
`tods_validate.__version__` and `tods_validate.read.to_dataframe`.

### `docs/api.md`, `docs/read-api.md`, `scripts/check_doc_currency.py`, `tests/test_doc_currency.py`

`docs/api.md` described `Finding` as 7 fields and 2 helpers. It has 10 fields
and 3 helpers, and `report.schema.json` **requires** the three it omitted
(`data`, `caused_by`, `severity_original`) and `fingerprint()`, which is the
identity `--baseline` matches on. Re-verified field by field and re-stamped;
the old stamp said "against tods-validate 0.8.0" on a 0.10.0 tree, which the
gate could not have caught because it hashes content rather than comparing
versions.

`docs/read-api.md` documents 10 of the 19 contract names and carried no
currency stamp, so `make docs-check` had nothing to fail on when it drifted.
Added to `STAMPED`, with `FeedFile.readable` and `LoadProblem` documented (both
public, both previously absent; `problems` was documented without its element
type, which left the field unusable from the page alone).

`tests/test_doc_currency.py` parametrized over a hand-written list of two
paths. It now derives from the checker's own `STAMPED`, plus an assertion that
the list is not empty, because a parametrize over an empty list reports success
without running.

Break: appending one line to `read-api.md` gives `check_doc_currency.py`
**exit 1**, naming the file and the new hash. Restore: **exit 0, three files
current**.

### `tests/test_coverage_advisory.py`

`TODS-I601` flags a run spanning more than `_LONG_SPAN_SECONDS = 6 * 3600`
with no break event. Its fixture spans eight hours, which proves the rule
fires and says nothing about where the bound is. Demonstrated: moving the
constant from six hours to seven left the conformance test for `TODS-I601`
**passing, exit 0**. Two runs one second apart now sit either side of the
boundary; against the same seven-hour bound they **both fail**. Restored:
10 passed.

The pair also asserts the constant's current value, so moving the bound has to
move both sides deliberately rather than turning one of them red by accident.

### `.github/workflows/ci.yml`

Comment only. The `secrets` job described itself as scanning "the PR/push diff
and full history"; it now describes both scans and why neither substitutes for
the other.

## Verification

```
make verify < /dev/null; echo "EXIT=$?"
```

`EXIT=0`. 13 of 13 gates PASS. 701 tests (from 664), coverage 91.80% against a
90% floor. Full log: `/private/tmp/tods-audit/20260828T1710-verify-final.log`.

The AST rule census and the falsifiability harness were re-run after every
change: still 43 registered, 43 emitted, 0 non-literal emission sites, and 43
of 43 rules firing on their own fixture, silent on the valid feed, and silent
when their check is neutered.

`.venv/bin` must be on `PATH`, which is what CI does (`ci.yml` writes it to
`$GITHUB_PATH`). Without it six gates fail for environment reasons on a laptop.
That is not a repository defect, but it is a sharp edge for a new contributor,
because `CONTRIBUTING.md`'s local instructions and CI's `PATH` step describe
two different setups.

## Left undone, and why

- **`--log-format json`** (Observability Tier C). Not implemented. Adding
  `structlog` as a second runtime dependency to a tool that deliberately has
  one, in order to format log records that do not exist, is a product decision
  and not a remediation. Recorded as a gap with both options written out.
- **The branch ruleset and the PyPI environment.** Live settings, inspected
  read-only. See `v1.0.0-readiness.md` section C7 for what is actually there
  and why the committed payload should be diffed against the live export
  before anyone applies it.
- **Deleting the `v0` tag.** It is a lightweight tag pointing at the v0.5.0
  release commit, so `ChelseaKR/tods-validate@v0` resolves to v0.5.0 today.
  Deleting a published ref is a live action; the gaps ledger already records
  it and the two commands.
- **`tests/` under `mypy`.** Out of scope for this pass; `scripts/` was the
  half that gates merges.
- **`docs/rulesets/main.json` corrections.** The file does not exist in this
  checkout (it arrived with #152), so editing it here would have created a
  conflicting duplicate. The divergence is written up in
  `v1.0.0-readiness.md` section C7 instead.
- **Any new or changed TODS rule.** None was touched, so no spec text needed
  citing. That is deliberate: #143 and #144 both need a citation chosen and
  defended, and inventing one to close an issue would be the exact failure
  this validator exists to refuse.

## Status log

- 2026-08-28: pass opened; issues, pull requests, roadmap and multiyear plan
  read.
- 2026-08-28: baseline `make verify` recorded (green with `.venv` on `PATH`;
  664 tests, 91.71%).
- 2026-08-28: AST rule census and falsifiability census run; 43 of 43 clean.
- 2026-08-28: phases 2 to 9 executed, each broken and restored.
- 2026-08-28: `make verify` green, 701 tests, 91.80%. Readiness assessment
  written. Phase 11 remains blocked on people.
