# Roadmap

Planned direction for tods-validate. Dates are intentions, not promises;
items move earlier when users ask for them. Feedback and feature requests
are welcome as GitHub issues.

## v0.2.0 — Suppression and reporting (shipped 2026-06-12)

- `--ignore TODS-Wxxx` (repeatable) and a `tods-validate.toml` config file so
  agencies can encode local policy and run the validator in CI without
  fighting warnings they have decided to accept.
- `--format markdown`: a report suitable for pasting into an issue or a
  working-group thread.
- Real-feed validation is an ongoing maintainer practice. Private feed data is
  never committed; observed failures are reduced to reviewable regression
  fixtures. See `docs/production-feed-validation.md`.

## v0.3.0 — The merge pipeline (shipped 2026-06-12)

- `tods-validate merge feed/ -o supplemented.zip`: materialize the
  "TODS-Supplemented GTFS" the spec describes, so the result can be checked
  with MobilityData's gtfs-validator. The spec says the merged dataset should
  form a valid GTFS feed; this makes that property testable.
- Supplement-internal reference checks (for example,
  `stop_times_supplement.txt:trip_id` resolving against supplemented trips).
- A documented CI recipe chaining merge and gtfs-validator.

## v0.4.0 — Distribution and analysis surfaces (shipped 2026-06-20)

- Docker image on GHCR for CI environments without Python.
- `tods-validate rules` (text and JSON, with category and interpretation
  metadata) and a published JSON Schema for the report format, so dashboards
  can consume findings without scraping text.
- A pre-commit hook definition.
- `scripts/benchmark.py` for throughput on large synthetic feeds, and
  `scripts/check_perf_budget.py`, which turns that measurement into a CI gate
  against `perf/baseline.json`.
- SARIF and HTML report formats; richer text/Markdown (by-rule grouping,
  root-cause hints, path-to-green).
- `diff`, `batch`, `stats`, and `anonymize` subcommands; a `merge` manifest.
- Opt-in coverage (TODS-I50x) and advisory (TODS-I60x) rules via `--enable`.
- A public Python API (`validate_feed`), `--baseline`, `--profile`, config
  `extends`, and input-safety hardening (SECURITY.md).

## v0.5.0 — Spec tracking

- `--spec-version 1.0.0` validates against TODS as it stood before
  v2.0.0-alpha.1: five files, no Supplement mechanism, a differently-shaped
  `run_events.txt`. Done; see `docs/spec-versions.md` for the file/field
  delta and exactly which rule bands run under each version.
- Validation for spec additions as they are adopted upstream (the spec
  repository currently has open proposals for rosters, runtimes, and
  electrification files such as chargers and energy consumption). Researched
  but deliberately not implemented: as of 2026-07, rosters (#45), runtimes
  (#42/#43), and chargers (#46) are all still open, unmerged proposals —
  chargers dormant since 2023-12, the others last substantively discussed
  2024-08 with real field-level disagreements still unresolved. See
  `docs/research/E1-upstream-spec-state.md` for the cited current state of
  each and why `--enable experimental` support would be premature.
- Offering this project's fixture feeds upstream as a conformance suite. The
  corpus and governance hand-off are proposed in
  [MobilityData issue #153](https://github.com/MobilityData/transit-operational-data-standard/issues/153);
  it remains downstream and validator-specific unless the TODS Board adopts it.

## v1.0.0 — Stability commitments

Access to real feeds is no longer blocked; the maintainer's privacy-preserving
record is in `docs/production-feed-validation.md`. The remaining gate is one
conformance-only release with no unreviewed drift against
`docs/v1-contract-candidate.json`, while every real-feed defect is reduced to
a reviewable regression case. v1.0 means semantic-versioning guarantees on
rule IDs, exit codes, the public Python exports, and the JSON report schema,
plus the acceptance-test corpus in CI.

## Out of scope

Validating GTFS itself (use
[gtfs-validator](https://github.com/MobilityData/gtfs-validator)),
GTFS-realtime correlation, and feed editing or repair beyond the merge
described above.

## Metrics ledger

Per `docs/standards/QUALITY-AND-METRICS-STANDARD.md`'s per-repo Metrics
table: project-specific values here, rigor cited to the owning standard.
Updated 2026-07-05.

| Metric | Target | Measured by | Gate | Owner |
|---|---|---|---|---|
| Line + branch coverage | ≥ 90% (published library) | `pytest --cov --cov-branch` in CI | AUTO | Chelsea Kelly-Reif |
| Cyclomatic complexity | ≤ 10 | `ruff` `C901`/mccabe | AUTO | Chelsea Kelly-Reif |
| SHA-pinned `uses:` | 100% | manual + `zizmor` | AUTO | Chelsea Kelly-Reif |
| Workflow SAST findings (High/Critical) | 0 | `zizmor --min-severity high` | AUTO | Chelsea Kelly-Reif |
| SAST findings (blocking) | 0 | Semgrep `ci --config auto`, CodeQL | AUTO | Chelsea Kelly-Reif |
| Dependency vulnerabilities (fixable) | 0 | `pip-audit --strict` | AUTO | Chelsea Kelly-Reif |
| Secrets in tree/history | 0 | gitleaks (pre-commit + CI) | AUTO | Chelsea Kelly-Reif |
| Container CVEs (CRITICAL/HIGH) | 0 | Trivy in `docker.yml` | AUTO | Chelsea Kelly-Reif |
| Rule ↔ fixture parity | 1:1 | `tests/test_conformance.py` | AUTO | Chelsea Kelly-Reif |
| Mutation kill-rate (rules engine) | ≥ 70% (ratchet; baseline ~65%) | `mutmut` (advisory, weekly) | REVIEW | Chelsea Kelly-Reif |
| axe/pa11y violations (HTML report + playground) | 0 | `make a11y` (axe + HTML_CodeSniffer, WCAG 2.1 AA) | AUTO | Chelsea Kelly-Reif |
| Perf regression budget | ≤ 2x baseline (rows per CPU-second) | `make perf-check` (`perf` job in `ci.yml`) vs `perf/baseline.json` | AUTO | Chelsea Kelly-Reif |
| Screen-reader walkthrough | per release | not yet committed as an artifact | REVIEW-not-yet-built | Chelsea Kelly-Reif |
| Threat model | per new surface | `SECURITY.md`, updated ad hoc | REVIEW | Chelsea Kelly-Reif |

Rows marked "not-yet-built" are honest gaps, not silent omissions; see
`docs/CONFORMANCE-GAPS.md` for the open item each maps to.

## Release checklist (QM-17)

Run through before creating a GitHub release (tagging triggers
`pypi-publish.yml`, `docker.yml`, `release-corpus.yml`, each of which
independently re-runs `make verify` at the tagged commit before publishing):

1. `CHANGELOG.md` has a dated section for the version being released
   (`## vX.Y.Z - YYYY-MM-DD`), and `## Unreleased` items have moved into it.
2. `pyproject.toml` `version` and `CITATION.cff` `version`/`date-released`
   match the tag you are about to create.
3. Tag it **annotated and signed**: `git tag -s vX.Y.Z -m "release: vX.Y.Z"`
   (a lightweight or unsigned tag now fails `verify.yml`'s REL-08 check).
4. Push the tag, then create the GitHub release from it. The three release
   workflows run automatically; watch that `verify` (and, downstream,
   `verify-published`) succeed before considering the release done.
5. Confirm the SBOM, provenance attestation, and (for the image) cosign
   signature are attached/verifiable, per `SECURITY.md` §Supply chain.
