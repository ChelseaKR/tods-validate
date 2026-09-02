# Changelog

Notable changes to tods-validate. Rule IDs are never renumbered or reused;
new checks may be added in minor releases.

## [Unreleased]

Changed:

- The branch ruleset is applied, and `docs/rulesets/main.json` is the export of
  what is enforced rather than a description of what was wanted. Four documents
  said no ruleset was enabled on this repository; `protect-main` had been active
  since 2026-07-09, with ten required checks and an admin bypass, so the file and
  the setting had never been compared. It now requires sixteen checks, `contract`
  among them, so the gate protecting the v1 public contract can no longer be red
  on a pull request that merges. `bypass_actors` is empty, which means it binds
  the maintainer too.

  Two settings went in weaker than the committed file asked for, because the
  file asked for something unsatisfiable. `required_approving_review_count: 1`
  with `require_code_owner_review: true`, against a `CODEOWNERS` naming one
  person and no bypass, blocks every merge: GitHub does not count a
  self-approval. `tests/test_branch_ruleset.py` had asserted both, so the suite
  was green about a configuration that could not run. The assertion now derives
  from the number of code owners, and starts demanding an approval on its own
  the moment a second one is added.

  Applying it also corrected the documented command. Updating a ruleset is
  `PUT .../rulesets/{id}`; the `POST` form the docs carried creates a second
  ruleset, and two rulesets both apply.

Added:

- Every published file is compared with the deployment, not just the front
  page. `pages.yml` uploads the whole `web` directory, 46 files today, and
  `scripts/check-deployed-playground.sh` compared exactly one of them, once a
  week. `scripts/check-deployed-tree.sh` walks the tracked tree and names every
  file whose live bytes are not the published bytes;
  `.github/workflows/live-integrity.yml` runs it daily and on demand. It refuses
  to pass vacuously: a comparison set under 40 files, a fetch that does not
  succeed, and an origin that answers a guaranteed-missing path with anything but
  404 are failures rather than a quiet OK. The `drift` job moves out of
  `playground-deployment.yml`, which keeps the two jobs that need a browser on
  their weekly cadence.

  It is red on arrival, and that is the finding rather than a defect in the
  check: all 46 published files currently differ from the deployment. The last
  successful deploy was 2026-08-22, and the page metadata added since then has
  never reached the site. The version pin both the boot check and the
  accessibility audit read is identical on both sides, which is why nothing
  already running could see it.

- Every published page says what it is and where it is. The playground and all
  44 rule-catalog pages carried a `<title>` and nothing else in the head: no
  description, no canonical, no Open Graph, no Twitter card. Each page now
  carries all of them. A rule page describes itself with the rule's registered
  description, which is the paragraph it already renders, so there is one
  string rather than two. Its canonical is `RULE_PAGE_BASE + <id>.html`, the
  same URL SARIF `helpUri` and editor hovers already publish, so a page's
  canonical and the link a CI annotation hands a reader cannot drift apart.

  Every absolute URL carries `/tods-validate/`. These pages are served at a
  path on an origin five sibling projects share, and
  `https://chelseakr.github.io/` is itself a 404, so a canonical naming the
  bare origin would tell a crawler that six unrelated projects are one page,
  and a root-relative href would resolve to another project or to nothing.

  No description states a rule count, a conformance level, or coverage: those
  are derived from the registry, and a figure in a meta tag would be a copy
  nothing derives. None of them implies that Cal-ITP, MobilityData or the TODS
  working group has endorsed this; see NOTICE.
  `tests/test_generate_rules_doc.py` and `tests/test_playground.py` fail on
  each of those, and their expected origins are written out rather than read
  from `RULE_PAGE_BASE`, because a check that derives its expectation from the
  constant it is checking moves with the mistake.

Changed:

- The `make citation` gate is now `make citation-cff`, and the CI job that runs
  it is renamed to match. It validates `CITATION.cff`, the file describing how
  to cite the software; it has never had anything to do with the spec citations
  findings carry. In a repository whose premise is cited findings, a green
  `make citation` read as a claim about the wrong thing entirely. The recipe is
  unchanged and `docs/rulesets/main.json` is updated so the intended ruleset
  still names a check the workflows produce.

Fixed:

