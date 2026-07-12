# Deep dive — current state as read on 2026-07-01

This is an assessment from reading the code, not from the docs' own claims.
Version at time of reading: 0.6.0 (`pyproject.toml`), clean working tree on
`main`, most recent commits covering mutation testing (#15), SBOM/provenance
(#14), and the research-roadmap implementation pass (#6).

## What this repo is

`tods-validate` is a Python CLI, library, LSP server, GitHub Action, Docker
image, pre-commit hook, and in-browser playground that validates Transit
Operational Data Standard (TODS v2.1.0) feeds — the non-public operational
overlay on GTFS (crew runs, deadheads, vehicle assignments). TODS has no
canonical validator; this project is a deliberate bid to become it, and to be
a credible work sample for the Cal-ITP/MobilityData ecosystem (`CLAUDE.md`
states this candidly).

## Architecture map

The pipeline is small and legible:

- **Load** — `src/tods_validate/loader.py` reads a directory or zip into a
  `Package` of `FeedFile`s (`Row` = 1-based line + `dict[str, str]`).
  Structural defects become `LoadProblem`s rather than exceptions, so one bad
  file cannot hide the rest. Input-safety limits (512 MiB/member, 2 GiB total,
  200:1 compression ratio, path-traversal rejection) live here.
- **Companion view** — `src/tods_validate/gtfs_companion.py` builds
  `CompanionGTFS`: the supplemented GTFS slices (trips, stops, calendars,
  stop_times endpoints, service-date sets) that reference rules resolve
  against. `merge_supplement()` implements the spec's supplement evaluation.
- **Rules** — `src/tods_validate/rules/__init__.py` is a registry of `Rule`
  dataclasses (stable ID, severity, spec citation, `interpretation` field for
  ambiguity calls, `needs_gtfs`, opt-in categories) plus a `@rule` decorator.
  42 rules across five modules: `structure.py` (x1xx), `fields.py` (x2xx),
  `references.py` (x3xx, 805 lines, the largest), `semantics.py` (x4xx),
  `coverage.py` (opt-in x5xx/x6xx).
- **Run** — `src/tods_validate/runner.py` (44 lines) glues loader + companion
  + rules; the CLI (`cli.py`, 676 lines: validate/diff/batch/stats/anonymize/
  fix/merge/rules/lsp) and the test suite both go through it.
- **Report** — `src/tods_validate/report.py` renders text, JSON (schema-
  versioned 1.1.0, `docs/report.schema.json`), Markdown (`--stamp`
  provenance), GitHub annotations, SARIF, and a self-contained accessible
  HTML report. Cluster hints and "path to green" live here.
- **Satellites** — `suggest.py` (auto/review fix suggestions with a strict
  meaning-preservation bar), `fix.py` + `_pkgio.py` (safe mechanical fixes),
  `merge.py` (materialize TODS-Supplemented GTFS), `anonymize.py` (salted
  SHA-256 pseudonyms), `baseline.py`, `stats.py`, `watch.py`, `config.py`
  (TOML + `extends` + profiles), `api.py` (`validate_feed`, semver-promised),
  `testing.py` (`assert_feed_valid` / `assert_feed_produces` pytest helpers),
  `lsp.py` (pygls server with a pure, injectable diagnostic core).
- **Distribution** — `action.yml` (composite Action), `Dockerfile`,
  `.pre-commit-hooks.yaml`, `web/index.html` (Pyodide playground, not yet
  deployed), `editor/vscode/` (unpublished thin LSP client).
- **CI** — `.github/workflows/ci.yml` (ruff, ruff-format, mypy strict, pytest
  ≥90% coverage on a 3.11–3.13 matrix, docs-drift check for the generated
  `docs/rules.md`, i18n N/A gate, Action self-test, and an advisory
  merge→gtfs-validator handoff job); plus `mutation.yml` (weekly advisory
  mutmut on the rules engine), `pypi-publish.yml` (OIDC Trusted Publishing +
  CycloneDX SBOM + SLSA provenance), `release-corpus.yml`, `pages.yml`,
  `docker.yml`. All third-party actions are SHA-pinned.

Tests: 30 modules, 207 test functions (parametrization expands the collected
count; I did not run the suite in this pass, per ground rules). The
conformance contract in `tests/test_conformance.py` enforces exactly one
fixture directory per rule and a zero-finding reference feed.

## What is genuinely strong

1. **The finding is the product, and the code honors that.** Messages across
   all five rule modules consistently name file/row/field and say what good
   looks like; `Rule.interpretation` makes every ambiguity call auditable in
   `rules --format json`; `docs/spec-questions.md` documents eight spec
   ambiguities with the exact permissive reading taken and the rule ID that
   implements it. This is a real moat versus a generic schema checker.
2. **Contracts are taken seriously.** Rule-ID permanence, the JSON report
   schema version with an add-only policy (`report.py`,
   `REPORT_SCHEMA_VERSION`), stable finding ordering as a documented
   guarantee, exit codes 0/1/2, and a published conformance corpus with
   `expectations.json` — this is the posture of a tool that expects other
   tools to build on it.
3. **The one-engine/many-surfaces shape.** CLI, Action, LSP, playground, and
   pytest helpers all call the same `runner.run()` / `validate_feed()`. The
   LSP's diagnostic core is pure and testable without an editor (`lsp.py`,
   `TextReader` injection).
4. **Supply-chain and input-safety work is ahead of most portfolio-stage
   projects**: zip-bomb/traversal limits with tests (`tests/test_loader_safety.py`),
   SHA-pinned actions, OIDC publishing, SBOM + provenance, Dependabot +
   Renovate.
5. **Honesty as a stated behavior**: `stats` explicitly refuses to be a
   quality score; `anonymize` explicitly disclaims anonymity; `--stamp` is
   opt-in because timestamps break reproducibility; the synthetic user
   research is loudly labeled synthetic.

## Structural debt and gaps actually observed

- **The supplement-evaluation logic exists twice.**
  `gtfs_companion.merge_supplement()` (validation view) and
  `merge._merge_file()` (materialized output) independently implement
  PK-match/delete/update/add. They can drift; today nothing proves they
  agree beyond both passing their own tests.
- **Silence about what was not checked.** `Rule.needs_gtfs` silently skips 13
  rules when no companion feed loads, and `references.py`'s TODS-W302 covers
  only run_events' dependencies — a package with `vehicle_assignments.txt`
  but no trips/calendar gets no warning that E205/E311/E312 never ran. A
  green run with no GTFS is indistinguishable in the JSON report from a green
  run with full cross-validation. For a compliance artifact this is the most
  significant honesty gap in the product.
- **Findings are prose-only.** `Finding` (`findings.py`) carries no
  structured parameters (offending value, expected value, referenced ID), so
  the JSON/SARIF consumers, the baseline identity, and any future i18n all
  have to parse English sentences. `render_sarif()` also builds rule
  descriptors from findings alone, dropping the registry's titles,
  descriptions, and spec URLs it already has.
- **Baseline identity is row-number-anchored twice over.**
  `baseline.finding_identity()` = (rule_id, pointer, message); the pointer
  embeds the row number and the message embeds it *again*, so inserting one
  row invalidates every downstream finding's identity. The docstring admits
  it is a heuristic.
- **Per-rule full scans, no shared derived state.** `semantics.py` rebuilds
  its `_Event` list (with `parse_time` on every value) independently in five
  rules; `references.py` re-walks `run_events.txt` per rule. `ValidationContext`
  caches nothing. Fine at fixture scale; untested at the 512 MiB scale the
  loader is willing to accept, and `Row.values` as per-row dicts is a
  memory-heavy representation at that scale.
- **Policy surface is inconsistent across subcommands.** `cli.py`'s
  `validate` resolves config/ignore/profile/baseline; `diff` and `batch`
  resolve none of them (no `--ignore`, no config file, no baseline for
  `batch`), so an agency's house policy silently does not apply in review and
  fleet flows.
- **Cascade noise.** A ragged row (`loader.py` keeps it) is reported by
  TODS-E104 and then again by TODS-E201 for each short cell; nothing links
  effect to cause.
- **Playground gaps.** `web/index.html` loads Pyodide from jsdelivr with no
  SRI hash, installs `tods-validate` unpinned from PyPI (so the page silently
  changes behavior on release), and updates `#status` with plain
  `textContent` — no `aria-live`, so a screen-reader user never hears "Done."
  The HTML report itself is light-scheme-only and has no filtering, which
  will not survive a 10,000-finding real feed.
- **Standards-conformance debt.** No `Makefile`/`make verify` parity (the
  portfolio STANDARDS spine expects it), no committed lockfile, and no
  `docs/RESPONSIBLE-TECH-AUDITS.md` (the portfolio's per-repo audit artifact
  is absent here; also note the roadmap file is lowercase `docs/roadmap.md`
  while sibling repos use `docs/ROADMAP.md`).
- **The composite Action installs from source at run time** (`action.yml`
  pip-installs the checked-out tree, resolving `click` unpinned at each run)
  — slower and weaker supply-chain posture than the GHCR image the project
  already publishes.

## Strategic position inside the portfolio

This is the portfolio's cleanest "standards-infrastructure" play: a small,
dependency-light engine (only `click` at runtime) with unusually mature
contracts, aimed at a young standard whose canonical-validator seat is empty.
Its differentiators — scheduler-language findings, documented interpretation
choices, a published conformance corpus — are exactly the assets that
transfer upstream. Its structural risks are the flip side: everything is
calibrated to synthetic fixtures, the engine has never seen production scale,
and the honesty story has one hole (unreported skipped checks) that matters
precisely because the tool markets itself as a compliance artifact. The
fixes in `02-large-scale-fixes.md` are ordered around closing that gap
between "excellent at fixture scale" and "trustworthy at production scale."