- The deployed-playground check drove one broken fixture through the live page
  and asserted the report mentioned that fixture's rule. A page that answered
  every feed with findings passed that unchanged, so "the playground validates"
  and "the playground complains" were not distinguishable by any gate. It now
  runs the valid fixture through the same page afterwards and fails if the
  report carries any rule ID at all (#146). Running it second also exercises
  the cleanup in `web/index.html` that unlinks the previous run's files from
  `/feed`: a leak there now surfaces as findings carried over from the run
  before. Re-selecting an identical file list is not a `change` event, so the
  file input is cleared between runs; without that the second upload silently
  reused the first one's selection.

- `test_rule_page_carries_expected_fields_and_escapes_html` asserted
  `"<link " not in page` to enforce "no external assets". That stated the rule
  more broadly than the rule is: what must not appear is a link that makes the
  browser fetch something. It now names the rels that load (`stylesheet`,
  `icon`, `preload`, `prefetch`, `preconnect`, `manifest`) and permits
  `rel="canonical"`, which fetches nothing.

- The 44 rule-catalog pages published at `web/rules/` had never been audited
  for accessibility. `pages.yml` deploys the whole `web/` tree; `make a11y`
  pointed axe and HTML_CodeSniffer at `index.html` and a generated report and
  at nothing else. Added to the gate, they failed it: **141 colour-contrast
  errors and 43 "links must be distinguishable without relying on colour"
  errors**, from two defects in one shared stylesheet. It declared
  `color-scheme: light dark` and then set no `color` or `background` on
  `body`, so a user agent in dark mode painted light text on an unpainted
  canvas and every text element failed, `<h1>` and body copy included; and
  links were `color: inherit` with `text-decoration: none`, leaving them
  indistinguishable from body text by any means at all. Both fixed, every
  colour stated for both schemes with its computed ratio recorded, all four
  audited URLs passing.
- `scripts/generate_feed.py` promised packages that "can be regenerated
  bit-for-bit", but wrote zip entries with build-time mtimes, so two runs of
  one seed produced identical contents inside archives with different
  checksums. Entries now carry a fixed timestamp. This matters now that the
  archives are published: a benchmark number is only checkable against the
  bytes it was measured on.
- The weekly mutation workflow could not fail. `continue-on-error: true` on
  the job, `|| true` on every step: a kill rate that halved rendered
  identically to one that did not move. It now fails below the floor committed
  in `perf/mutation-baseline.json` (CQ-47). Re-measuring also found the
  documented ~65% stale, recorded against 280 mutants when the engine now
  generates 330; the real figure was 57.6%, and killing twelve survivors in
  one under-tested helper moved it to 62.2%.

- The v1 public-contract gate verified `pythonExports` against each module's
  `__all__`, which is a declaration of the export list rather than the export
  list. A rename that left the list behind removed `tods_validate.suggest_fixes`
  from the package while `__all__`, `docs/v1-contract-candidate.json` and the
  comparison all still agreed with each other: `scripts/check_public_contract.py`
  printed "v1 public-contract candidate is current", exited 0, and all 707
  tests passed with a public export that no longer imported. Every declared
  name is now resolved against its module, and an unresolvable one fails the
  gate by name. This is the third field found comparing itself, after
  `contractVersion` and `cliExitCodes`, and it matters more than either: the
  public Python exports are one of the four things v1 promises.

- A companion GTFS file that parsed but did not read in full counted as a
  clean read. `loader.py` splits CSV defects into ones that stop parsing
  (`encoding`, `empty`, `csv_error`) and ones that leave the file parsed but
  drop values (`ragged`, `duplicate_header`). #125 fixed the first kind for
  companion files; the second kind still counted the file as `present`, so
  every rule reading it recorded `ran` in the coverage manifest. Nothing
  reported the defect either way, because TODS-E103/E104/E105 scan the TODS
  package and never the companion feed. One short row in a companion
  `trips.txt` therefore did one of two things: dropped a `block_id`, leaving
  the run to report "No problems found", "Every applicable check ran" and
  exit 0; or dropped a `trip_id`, and reported `TODS-E307` against the
  producer's `run_events.txt`, an ERROR asserting that a trip "does not exist
  in the companion GTFS trips.txt" when it did. Such a file is now not
  available to resolve references against, exactly as an unreadable one
  already was not: dependent rules are recorded `skipped:needs_gtfs_table`,
  the skip counts as unrequested so `--require-complete-run` fails on it, and
  `TODS-W302` discloses it with the loader's own message so the producer gets
  the row or column number. `loader.PROBLEM_CODES` now closes the code space,
  with a test that reads the parser's own source, so a defect code added later
  cannot default to harmless. See
  [ADR 0007](docs/adr/0007-companion-gtfs-partial-read-is-not-a-read.md).

- Three checks that read a document produced outside this repository could
  report success without having read it. Each now fails closed and says what
  it did not read.
  - `doctor`'s gtfs-validator stage counted notices out of a `report.json`
    whose shape it did not understand. A report that parsed as JSON but was
    not an object, or had no top-level `notices` array, or held a notice with
    a non-integer `totalNotices` or a severity this version does not count,
    yielded zero notices and `status="ran"` -- rendering as "0 error
    notice(s), 0 warning notice(s), 0 info notice(s)", exactly what a
    genuinely clean gtfs-validator run renders as, and exiting 0. The stage is
    now FAILED with a reason naming what could not be read, which the existing
    exit-code rule already treats as a failure, so a merged feed nobody
    checked no longer exits 0 (#147).
  - `scripts/spec_watch.py`, the tripwire for `schema.py` drifting from the
    upstream spec, printed `spec-watch: schema.py is in sync with the upstream
    spec.` and exited 0 for any document it could not parse. Upstream
    restructuring its headings, renaming the Type or Required columns, or the
    raw URL serving any other 200 all landed there, and the weekly workflow
    greps stdout for drift, so nothing would have reported that the tripwire
    had stopped working. A run that recognises no field table now raises and
    prints a report under a heading the workflow opens an issue for; a run
    that reads some of the four in-scope tables but not all of them names the
    ones it did not read and exits 2 rather than 0. Every report, clean ones
    included, now ends with the tables it compared. A fetch failure still
    writes nothing to stdout, so a flaky network still files no issues.
  - `scripts/check_npm_audit.py`, the merge-blocking Node advisory gate, has
    a cross-check for reports it cannot parse, guarded by `blocking_total`,
    which returned 0 for a report whose `metadata.vulnerabilities` counts it
    could not read. A report that degraded in both halves at once -- no
    readable counts and no parseable advisories -- disarmed its own guard and
    passed. Unreadable counts are now distinct from zero, and a
    `vulnerabilities` value that is not an object fails instead of parsing as
    an empty advisory list.

- The weekly **Playground deployment check** failed on `main` from 2026-08-24
  against a deployment that was correct. Its drift job compared the live page
  with `web/index.html` at the most recent release tag, and `v0.10.0` tags a
  page still pinned to `0.9.0`: the repin landed on `main` after the tag
  (#142) and was dispatched live, so the served page was right and the
  expectation was stale. A tag cannot be corrected in place, so the check
  could never have gone green again. It now compares against `web/index.html`
  on the default branch, which is both what `workflow_dispatch` deploys and
  the honest answer to "the page this repository publishes", and which goes
  green again on the deploy that resolves any real drift.

- The secret-scan gate could not see the working tree. `make secrets` ran
  `gitleaks detect --source .`, which walks commits, under a comment claiming
  it covered "working tree + history". Measured: a file at the repository root
  holding an AWS key pair, a GitHub PAT and a Slack bot token, saved and never
  added to the index, gave "283 commits scanned / no leaks found" and exit 0;
  the same tree with `--no-git` gave "leaks found: 1" and exit 1. The gate now
  runs both scans, each reporting its own result, and neither can
  short-circuit the other. `.gitleaks.toml` scopes the working-tree scan away
  from `.venv/` and `node_modules/`, which `verify.yml` populates before it
  runs `make verify`.
- The performance budget could only fail for one reason, and doing less work
  made it greener. `scripts/check_perf_budget.py` divided an assumed row count
  (`trips * 2`) by CPU time and discarded the timed run's result entirely, so
  a validator that had stopped reading the feed would have burned almost no
  CPU, reported an enormous rate, and passed further inside the budget than a
  correct one. Every repetition now counts the rows the loader actually
  parsed, refuses to report a rate below the floor the generator writes, and
  refuses when two repetitions disagree about the count.
  `maxRegressionFactor` is also bounded: it was read unbounded from the same
  file as the baseline, where a large enough value retires the gate rather
  than loosening it.
- `mypy` did not check the scripts that are the gates. `ruff` covered
  `src tests scripts`; `mypy` had `files = ["src"]`, leaving
  `check_public_contract.py`, `check_npm_audit.py`, `generate_rules_doc.py`
  and `spec_watch.py` unchecked. Now `["src", "scripts"]`, 44 files. One real
  error surfaced and is fixed: `spec_watch.py`'s spec fetch returned `Any`
  from a function declared `-> str`.
- `make verify` could be green on a tree CI rejects, without saying so. Two
  `pull_request` jobs had no `make` equivalent and no mention in the Makefile
  header that enumerates CI-only work: `perf`, and the VS Code extension
  package job (path-filtered to `editor/vscode/**`, which is why it went
  unnoticed). Both are named now, and `tests/test_ci_gate_parity.py` compares
  the header to the workflows so the next one cannot go unnamed.
- `docs/read-api.md` was outside the currency gate. It documents ten of the
  nineteen names the v1 contract freezes and carried no `Last verified` stamp,
  so `make docs-check` had nothing to fail on when it drifted. Added to
  `STAMPED`, and `tests/test_doc_currency.py` now derives its parametrize from
  that list instead of restating it.

Changed:

- `loader.py` now pools cell values per file: equal cells in one file share one
  string, which on repetitive transit data is most of them. Peak memory over a
  full `run()` falls from **36.6x the input bytes to 30.9x** with throughput
  unchanged (65.9k against 65.0k rows/CPU-s, inside the noise). Values are
  equal as before and only their identity changes, so no output moves.
  A per-file dict rather than `sys.intern`, because interned strings live
  until the interpreter exits and would make every feed opened in the LSP
  server permanent.
- `SECURITY.md` states the memory ceiling next to the zip-bomb limits it
  contradicts. The 512 MiB per-member and 2 GiB total limits bound extraction,
  not memory: at 31x they describe packages needing 16 and 62 GiB, so the
  practical ceiling is a few hundred MiB of input on an 8 GiB machine.
  `tests/test_memory_budget.py` fails if that prose and `perf/baseline.json`
  disagree.

- Development dependencies moved from the `dev` extra to a PEP 735
  `[dependency-groups]` table (CQ-27, #145), so no linter, type checker, or
  test runner is installable as an extra of the published distribution.
  Install with `uv sync --group dev` or `pip install -e . --group dev` (pip
  25.1 or newer); `[project.optional-dependencies]` now holds only the `lsp`
  and `dataframe` runtime extras. `tests/test_packaging.py` is the AUTO-GATE
  the standard's CQ-27 row asks for and fails if development tooling
  reappears as an extra. ADR 0005 carries an amendment noting the move.
- CHANGELOG section headings adopt the Keep a Changelog form,
  `## [X.Y.Z] - YYYY-MM-DD` (DOC-07/REL-10). The release gate's
  CHANGELOG-section grep in `verify.yml` moved with them, and
  `tests/test_changelog.py` now runs that grep, extracted from the workflow,
  against this file: the two can no longer drift apart without the ordinary
  test suite saying so, instead of the mismatch surfacing on a release tag.

- **TODS-W302**'s title becomes "Referenced file is missing or was not read in
  full, references not checked" (from "missing or unreadable"), and its
  description covers the third case. Its ID, severity and category are
  unchanged, so `docs/v1-contract-candidate.json` is unaffected.
- The `skipped:needs_gtfs_table` reason in the coverage manifest widens from
  "the companion GTFS feed has none of the files the check reads" to the same
  wording plus ", or could not read one of them in full". The old wording was
  already inaccurate for the unreadable companion files v0.10.0 introduced:
  the file was there.

Added:

- [`docs/phase-gates.json`](docs/phase-gates.json) and
  `scripts/check_phase_gates.py`, a monthly tripwire for the eight gates
  `docs/MULTIYEAR-PLAN.md` is waiting on: the TODS Board's answer on a shared
  conformance corpus (#153), the `employee_run_dates.txt` primary key (#156),
  the three upstream spec proposals (#45, #42/#43, #46), a real production feed
  (#76), an assistive-technology walkthrough (#74), and the dated
  deployed-playground record (#146). The plan's rule is that "a phase is not
  scheduled until it can be worked", which left one thing unanswered: how
  anybody would find out that it can be. All eight were re-read live on
  2026-08-27 and all eight are still open, so phase 5 has not started and
  neither of phase 6's triggers has fired.

  It files an issue when a gate moves **and when it could not read one**,
  because a tripwire that goes quiet when it breaks converts an outage into a
  green tick. A partial read reports how many of the recorded gates it actually
  compared, so a run that read two of eight cannot be mistaken for a complete
  one.

- The four stewardship contracts that had been open with nobody assigned, each
  as a *checked* contract rather than a document, because the portfolio defines
  AUTO-GATE as merge-blocking with no `|| true`:
  - **Incident response.** [`.github/labels.yml`](.github/labels.yml) declares
    the `incident` / `sev1`-`sev4` / `deploy-caused` convention (IR-02, IR-04,
    IR-17); [`docs/incidents/TEMPLATE.md`](docs/incidents/TEMPLATE.md) carries
    every section IR-07 names; and
    [`docs/runbooks/secret-exposure.md`](docs/runbooks/secret-exposure.md)
    works IR-10 to IR-14 in order, with a per-credential revocation table for
    the tokens this project could actually leak.
    `scripts/check_incident_contract.py` gates all of it plus IR-15 (no
    wildcard `git add` in unattended automation) and IR-16 (no scripted commit
    without a secret scan). Both of those were already clean, so each reports
    what it scanned rather than only whether it found anything.
  - **Data governance.** Five sources classified under the v2.0.0 tiers in
    [`docs/data/`](docs/data/), four at L1 and a user's own feed at L3, with
    `scripts/check_data_cards.py` failing in both directions (a declared source
    with no card, a card with no declared source) and additionally on a
    tier disagreement or a source path that no longer exists (DG-01).
  - **QM-11, the DORA quarterly review.**
    [`docs/DORA-2026-Q3.md`](docs/DORA-2026-Q3.md) plus a JSON snapshot and
    `scripts/delivery_metrics.py`. Three of five metrics come back breached
    and one N/A; the collector writes `null` with a reason rather than `0` for
    anything it cannot measure, which `tests/test_delivery_metrics.py` pins.
  - **AI-development measurement.** The `AI-DEV-MEASUREMENT: APPLIES`
    declaration in the metrics ledger, the diagnostic share measured and
    stated as never-gating, and two BASELINE counterweights each carrying a
    dated graduation decision of 2026-11-30.
- [`docs/runbooks/publish-vscode-extension.md`](docs/runbooks/publish-vscode-extension.md),
  recording why the extension is not on the Marketplace as the steps to publish
  it rather than as an excuse (EXP-10). The VSIX builds, type-checks, audits,
  and verifies its own contents in CI today; what is missing is an Azure DevOps
  publisher and a signed Eclipse Contributor Agreement.
- A `stewardship` job in `ci.yml` running the two new AUTO-GATEs, and both
  added to `make verify`, which now runs fifteen gates.

- [`docs/a11y/STATEMENT.md`](docs/a11y/STATEMENT.md): the dated accessibility
  statement, carried by the `docs-check` currency gate, naming **WCAG 2.1
  Level AA** as the target and deliberately making no conformance *claim*,
  because the only evaluation run is automated. It tables every surface
  against what has actually been checked and by what.
- Two new budget gates beside the existing throughput one.
  `scripts/check_memory_budget.py` holds peak traced memory per input byte to
  1.03x the committed ratio (FIX-04), and `scripts/check_bundle_budget.py`
  holds the shipped HTML to byte ceilings in `perf/bundle-baseline.json`,
  including a report at ten thousand findings, which grows at 235 bytes a
  finding and so can grow silently. Both refuse to pass when they cannot
  compare, like the throughput gate they copy.
- Synthetic benchmark feeds are published (EXP-13).
  `.github/workflows/release-corpus.yml` builds one byte-reproducible archive
  per profile on every release, prints their checksums into the job summary,
  and attaches them. Every number in `docs/BENCHMARKS.md` previously cited a
  feed a reader could not obtain.

- [`docs/rulesets/main.json`](docs/rulesets/main.json), the branch ruleset for
  `main` as a reviewable artifact rather than a paragraph of prose in
  `docs/CONFORMANCE-GAPS.md` (CQ-37 to 43, CICD-03/11-18). **It is not
  applied**; enabling a ruleset is a live settings change no automated pass
  makes, and `docs/rulesets/README.md` says so and gives the command.
  `tests/test_branch_ruleset.py` keeps its required-status-check list in step
  with the checks the workflows actually report, in both directions. Writing
  the prose down as a file immediately found a defect in the prose: it named
  `zizmor` among the required checks, and `zizmor.yml` is path-filtered on
  `pull_request`, so on a pull request touching no workflow file the check
  never reports and the merge could never happen. It is excluded, with a test
  that keeps it excluded until the filter goes away.

- [`docs/MULTIYEAR-PLAN.md`](docs/MULTIYEAR-PLAN.md), which sequences the
  remaining work in `docs/roadmap.md`, `docs/CONFORMANCE-GAPS.md`, and
  `docs/ideation/` into six phases across roughly 2026 to 2029, and separates
  the work that is gated on engineering from the work that is gated on other
  people. The three fixes above are its first phase.

- `scripts/check-playground-boots.cjs`, the first check that shows the
  deployed playground actually works. It drives the live page in a real
  browser, waits for Pyodide to load and micropip to install the pinned wheel
  from PyPI, uploads a synthetic fixture, and fails unless the rendered report
  contains the finding that fixture triggers. Every previous playground gate
  was satisfiable by a page that is byte-perfect, accessible, and broken for
  every visitor: the drift check compares bytes, and the live accessibility
  audit loads the page with `?a11y-static=1`, the parameter that deliberately
  skips the Pyodide boot. This project has shipped exactly that failure (#136:
  a pin PyPI did not serve, so `micropip.install` rejected it for every
  visitor while every gate stayed green). Runs in `pages.yml` after each
  deploy and weekly in `playground-deployment.yml` (#146).
- `src/tods_validate/py.typed`. The package declared no type information, so
  every downstream type checker treated an installed `tods-validate` as
  untyped and refused to look inside it: a five-line consumer importing
  `validate_feed` got `Skipping analyzing "tods_validate": ... missing library
  stubs or py.typed marker` and exit 1 from `mypy --strict`, and gets
  "Success" now. `mypy --strict` has run over `src/` on every pull request
  since 0.1.0 without any of that reaching a caller.
- Tests for the two public exports nothing exercised.
  `tods_validate.read.to_dataframe` and `tods_validate.__version__` are both in
  `docs/v1-contract-candidate.json` and were named in none of the 52 test
  modules, which a 90% line-coverage floor cannot see. Both are covered, and
  `tests/test_contract_surface.py` adds the floor that finds the next one.
- `tests/test_readme_claims.py`: every `--flag` the README names must exist in
  the CLI, or be attributed to another program, or be recorded as
  documented-absent with a link to the gap that tracks it.

Documentation:

- The Observability section claimed an opt-in `--log-format json` flag. No
  such flag exists, and no module under `src/` imports `logging`, so there are
  no log records for one to format. The section says that now, the Standards
  Conformance table points at the new
  `docs/CONFORMANCE-GAPS.md#observability` row, and the row sets out both ways
  to close it without picking one.
- `docs/api.md` listed seven `Finding` fields and two helpers. The dataclass
  has ten fields and three helpers, and `docs/report.schema.json` already
  required the three it omitted (`data`, `caused_by`, `severity_original`) and
  `fingerprint()`, which is the identity `--baseline` matches on.
- `docs/read-api.md` now documents `FeedFile.readable` and `LoadProblem`;
  `problems` had been documented without its element type.
- Two smaller README corrections: "16 reference checks" is now "the 16 checks
  that read GTFS files" (six of the sixteen are field, semantic or coverage
  rules), and the `ingest-ready` paragraph records that it currently resolves
  to the same settings as `strict`.
- `docs/plans/v1.0.0-readiness.md`, an item-by-item readiness assessment with
  evidence per item, and `docs/plans/improvement-plan.md`, the log behind it.

## [0.10.0] - 2026-08-21

`v0.9.1` was tagged and signed (commit `edd2ea1`) but its GitHub Release
object was never created, so `pypi-publish.yml` never ran: PyPI's latest
published version stayed 0.9.0 while `pyproject.toml` and the tag said 0.9.1
(#136). Sixteen PRs landed on `main` after that tag, several changing
validator behavior, so re-publishing the number `0.9.1` would misdescribe
what actually ships. This release supersedes it. The `v0.9.1` tag is left in
place, signed and unmoved, and is not the version anyone should install;
`v0.10.0` is.

The version is a MINOR bump, not a PATCH, because two of the changes below
are not backward-compatible: the Python floor rises to 3.12 (drops installs
on 3.11), and `TODS-E301`/`TODS-E303`/companion-GTFS reference checks now
fail closed on an unreadable file instead of silently skipping or inventing
findings, which can change a previously-clean run's exit code. Per this
repo's pre-1.0 SemVer policy (`docs/standards/RELEASE-AND-VERSIONING-STANDARD.md`
REL-05), a `0.y.z` MINOR release may carry a breaking change; this is not
yet the v1.0.0 release described in `docs/v1-contract-audit.md`, which is
reserved for a conformance-only release after the contract snapshot has
gone unchanged for one full release cycle. This one does not qualify --
it adds a rule (`TODS-E207`) and changes coverage-manifest behavior in three
commands.

Fixed:

- A companion GTFS file that could not be decoded (bad encoding, empty,
  unparseable CSV) counted as present. The reference rules that read it ran
  against an empty table instead of being skipped, invented ERRORs against
  every real ID in the TODS file that referenced it, and the coverage
  manifest recorded them `ran`. The same shape reached two TODS-internal
  checks: an unreadable `run_events.txt` or `vehicles.txt` produced invented
  `TODS-E301`/`TODS-E303` findings the same way. All three now treat an
  unreadable file the same as a missing one — the rule is skipped
  (`skipped:needs_gtfs_table` for the companion-GTFS case), and `TODS-W302`
  discloses that the file could not be read (pointing to `TODS-E103` for the
  reason on the TODS side), instead of silently reporting `has no <file>` or,
  worse, inventing errors against it.
- `diff OLD NEW` reported a rule's old finding "fixed" whenever it was absent
  from NEW, without checking whether the rule ran in NEW at all. A rule that
  stopped running — a companion GTFS feed dropped, or newly unreadable
  (#125), between OLD and NEW — makes its old findings disappear the same
  way a genuine fix does, and `diff` could not tell them apart: comparing
  `tests/fixtures/invalid/TODS-E307` (a bad `trip_id` reference) against the
  same package with the companion `trips.txt` removed reported `fixed: 1`
  and exit 0, when the bad reference was never re-checked, let alone fixed.
  `diff` now uses `run_with_coverage` and only counts an OLD-only finding
  `fixed` when its rule ran in NEW; otherwise it lands in a new `unknown`
  bucket, named in the counts line. Every rule that ran in OLD and not in
  NEW is also named below the findings, whether or not it had a finding to
  lose — a dropped companion can zero out 16 checks with 0 findings on
  either side, which used to read as a silently clean diff.
- `batch` used the two-tuple `run()` wrapper, so none of its three formats
  (text, `--format json`, `--format markdown`) had a coverage manifest to
  disclose: a TODS-only feed in a fleet run skipped 16 of 42 checks, 9 of
  them ERROR-severity, and its row read `0 0 0 pass` — exactly the numbers a
  fleet compliance artifact is read for, with nothing saying the run was
  partial. `batch` now uses `run_with_coverage`. Every format carries the
  manifest: text and Markdown gain a "checks not run" column beside each
  feed's status plus a fleet-wide `Rule-set coverage` line in the roll-up
  (pooling every feed's outcomes, the same disclosure a single-feed report
  already carries); `--format json` adds a per-feed `checksNotRun` count and
  a `coverage` block matching `validate --format json`'s.
  `--require-complete-run` (#124) is now available on `batch` too: a feed
  with an unrequested skip (missing/unreadable companion GTFS) fails that
  feed, the same as it does for `validate`.
- `uv.lock` pins `pip` at 26.2.1, past `PYSEC-2026-3721` (disclosed after
  26.1.2 was pinned). Vendored only as a transitive build/audit tool, never
  imported by `tods_validate` itself, but it was failing `make audit` (and
  would fail it for any PR, unrelated to that PR's own change) until bumped.
- `fix -o OUT` and `anonymize -o OUT` no longer destroy a file the loader could
  not read. Both commands rebuild every file from the loader's headers and rows;
  a file whose decode or CSV parse failed has neither, so it was written out as a
  single newline — the user's data replaced by an empty file. `fix` compounded it
  by printing `Nothing to fix.`, because no trim/blank/duplicate counter had
  moved, so the run reported that it had changed nothing while it was the run
  that lost the data. Both commands now refuse to write such a package and name
  the offending file; `fix`'s dry run reports it instead of claiming there was
  nothing to fix. Use `--encoding` if the file is deliberately not UTF-8.
  Packages that load cleanly are unaffected.
- `--format github` now discloses the checks that did not run. It is the only
  format the composite action emits, and it was the one format that never
  carried the coverage manifest: `render_github` took no `coverage` argument
  at all, so a feed validated without a companion GTFS feed printed
  `0 error(s), 0 warning(s), 0 info` and stopped there, while 16 of 42 checks
  had not run, 9 of them ERROR-severity. An agency or vendor who left the
  `gtfs:` input out of the workflow got a green check and had no way to learn
  that no reference was ever resolved. The summary line now carries the run's
  scope, and each reason a check did not run becomes its own `::notice`
  annotation naming the rules, so the disclosure reaches the pull request's
  Checks tab and not only the log.
- Every report format now names the rules that did not run, not just how many,
  and a run that skipped nothing says so (`Every applicable check ran (42 of
  42).`) rather than staying silent. Silence could not be told apart from a
  format that does not disclose, which is how this defect survived.
- The Markdown report states its rule-set coverage with or without `--stamp`.
  The block used to be printed only under `--stamp`, which tied a statement of
  what the run checked to a statement of when it ran; the unstamped report is
  the default and the one people paste into issues.

Changed:

- Minimum supported Python raised from 3.11 to 3.12 (#72), closing CQ-01
  directly against the standard's stated floor (Python 3.10 reaches EOL
  October 2026) instead of via the declared deviation `docs/adr/0001` had
  recorded since 2026-07-09. `docs/adr/0006-python-312-floor.md` supersedes
  0001. `README.md` and `CONTRIBUTING.md` now say "Requires Python 3.12 or
  newer"; CI's test matrix is `3.12`/`3.13` (3.11 dropped). Installed
  releases are unaffected; this binds new installs, upgrades, and local dev.

Added:

- `TODS-E207` checks that `routes_supplement.txt`'s `route_color` and
  `route_text_color` are valid GTFS Color values: six hexadecimal digits, no
  leading `#` (GTFS reference, "Field Types > Color"). Every other field a
  supplement file inherits from its GTFS base is typed `Text` by
  `schema._supplement()` regardless of the base file's real GTFS type, so
  these two carried no format check at all before this; `_supplement()`
  gained a `field_types` override used only for these two fields, rather
  than transcribing the full GTFS field-type inventory for a single rule.
  (#101)
- `--require-complete-run` fails the run when a check could not run because an
  input was missing, such as a companion GTFS feed that was not given. Skips
  the caller asked for (`--ignore`, opt-in rules left off, `--spec-version`
  scoping) are disclosed but do not fail it. The GitHub Action exposes it as
  the `require-complete-run` input.
- **A skipped check still does not change the exit code by default.** That is
  deliberate: this tool has shipped as a merge gate since 0.1.0 and every feed
  validated without a companion GTFS feed skips 16 checks, so failing on a
  skip would turn existing pipelines red on upgrade for something they never
  asked the tool to promise. The README now states it instead of leaving `0`
  to be read as "fully checked".

Docs:

- The Standards Conformance section's intro paragraph enumerated eleven
  standards ("code quality, security & supply chain, ... AI-evaluation") while
  the table below it declares fifteen -- Performance, Incident Response, Data
  Governance, and AI Development Measurement were in the table and missing
  from the prose. v0.9.1 (#118) fixed the table itself (a comma in the
  Accessibility row's state broke the vendored portfolio-standards v2.0.0
  DOC-11 checker, which the prose drift did not: the checker grades the
  table, not the paragraph above it); this is the second, smaller half of
  #113. The paragraph now points at the table instead of maintaining a second,
  driftable count.

## [0.9.1] - 2026-08-18

A patch release that repairs the release pipeline itself and ships one
playground change. No validator behaviour changes: no rule added, removed,
renumbered or re-severitied, and the CLI, Action, and report contracts are
untouched. It matters because the two pipeline defects below are why the
deployed playground still serves tods-validate 0.7.0 today; this is the
release that moves it forward.

Fixed:

- The playground deploy no longer races the PyPI upload it depends on. Both
  `pages.yml` and `pypi-publish.yml` fired on `release: published`, and the
  page micropip-installs the exact wheel it pins, so the deploy's guard
  ("refuse to publish a page pinned to a wheel PyPI does not have") checked
  PyPI seconds after the release was published -- long before the upload
  finished -- and refused, correctly, on both v0.8.0 and v0.9.0. The deploy is
  now a `deploy-playground` job at the end of `pypi-publish.yml`, called via
  `workflow_call` after `verify-published` has re-downloaded the wheel from
  PyPI and checked its provenance, so the ordering is structural rather than a
  race. The guard stays, now with a 10-minute retry window for index
  propagation, and a wheel PyPI never serves still fails the deploy naming the
  missing wheel -- it never deploys anyway and never skips quietly.
  `workflow_dispatch` remains for out-of-band deploys.
- The PyPI publish step accepts what the build backend now produces. v0.9.0
  built, signed, and attested cleanly, then failed at upload with
  "'2.5' is not a valid metadata version": the pinned
  `pypa/gh-action-pypi-publish` commit predated Metadata-Version 2.5. The pin
  is now v1.14.2, which publishes 2.5 metadata; v0.9.0 reached PyPI through a
  manual re-run after that fix, and v0.9.1 is the first release to publish
  through it end to end. (#116)

Added:

- The playground footer has a support link beside the version line -- a plain
  text link whose text says where it goes, sized to a deliberately spare page.
  This is the change that needs a release to reach the deployed site: the
  playground only ever serves `web/index.html` as of the latest tag, which is
  what `scripts/check-deployed-playground.sh` enforces. (#96)

Docs:

- The README's Action examples pin the current release instead of the
  previous one; the v0.9.0 miss was corrected in #115 and this release bumps
  the pins to v0.9.1 in the same commit as the version, so the quickstart
  cannot trail the release again.
- The Standards Conformance table's Accessibility row states its scope in the
  same `Applies (scope)` form as every other row. (#118)

## [0.9.0] - 2026-08-16

Behaviour change for Action and CLI consumers: two checks now report findings
they did not report in v0.8.0, and one stops reporting findings it should never
have reported. On the same feed, `tods-validate` can therefore exit 1 where
v0.8.0 exited 0, or exit 0 where v0.8.0 exited 1. Nothing about the exit-code
contract itself changed (0 clean, 1 findings at or above the threshold, 2 usage
error), and no rule ID was renumbered, removed, or given a new severity. The
three checks are, in this section: `TODS-E204` on `employee_run_dates.txt`
duplicates, `TODS-E201` on supplement rows that add a GTFS entry, and the
companion-GTFS detection fix.

Fixed:

- CQ-09's lockfile-drift gate was missing the half that fails. Every CI job and
  the release verification workflow installed with `uv sync --frozen`, which
  installs exactly what `uv.lock` records and exits 0 whether or not the lock
  still agrees with `pyproject.toml` -- so a version bump or an added dependency
  could ship a stale environment with every check green. Measured on this repo:
  with `pyproject.toml` at 0.9.0 and `uv.lock` still at 0.8.0, `uv sync --frozen
  --extra dev` exits 0 and installs 0.8.0, while `uv lock --check` exits 1.
  `uv lock --check` now runs before every `uv sync` in CI and in the release
  verify workflow, and as the first gate in `make verify` (`make lockfile`).
  ADR 0005, which asserted that `--frozen` "fails on any lockfile drift",
  records the correction.
- The accessibility gate now runs an accessibility check. `make a11y` began
  with `npm audit --audit-level=high`, so once an unpatched HIGH advisory
  appeared in the pa11y-ci development toolchain the recipe aborted on its
  first line and `npm run a11y` stopped executing entirely — the job went red
  for a dependency reason and audited nothing, on every commit, for weeks. The
  npm dependency audit is now its own gate (`make npm-audit`, in the `audit`
  job, at the same HIGH floor) and `make verify` runs every gate independently
  and reports each one's result, instead of stopping at the first failure. The
  one advisory behind this, GHSA-jmr9-qjv8-65gv in `extract-zip`, is recorded
  in `waivers.yml` with an owner and a 2026-11-15 expiry; a different advisory,
  the same advisory on another package, or the same advisory escalated in
  severity still fails the gate, which `tests/test_npm_audit_gate.py` pins.
- A stray GTFS file next to the TODS files no longer promotes the package to
  its own companion GTFS feed. A package is a companion only when it carries a
  file TODS IDs resolve against (`trips.txt`, `stops.txt`, `stop_times.txt`,
  `routes.txt`, `calendar.txt`, `calendar_dates.txt`); one `agency.txt` used to
  be enough, which made all 16 GTFS cross-reference rules run against a feed
  with no trips, stops or calendars — 28 invented errors on a valid feed, and a
  coverage manifest reporting 39 of 42 rules as having run.
- Every rule that reads the companion GTFS feed now declares which files it
  reads, and is reported `skipped:needs_gtfs_table` when the companion does not
  have them, instead of running against data that cannot answer it. A TODS
  supplement file no longer counts as its own GTFS base table: `trips_supplement.txt`
  modifies `trips.txt`, so without `trips.txt` there is nothing to resolve a
  `trip_id` against. This also stops `TODS-I501` reporting trip coverage
  computed from supplement rows alone.
- `docs/report.schema.json` now lists `skipped:spec_version`, which the
  validator has emitted since v0.8.0 without documenting: a report from
  `--spec-version 1.0.0` failed the schema it publishes.

Changed:

- Supplement rows known to add a GTFS entry now require every field the GTFS
  reference marks Required for that file. Updates and deletes still require
  only their primary-key fields. The check stays permissive when no companion
  GTFS is available because an addition cannot then be distinguished from an
  update.
- `employee_run_dates.txt` now uses the explicit four-field primary key agreed
  in the #152 discussion. Exact duplicates produce `TODS-E204`;
  `TODS-W408` remains as a grouped compatibility signal for existing machine
  consumers.
- The current GTFS supplement field inventory now recognizes
  `trips.safe_duration_factor`, `trips.safe_duration_offset`,
  `stops.stop_access`, and `routes.cemv_support`.

Added:

- A reviewed v1-candidate public-contract snapshot and blocking drift check
  covering rule IDs/severities/categories, exit codes, supported spec versions,
  Python exports, and required JSON report fields. It runs on every pull request
  and in the test suite; previously it reached CI only through the release
  workflows, so the contract was first verified after a release tag was cut.
  The CLI's exit codes now have names in `tods_validate.policy`
  (`EXIT_CLEAN`/`EXIT_FINDINGS`/`EXIT_USAGE`) that the check reads, instead of
  literals restated inside the checker.
- A blocking WCAG 2.1 AA accessibility job using both axe-core and
  HTML_CodeSniffer on the playground and a generated HTML report. The same gate
  runs during release verification, and the npm lockfile is vulnerability-
  audited. That job audits this repository's `web/index.html`, which is the
  source of the deployed playground and not the deployment; the deployed page is
  now checked separately, against the live URL, by the same runners and standard.
- The playground is deployed when a release is published, rather than only by
  manual dispatch, and the deploy refuses to publish a page pinned to a wheel
  PyPI does not have yet. After each deploy, and weekly, the served page is
  compared against the page this repository publishes and audited for
  accessibility, so a stale or silently failed deployment is reported instead of
  going unnoticed. `tests/test_playground.py` pins the playground's
  `TODS_VALIDATE_VERSION` to `pyproject.toml`'s version.
- Currency stamps on `docs/getting-started.md` and `docs/api.md` (DOC-15), added
  after re-running every command, exit code, signature, and member those pages
  document. `make docs-check` now fails when a stamped page changes without a
  fresh verification, so the date means the text was checked rather than that
  someone typed a date once.
- The perf budget is enforced (QM-02). `scripts/check_perf_budget.py` validates
  a 50,000-trip synthetic feed and fails when throughput regresses past the
  factor in `perf/baseline.json`; `scripts/benchmark.py` could measure this
  before, but nothing compared the measurement to anything. Throughput is
  measured in rows per CPU-second rather than wall clock, so a busy shared
  runner is not reported as a regression, and the check fails rather than
  passes when it has no baseline to compare against.

## [0.8.0] - 2026-07-16

This release broadens compatibility and makes operational changes easier to
inspect: TODS v1 feeds can be validated directly, GTFS changes can be checked
for broken TODS references, and HTML reports can include accessible run
timelines. It also tightens field-format and conformance-corpus safeguards.

Added:

- TODS-E203 now checks Latitude, Longitude, and Non-negative float fields, not
  only Time, Date, and Non-negative integer. An out-of-range `ops_location_lat`
  or `ops_location_lon` (outside -90..90 / -180..180) and a negative or
  non-numeric `shape_dist_traveled` are now reported instead of passing
  silently. Messages for the existing field types are unchanged.
- The VS Code client now packages reproducibly from its lockfile in CI, includes
  its Apache-2.0 license, uploads a reviewable VSIX artifact, and offers a setup
  guide when `tods-validate-lsp` is not available on `PATH`.
- `--format html --timeline` adds an opt-in visual time rail for each
  `(service_id, run_id)`. Event rows with findings use a dashed bar and
  diamond marker, and every rail has a complete sequence-ordered table with
  the same times, work, movement, and finding IDs for screen-reader and
  non-visual use.
- The browser playground is deployed at
  <https://chelseakr.github.io/tods-validate/> and linked from the README.
  Feed files remain in the browser during validation.
- An `ingest-ready` named profile for CAD/AVL import gates. It fails on
  warnings, enables coverage and advisory checks, and adds no ignored rules;
  select it with `--profile ingest-ready` or `profile = "ingest-ready"` in
  `tods-validate.toml`.
- `--spec-version 1.0.0` validates against the TODS spec text as it stood
  before v2.0.0-alpha.1 (deadheads.txt/ops_locations.txt/deadhead_times.txt,
  runs_pieces.txt, and a differently-shaped run_events.txt), transcribed from
  the last commit before v2 spec work began; see `docs/spec-versions.md` for
  the full file/field delta, citations, and exactly which rule bands run
  under each version (structure and field-value rules run against either
  version's schema; reference/semantic/coverage/advisory rules, which assume
  v2.1.0-only mechanisms, are skipped and disclosed via the coverage
  manifest's new `skipped:spec_version` status). `--spec-version` previously
  parsed and validated the flag but had no effect on which schema was
  checked.
- `tods-validate drift OLD_GTFS NEW_GTFS --tods FEED` (EXP-02): diagnoses the
  "your GTFS moved under your TODS" failure directly, reporting exactly which
  referenced `trip_id`/`stop_id` values disappeared and which trips'
  `block_id` changed between two GTFS versions, with a conservative rename
  guess offered only when exactly one new GTFS ID is an unambiguous close
  match. `--format text|markdown|json`; exits non-zero on any break so it can
  gate a GTFS update in CI.

Fixed:

- Malformed feed values and baseline files now produce validator findings or
  clear input errors instead of uncaught exceptions. Numeric parsing requires
  ASCII digits, GitHub annotation properties are escaped, LSP diagnostics stay
  within the validated feed, and baseline documents must contain a findings
  array.
- GHCR release builds now use the lowercase image reference created by Docker
  metadata when running the blocking Trivy scan. The Docker workflow can also
  rebuild an existing signed release tag through `workflow_dispatch`.
- The advisory spec watcher now recognizes a field labeled Optional whose
  description makes it conditionally required. This stops
  `vehicle_assignments.service_id` from opening a false spec-drift issue while
  preserving TODS-E205's conditional requirement.
- Conformance-corpus expectations are now a committed, reviewed oracle. CI and
  the release builder compare every fixture's exact rule-ID set against it
  instead of regenerating expected outcomes from the validator under test.
- The README standards table now uses the canonical Security & Supply-Chain,
  AI Evaluation, and Responsible-Tech Framework labels consumed by the
  portfolio conformance checker.

## [0.7.0] - 2026-07-11

Findings now reach the editor (a language server with hovers and quick fixes,
plus a thin VS Code client), reports state exactly which checks ran and which
were skipped, and local severity policy is supported with mandatory
disclosure. Also new: fix suggestions (`validate --suggest`), an offline
`explain` command with worked examples, pytest helpers for exporters, and two
run-continuity warnings (TODS-W316, TODS-W409).

Added:

- An architecture decision record log under `docs/adr/`: 0000 records the
  practice, 0001–0005 backfill the decisions already in force (the Python 3.11
  floor, the i18n N/A declaration, the nested `editor/vscode` project,
  rules-as-registry, the uv/lockfile adoption). A committed `.python-version`
  pins local development to 3.12, the same interpreter CI runs its gates on.
  Closes CQ-01, CQ-26, CQ-44/45, and DOC-04/05 in `docs/CONFORMANCE-GAPS.md`.
- A permanent per-rule web page for every rule ID, generated into `web/rules/`
  by `scripts/generate_rules_doc.py` alongside `docs/rules.md`, plus a
  `web/rules/index.html` catalog grouped by band. Deployed with the rest of
  `web/` by `.github/workflows/pages.yml`. SARIF `helpUri` and the language
  server's hover text now link to these stable URLs
  (`https://chelseakr.github.io/tods-validate/rules/<RULE_ID>.html`) instead
  of the spec section directly, so the link keeps resolving even if the spec
  text moves; the spec citation itself is still carried in the SARIF rule's
  `properties.specSection` and on the rule page. `scripts/generate_rules_doc.py
  --check` now also fails CI if a committed rule page has drifted from the
  registry.
- TODS-W316: the time companion of W315. A run event that works a trip end to end
  should start at the trip's first scheduled departure and end at its last
  scheduled arrival; a mismatch is a warning, skipped for mid-trip events. Uses
  the stop_times the companion GTFS already ingests.
- TODS-W409: consecutive events in one run should connect in space — an event's
  end_location should be the next event's start_location, since an operator
  cannot teleport between locations. A gap is a warning (legitimate exceptions
  exist), and adjacencies with a blank endpoint are skipped. TODS-only, no
  companion GTFS needed.
- A language server (`tods-validate lsp`, or the `tods-validate-lsp` entry point)
  that re-validates the whole feed when you open or save any TODS file and shows
  each finding inline at its row and field. Findings name a field, so the
  diagnostic underlines the offending value, not just the line. Needs the new
  `lsp` extra (`pip install 'tods-validate[lsp]'`, which brings in pygls); the
  diagnostic-mapping core is pure and unit-tested without an editor.
- The language server now offers quick fixes and hovers. Hovering a finding
  shows the rule's title, description, and spec link; the fixable findings carry
  a code action — "Trim surrounding whitespace" (TODS-W206) and "Delete duplicate
  row" (TODS-W408) — that edits the document in place.
- A VS Code extension under `editor/vscode/` that launches the language server
  for TODS files, so the diagnostics, hovers, and quick fixes show up in the
  editor. It is a thin client (build it with `npm install && npm run compile`,
  press F5 to try it); it is not published to the Marketplace.
- `tods-validate validate --suggest` lists concrete fix suggestions for the
  mechanically-fixable findings after the report, each marked `auto` (safe and
  meaning-preserving, the kind `tods-validate fix` applies) or `review` (derivable
  but worth a human's confirmation, such as a time written `9:45` -> `09:45:00` or
  a date written `2026-03-15` -> `20260315`). A suggestion is only offered when its
  proposed value is one the validator would accept and is reachable by adding
  leading zeros, a zero seconds field, or removing date separators, so it never
  changes what a value means. Text and Markdown output only; the JSON report is
  left untouched so it stays a stable machine contract. The same suggestions are
  available programmatically via `tods_validate.suggest_fixes`.
- A test-helper module (`tods_validate.testing`) with `assert_feed_valid` and
  `assert_feed_produces`, so a TODS exporter can gate its own pytest suite on the
  same checks the CLI and Action run without shelling out. On failure they raise
  with the human-readable report rather than a stack trace. See docs/api.md.
- A contributor guide for authoring rules (docs/authoring-rules.md): how to pick
  a severity and allocate an ID, the scheduler-grade message style, and the
  fixture/conformance contract CI enforces.
- Reports now state their own scope. Every run records a coverage manifest —
  which rules ran, and which were skipped and why (no companion GTFS feed,
  opt-in rule not enabled, or suppressed by `--ignore`) — so "no problems
  found" is qualified by what was actually checked. The JSON report carries it
  as an additive `coverage` block (report schema 1.2.0, documented in
  docs/report.schema.json), SARIF records it under `invocations`, and the
  text/Markdown/HTML reports add a one-line "Checks skipped: …" disclosure
  (plus a coverage footer on stamped Markdown). Library callers can get the
  manifest via the new `tods_validate.runner.run_with_coverage`; `run` is
  unchanged.
- Reference findings (TODS-E301/E303/E307/E308/E309/E310/E311/E312/E314) now
  carry structured `data` parameters — the broken value and what it references
  — and the SARIF output is enriched from the rule registry: each descriptor
  gains the rule's title, description, and spec link (`helpUri`), and each
  result carries its finding's structured data in `properties`.
- `tods-validate explain RULE_ID`: an offline command that prints a rule's full
  detail — description, spec citation, and a worked before/after example — with
  `--format markdown` for pasting into an issue. Every core rule (and the
  opt-in coverage/advisory rules) now ships a worked example, sourced from one
  registry (`tods_validate.rules.EXAMPLES`) that `explain`, `docs/rules.md`,
  and LSP hovers all render through the same `render_rule_detail()`, so the
  three cannot drift from each other.
- An optional `[severity]` table in `tods-validate.toml` remaps individual
  rule severities to encode local policy, with a hard honesty constraint:
  every remapped finding is disclosed in every report format (a "Local
  policy" block plus a per-finding "(spec: ORIGINAL)" note), and downgrading
  a rule the spec declares ERROR requires an explicit `acknowledged = true`.
  The report schema (1.2.0) documents `findings[].severity_original`. (#25)

Changed:

- The `--format html` report is now an explicit accessibility pass: it declares
  its language and a responsive viewport, uses `header`/`main` landmarks, gives
  the findings table a caption and column-scoped headers, and lightens the info
  severity color so all three severities clear WCAG AA contrast on the white
  background. The README gained a short accessibility statement.
- `tods-validate fix` now does more than trim whitespace: it also drops
  entirely-blank rows (the `,,,` lines that otherwise raise a wall of E201) and
  removes rows that are byte-identical to an earlier one (the TODS-W408 duplicate
  assignment). A row that shares a primary key but differs in any value is a real
  conflict and is left untouched for a human. Still a dry run by default.

Fixed:

- The reported tool version (`toolVersion` in the JSON/HTML reports and
  `--version`) is now read from the installed package metadata instead of a
  hand-edited constant that had drifted to `0.4.0`.
- The README and `merge`-recipe GitHub Action snippets now reference the current
  `@v0.6.0` instead of the stale `@v0.4.0` they were pinned at.
- TODS-W302 now also discloses when `vehicle_assignments.txt` references could
  not be checked: block_id resolution needs the companion feed's `trips.txt`
  and service_id resolution needs `calendar.txt`/`calendar_dates.txt`; when a
  used column's target file is missing, those checks used to no-op silently.

Security / process (2026-07-05 standards-conformance remediation):

- `make audit` (pip-audit) now audits the exact `uv.lock` pins minus the
  project itself, so a release version bump (a version that is not on PyPI
  until after the release publishes) cannot fail the gate; release tags are
  SSH-signed and `verify.yml` verifies them against the committed
  `.github/allowed_signers`.

- The release pipeline (`pypi-publish.yml`, `docker.yml`, `release-corpus.yml`)
  no longer publishes anything without first re-running the full gate set
  (`make verify`, new) at the tagged commit, plus a version-consistency check
  and an annotated/signed-tag check; a `verify-published` job now re-checks
  the published artifact's provenance/signature after publish.
- Fixed template-injection-shaped patterns in `action.yml` and the release
  workflows (`${{ }}` no longer interpolated directly into `run:` shells).
- Added Semgrep, CodeQL (`python` + `actions`), zizmor, gitleaks (pre-commit
  + CI), and a blocking `pip-audit` gate; adopted `uv` with a committed
  `uv.lock`; added a Trivy CVE scan and a digest-pinned base image to the
  Docker build; the Dockerfile now runs as a non-root user.
- Added a `README.md` Standards Conformance table, `docs/CONFORMANCE-GAPS.md`,
  `docs/RESPONSIBLE-TECH-AUDITS.md`, `DEFINITION_OF_DONE.md`,
  `.github/PULL_REQUEST_TEMPLATE.md`, `.github/CODEOWNERS`, and a vendored
  copy of the engineering standards this project is held to
  (`docs/standards/`).
- No user-facing behavior changed in this entry; see `docs/CONFORMANCE-GAPS.md`
  for the full list of what closed and what remains open.

## [0.6.0] - 2026-06-29

New surfaces for working with a feed live (`--watch`, browser playground),
acting on findings (`fix`), and sharing results (`stats --format markdown`,
conformance corpus), plus a new cross-feed operational check (TODS-W315).

Added:

- `tods-validate validate --watch` re-validates whenever the feed changes
  (polls the files), the cheap interim ahead of editor/LSP integration.
- A browser playground (`web/`) that validates a feed entirely in the browser
  via Pyodide, with no upload, deployable to GitHub Pages. The Python it calls
  is guarded by tests; the page itself needs a browser to verify.
- TODS-W315: a run event that works a trip end to end should start at the
  trip's first stop and end at its last stop (in the supplemented
  `stop_times.txt`); a mismatch is a warning, skipped for mid-trip events. The
  companion GTFS now ingests `stop_times`, so this checks an operational
  consistency constraint no GTFS-only validator can see.
- `tods-validate fix` applies safe, deterministic fixes — currently trimming the
  TODS-W206 whitespace padding that stops IDs from matching. It is a dry run by
  default and writes a cleaned, UTF-8/no-BOM package with `-o`.
- `tods-validate stats --format markdown` prints a feed profile (now including a
  date range and a file-presence list) suitable for pasting into an issue or a
  working-group thread.
- A downloadable conformance corpus, attached to each release: every fixture
  plus an `expectations.json` mapping each to the rule IDs it should produce, so
  another validator can run the suite without cloning the repo
  (`scripts/build_conformance_corpus.py`).

## [0.5.0] - 2026-06-22

Correctness fixes (no rule IDs changed), a runnable bundled sample feed with a
fixed quickstart, and a conformance check that runs the spec's own examples.

Fixed (no rule IDs changed):

- TODS-E204 now detects duplicate `vehicle_assignments` primary keys when the
  optional `service_id` is blank (the common case). Previously a blank optional
  key component silently suppressed the whole uniqueness check, so real
  duplicate keys passed clean and coalesced during `merge`.
- Time values with hours `>= 100:00:00` are now accepted (GTFS time has no upper
  hour bound). They previously raised a false TODS-E203 and were dropped from the
  time-based semantic checks (E401/E402/W403).
- TODS-E314 no longer fires on a `stop_times_supplement` row whose trip was
  deleted via `trips_supplement` (`TODS_delete=1`); the spec says such
  stop_times are ignored, not an error.
- Duplicate header columns now keep the first occurrence's value (matching the
  TODS-E105 message that the duplicate column is ignored) instead of letting a
  later duplicate column silently win.
- All-blank data rows (a stray `,,,` line past the header) are no longer
  silently dropped; their missing required values are now reported (TODS-E201).
- TODS-E205 (vehicle_assignments block ambiguity) is now marked as requiring a
  companion GTFS feed, so a TODS-only run reports it as unchecked instead of
  silently passing the check.

Other:

- Bundled a runnable sample feed at `examples/sample-feed/` and pointed the
  README quickstart at it, so a new install has something that passes on the
  first run. The GitHub Action now sets up Python explicitly.

## [0.4.0] - 2026-06-20

Distribution, reporting, and analysis surfaces. No rule IDs changed; the JSON
report gained fields (it is now `reportVersion` 1.1.0) without removing any.

Added:

- `tods-validate rules` lists the rule catalog from the tool itself
  (`--format json` for tooling, now including category, default-enabled, and
  spec-interpretation metadata).
- Published JSON Schema for the `--format json` report
  (docs/report.schema.json), enforced by tests.
- Dockerfile and a workflow publishing images to GHCR on each release.
- pre-commit hook definition (.pre-commit-hooks.yaml).
- New report formats: `--format sarif` (GitHub code-scanning / security
  dashboards) and `--format html` (a standalone, shareable report).
- JSON report now carries `toolVersion`, `reportVersion`, a per-rule
  `summary.byRule` breakdown, and a stable `location` pointer per finding.
- Text and Markdown reports group findings by rule, show the shortest path to a
  clean run, and add root-cause hints when one rule clusters.
- New flags on `validate`: `--enable` (opt-in rules/categories), `--profile`
  (default/strict/lenient presets), `--spec-version`, `--baseline` (fail only
  on findings new since a previous JSON report), `--max-findings`, `--quiet`,
  `--stamp` (citable Markdown footer), and `--encoding`.
- New subcommands: `diff` (compare two feeds), `batch` (validate many feeds
  with a roll-up table), `stats` (descriptive feed metrics), and `anonymize`
  (pseudonymize person-identifying fields).
- `merge` now writes a `merge-report.json` manifest alongside the merged feed.
- The GitHub Action exposes `error-count`, `warning-count`, and `info-count`
  outputs and accepts an `enable` input.
- New opt-in rules: TODS-I501 / TODS-I502 (coverage) and TODS-I601 (advisory).
- Public Python API: `from tods_validate import validate_feed`.
- Input-safety hardening of zip ingestion (zip-bomb and path-traversal
  defenses, size limits) and a `SECURITY.md`.
- `scripts/benchmark.py` for throughput measurement on large synthetic feeds.

## [0.3.0] - 2026-06-12

- New `merge` subcommand writes the "TODS-Supplemented GTFS" dataset (the
  GTFS feed after supplement rows are applied) to a directory or .zip, with
  per-file counts of updated, added, and deleted rows. The merged feed can
  then be checked with MobilityData's gtfs-validator.
- New rule TODS-E314: a supplement row references a route, service, trip, or
  stop that does not exist in the supplemented feed.
- The CLI now has explicit `validate` and `merge` subcommands;
  `tods-validate PATH` without a subcommand still validates, so existing
  invocations and the GitHub Action are unaffected.

## [0.2.0] - 2026-06-12

- `--ignore RULE_ID` (repeatable) suppresses specific rules.
- Optional `tods-validate.toml` configuration file (`ignore`, `fail-on`),
  discovered in the working directory or passed with `--config`.
- `--format markdown`: a report suitable for pasting into an issue or a
  working-group thread.

## [0.1.0] - 2026-06-12

First release: 35 checks against TODS v2.1.0 covering file structure, field
values, references (including into the companion GTFS feed after supplements
are applied), and schedule semantics. CLI with text, JSON, and GitHub
annotation output, plus a composite GitHub Action.
