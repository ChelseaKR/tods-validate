# Conformance gaps

A dated ledger of what is open against `docs/standards/` (vendored
2026-08-09, portfolio-standards v2.0.0), referenced from the README
Standards Conformance table. Each heading matches a row in that table.

**Why this file instead of GitHub issues:** `DOCUMENTATION-STANDARD.md`
DOC-13 wants every gap linked to an open issue (`Applies — gap tracked in
#NN`). This remediation pass deliberately did not open GitHub issues —
opening real, publicly visible issues is a live action with effects outside
this repo's files, which a same-day automated remediation pass should not
take without the maintainer's explicit go-ahead. This file is the substitute:
every open item below is a candidate `gh issue create` away from becoming a
real tracked issue; once you open one, swap that row's link in the README
table and here.

Last regenerated: 2026-07-05. Updated 2026-08-09 for the four standards added
in portfolio-standards v2.0.0; earlier ADR-log closures remain recorded in the
code-quality and documentation sections.

## ai-development-measurement

**Closed 2026-08-27.** `docs/roadmap.md`'s metrics ledger now carries the
`AI-DEV-MEASUREMENT: APPLIES` declaration the standard's section 8 asks for,
with the diagnostic share measured (32 of 160 commits on `main` carry a
`Co-Authored-By: Claude` trailer) and stated as diagnostic-only, never gating.
The two quality-debt counterweights the standard pairs with throughput, revert
rate and unreviewed-merge rate, are BASELINE rows each carrying a dated
graduation decision of **2026-11-30**, because a BASELINE row without one is a
conformance failure in its own right. The quarterly review that reads them is
[`docs/DORA-2026-Q3.md`](DORA-2026-Q3.md), run jointly with QM-11 per that
standard's own cadence line.

AI-product evaluation remains separately N/A because the validator itself has
no model runtime.

## data-governance

**Current boundary:** validation is local and process-lifetime only;
`docs/RESPONSIBLE-TECH-AUDITS.md` records that feeds are not retained.

**Closed 2026-08-27.** Five sources are classified under the v2.0.0 tiers in
[`docs/data/sources.json`](data/sources.json), each with a card in
[`docs/data/`](data/): the spec transcription, the conformance corpus, the
example feed, and the generated benchmark packages at **L1**; a user's own feed
at **L3**. `scripts/check_data_cards.py` is the AUTO-GATE DG-01 asks for and
fails in either direction, on a declared source with no card and on a card with
no declared source, and additionally when a card and the list disagree about a
tier or when a source's paths no longer exist.

The user-feed card is the one that needed care, and it is written to *decline*
ownership rather than assert it: a feed is the input to a local validator that
holds it for one process lifetime and writes nothing back, so this project has
no standing to state a licence, a refresh cadence, or a retention line over an
agency's records. The card names the three L3 fields (`employee_id`,
`license_plate`, `vehicle_label`), points at the existing DPIA-lite, and records
that its "not retained" line stops being true by construction the day #76
succeeds.

## observability

**Current boundary:** Tier C, per `OBSERVABILITY-STANDARD.md` §0. OTel tracing
is out of scope and the README's `## Observability` section declares it: there
is no network surface to trace, and the tool is offline by design.

**Still open (found 2026-08-28):** Tier C also asks for "an opt-in
`--log-format json` flag backed by `structlog`" (`OBSERVABILITY-STANDARD.md`
§3, and `QUALITY-AND-METRICS-STANDARD.md` line 190 restates it as a must). The
flag does not exist anywhere in `src/`. Until today the README reproduced the
standard's own declaration sentence verbatim, ending "Opt-in `--log-format
json` only", which reads as a statement that the flag is there; nothing in
this ledger recorded otherwise, and no gate compared the sentence to the CLI.
`tests/test_readme_claims.py` now does, so the claim cannot return without the
flag returning with it.

Two ways to close it, and the choice is a product decision rather than a
remediation:

1. **Restate the tier.** Nothing under `src/` imports `logging`; the package
   emits no log records at all, so there is no stream for a format flag to
   select. The machine-readable surface here is the *report* (`--format json`,
   `--format sarif`, `docs/report.schema.json`), which is a different artifact
   from a log. If the standard's intent is "a machine can consume this tool's
   output", that is already met, and the row should say so in those words
   rather than by naming a flag.
2. **Implement it.** `structlog` would be a second runtime dependency for a
   tool that deliberately has one (`click`), added to satisfy a sentence
   rather than a user. Weaker unless an operator asks for parseable progress
   logs on large feeds.

Not on the v1.0.0 critical path either way: `--log-format` does not appear in
`docs/v1-contract-candidate.json`, so adding it later is an additive minor
release. What was on the critical path was shipping v1.0.0 with the README
claiming it.

## incident-response

**Closed 2026-08-27** as a checked contract.
[`.github/labels.yml`](../.github/labels.yml) declares the `incident`, `sev1`
to `sev4`, and `deploy-caused` convention (IR-02/IR-04/IR-17);
[`docs/incidents/TEMPLATE.md`](incidents/TEMPLATE.md) carries every section
IR-07 names; and [`docs/runbooks/secret-exposure.md`](runbooks/secret-exposure.md)
works IR-10 to IR-14 in order, rotate before revoke before scope before the
history decision before closing the entry point, with the per-credential
revocation table this repository would actually need.

`scripts/check_incident_contract.py` is the gate, in `make verify` and in the
`stewardship` CI job. Two of its four checks (IR-15, no wildcard `git add` in
unattended automation; IR-16, no scripted commit without a secret scan) were
already clean when they landed, so each prints what it scanned rather than only
whether it found anything: a guard with nothing to catch and a guard that is
not looking otherwise render identically, and this repository has shipped the
second kind before.

**Still open:** the labels are declared, not created. `gh label list` on
2026-08-27 showed none of the six exist on the repository; the create command
is in the header of `.github/labels.yml`. IR-02's live check (every open
`incident` issue carries exactly one `sevN`) needs those labels and a scheduled
run against the API, so it is not wired yet.

## performance

**Current evidence:** `scripts/benchmark.py`, `scripts/generate_feed.py`, and
`docs/BENCHMARKS.md` provide repeatable CLI throughput measurements.

**Closed:** the benchmark is a merge-blocking regression gate. QM-02 landed
`scripts/check_perf_budget.py` behind the `perf` job in `ci.yml` (and `make
perf-check` locally), which compares 50,000-trip throughput against
`perf/baseline.json` and fails past its regression factor. See the
quality-and-metrics section for the full description; this section previously
still recorded that gate as open after it had shipped.

**Still open:** the shipped HTML surfaces have no committed Lighthouse/bundle
baseline.

## code-quality

**Closed today:** ruff floor raised to `>=0.15`, mypy to `>=1.18`;
`.pre-commit-config.yaml` revs bumped (ruff v0.15.20, mypy v2.1.0) and a
gitleaks hook added; pytest strict flags
(`--strict-markers --strict-config --import-mode=importlib`, plus
`pythonpath = ["tests"]` so the import-mode change doesn't break the
existing `from conftest import ...` test style); coverage floor mirrored
into `pyproject.toml` (`[tool.coverage.report] fail_under = 90`) and branch
coverage turned on (`branch = true`, suite clears 90.98%); `ruff` `S`
(bandit-equivalent) and `C901` (mccabe, `max-complexity = 10`) added to the
lint select, with every finding fixed or justified (`assert` findings in
`rules/{references,semantics,coverage}.py` are internal type-narrowing after
the rule engine's own `needs_gtfs` gate, not a security control — justified
per-file in `pyproject.toml`; complexity findings carry a coded
`# noqa: C901` pointing back here); `uv` adopted — `uv.lock` committed, CI
runs `uv sync --frozen` (lockfile-drift check for free); `CODEOWNERS` added
(`.github/CODEOWNERS`).

**Closed 2026-07-09:** the ADR log exists — `docs/adr/0000` (the practice)
plus backfills 0001 (3.11 floor, closing **CQ-44/45**'s first item and, with
the committed `.python-version` pinned to CI's 3.12 gate version, **CQ-01**
via a declared deviation), 0002 (i18n N/A), 0003 (`editor/vscode` nesting,
closing **CQ-26**), 0004 (rules-as-registry), 0005 (uv/lockfile adoption).

**Updated 2026-08-21:** `requires-python` raised to `>=3.12` (#72), closing
**CQ-01** directly against the standard's stated floor instead of via a
declared deviation. `docs/adr/0006-python-312-floor.md` supersedes 0001;
0001 stays in the log as the record of why the deviation existed from
2026-07-09 to 2026-08-21.

**Updated 2026-08-27:** **CQ-27** closed. Development dependencies moved from
the `dev` extra to a PEP 735 `[dependency-groups]` table (#145), so no linter,
type checker, or test runner is installable as an extra of the published
distribution. `tests/test_packaging.py` is the AUTO-GATE the standard's CQ-27
row asks for: it fails if development tooling reappears under
`[project.optional-dependencies]`.

**Still open:**
- **CQ-37–43** — no committed branch-ruleset artifact (PR-required, stale-
  review dismissal, required status checks, linear history, no
  force-push, no admin bypass). ⛔ **Needs a live GitHub Settings change**
  this remediation pass intentionally did not make (see ci-cd below for the
  exact ruleset and the reasoning).
- **CQ-47** — mutation kill-rate on the rules engine is **62.2%** as of
  2026-08-27, below the 70% target. Two things changed this pass. The rate was
  re-measured, because the ~65% figure in `docs/mutation-testing.md` was
  recorded against 280 mutants and the engine has since grown to 330: it was
  really 57.6%, and killing twelve survivors in one under-tested helper took it
  to 62.2%. And the weekly workflow can now fail. It carried
  `continue-on-error: true` on the job plus `|| true` on every step, so a rate
  that halved rendered identically to one that did not move;
  `scripts/check_mutation_ratchet.py` now fails it below the floor committed in
  `perf/mutation-baseline.json`. Still open against the target; ratchet, don't
  jump.

## security-and-supply-chain

**Closed today:** Semgrep (`semgrep ci --config auto`, `.github/workflows/semgrep.yml`)
and CodeQL (`python` + `actions` languages, `.github/workflows/codeql.yml`)
added — both ran clean locally against the post-remediation tree. Semgrep's
first real run (before other fixes landed) caught and this pass fixed: a
Dockerfile running as root (added a non-root `USER`), a Dependabot config
missing a cooldown window (`.github/dependabot.yml`), and a missing
Subresource-Integrity hash on the playground's CDN script
(`web/index.html`). gitleaks added as a pre-commit hook and a CI job
(`ci.yml` `secrets` job; installs the CLI directly, checksum-verified,
rather than the license-gated `gitleaks/gitleaks-action`) — no
`continue-on-error`. `pip-audit --strict` added as a blocking CI job and
Makefile target, no mute pattern. `uv.lock` committed and scanned via the
same `pip-audit` gate (dependency versions now come from a committed,
drift-checked lockfile, not ambient resolution). Trivy image scan
(`CRITICAL,HIGH`, blocking, before push) added to `docker.yml`; the base
image is now digest-pinned
(`python:3.13-slim@sha256:eb43ff...` — verified against the live Docker Hub
manifest index at pin time, not fabricated). SRI hash added to the Pyodide
CDN `<script>` in `web/index.html` (computed from the actual fetched file).

**Still open:**
- **SEC-01/SEC-40** — `docs/RESPONSIBLE-TECH-AUDITS.md` was added this
  pass with a Security audit section, but it explicitly declines to assign
  a numeric ASVS level (the tool has no auth/session surface for most ASVS
  controls to apply to) rather than assign one that would overstate rigor.
  Revisit if this tool ever grows a network-facing surface.
- **SEC-15** — no ruleset blocking on Dependabot alerts ≥ CVSS 7. ⛔ Same
  live-GitHub-Settings constraint as CQ-37–43.
- **SEC-19** — no scheduled full-history TruffleHog run (the plan lists
  this as an *optional* third gate on top of gitleaks pre-commit + CI,
  which are both in place). Not added this pass; low incremental value
  over the two gitleaks gates already running.
- **SEC-35–38 / CICD-03** — `.github/workflows/scorecard.yml` was added
  (OpenSSF Scorecard, weekly + push-to-main, SARIF uploaded to code
  scanning), but it has never actually run — that requires a live push to
  GitHub, which this remediation pass did not do. Its Branch-Protection and
  Token-Permissions sub-scores will also stay low until the ruleset above
  is enabled. ⛔ Commit a dated `docs/audits/scorecard-YYYY-MM.md` report
  after the workflow has run at least once against the real repo.

## ci-cd

**Closed today:** write-scope permissions moved from workflow level to job
level in `docker.yml`, `release-corpus.yml`, and `pages.yml` (previously
only `pypi-publish.yml` did this correctly). Concurrency groups added to
`docker.yml` and `release-corpus.yml` (previously only `pypi-publish.yml`
and `pages.yml` had one). zizmor added
(`.github/workflows/zizmor.yml`, triggered on any PR touching
`.github/workflows/**` or `action.yml`, blocking at `--min-severity high`);
the full workflow set is zizmor-clean as of this pass (0 findings at the
default "regular" persona; 20 informational/low findings remain under
`--persona=pedantic`, none of which the standard requires blocking on).
CodeQL's `actions` language now covers the workflow set too. Template-
injection fixed everywhere it existed: `action.yml` (`inputs.*` and
`github.action_path`), `pypi-publish.yml` and `release-corpus.yml`
(`github.event.release.tag_name`) — all now routed through `env:` rather
than spliced into `run:` shell text. `make verify`
(`Makefile`) now exists and CI's `lint`/`test`/`audit` jobs call its targets
directly (`make lint`, `make format`, `make typecheck`, `make test`, `make
audit`), so CI-vs-local drift is structural, not a copy-paste discipline.
`CONTRIBUTING.md` now says `make verify` and links `docs/standards/`.

**Still open:**
- **CICD-03/11-18** — ✅ **closed 2026-09-01.** The ruleset `protect-main`
  (id 18752857) is active on the default branch, and
  [`docs/rulesets/main.json`](rulesets/main.json) is the export of it.
  `tests/test_branch_ruleset.py` keeps its required-status-check list in step
  with the checks the workflows actually report.

  Applying it corrected two errors in this entry. The update endpoint is
  `PUT /repos/{owner}/{repo}/rulesets/{id}`; the `POST` form named here
  creates a second ruleset, and against a live ruleset under a different name
  that is what it would have done. And the live ruleset was already active
  under the name `protect-main` while this entry said none was enabled, so the
  committed file described a ruleset that did not exist alongside a real one
  nothing was comparing it to. Re-export after any change; see
  [`docs/rulesets/README.md`](rulesets/README.md).

  What is still open is narrower than the row it replaces: nothing compares
  the committed export with GitHub. The test checks the file against the
  workflows, which is the drift that happens on its own, but a settings change
  made in the UI would not show up in any diff.

  Writing the prose down as a file found a defect in the prose. This entry
  previously said to require `zizmor` among the status checks. `zizmor.yml` is
  path-filtered on `pull_request`, so on a pull request touching no workflow
  file the check never reports and the merge could never happen. It is
  excluded, with a test that keeps it excluded until the filter goes away.

  Solo-maintainer self-review remains a structural limitation no ruleset fixes
  by itself (`CODEOWNERS` is ready for when a second maintainer joins), and
  with `bypass_actors` empty, expect to need a recorded bypass to merge until
  there is a second person.
- **CICD-06** — ✅ **closed 2026-09-01.** Both halves are set.
  `pypi-publish.yml`'s `publish` job runs in a `pypi` environment, asserted by
  `tests/test_publish_scoping.py`, and the trusted publisher on PyPI now names
  that environment instead of accepting any. The subject the standard asks for,
  `repo:ChelseaKR/tods-validate:environment:pypi`, is the one PyPI checks.

  PyPI publishers are immutable, so this was an add-then-remove rather than an
  edit: the scoped publisher was created alongside the `(Any)` one and the old
  entry deleted after. Doing it in that order leaves no window in which a
  release has no publisher to match.

  The `pypi` environment was created explicitly rather than left to appear on
  first use, so it can carry rules: its deployment branch policy admits the
  tag pattern `v*` and nothing else. A publish therefore has to originate from
  a version tag, which is what the release path already does, and a
  `workflow_dispatch` run from a branch is refused at the job rather than
  after it has built something. There is deliberately no required-reviewer
  rule; on a solo repository that would stall every release waiting for an
  approval only the person who triggered it could give.

  One thing this close does not claim. Nothing in this repository can read
  PyPI's project settings, so that half is recorded on the maintainer's word,
  and the first release after this date is what actually demonstrates it. If
  that release fails to publish, this is the entry to reopen.
- **CICD-29** — a Metrics table now exists (`docs/roadmap.md` §Metrics
  ledger, added this pass), so this is substantially addressed; revisit
  whether every optional CI stage is declared applicable/N/A there as the
  repo evolves.

## release-and-versioning

**Closed today:** the release-integrity hole (REL-14/15/16) is closed —
`.github/workflows/verify.yml` (a reusable `workflow_call` workflow running
`make verify` plus version-consistency and tag-signature checks) is now a
required `needs:` dependency of `publish` in `pypi-publish.yml`,
`build-push` in `docker.yml`, and `corpus` in `release-corpus.yml`. None of
the three can run without it passing. A `verify-published` job was added to
both `pypi-publish.yml` (re-downloads the published sdist/wheel from PyPI
and checks its build-provenance attestation with `gh attestation verify`)
and `docker.yml` (re-verifies the cosign signature on the pushed digest) —
so "the job exited 0" now means the published artifact was independently
re-checked, not just that upload didn't error. Version-consistency
(tag == `pyproject.toml` version == `CITATION.cff` version, and
`CHANGELOG.md` has a matching dated section) and an annotated+signed-tag
check (REL-08) are both wired into `verify.yml`, gated on `inputs.tag != ''`
so they only run for a real release event, never for `workflow_dispatch`
smoke-runs or PR-time `make verify`. `SECURITY.md` now states a
supported-versions policy (latest 0.x only, pre-1.0) and a concrete
response SLA (3 business days ack; 30/90-day fix-or-mitigate by severity).

**Still open:**
- **REL-08, historical tags** — `v0.1.0` through `v0.6.0` are lightweight,
  unsigned tags, created before this pass. `verify.yml`'s new check is a
  forward-fix only: it will fail the *next* release unless that tag is
  created annotated and signed. **⛔ Manual action for the next release:**
  `git tag -s vX.Y.Z -m "release: vX.Y.Z"` (requires a configured GPG or SSH
  signing key) instead of `git tag vX.Y.Z`, then push the tag before
  creating the GitHub release. Since v0.7.0 release tags are SSH-signed with
  the key listed in `.github/allowed_signers`, and `verify.yml` verifies the
  signature against that file. The historical tags were **not** rewritten
  (rewriting published tags retroactively is destructive to anyone who
  already fetched them, and out of scope for a file-edit-only remediation
  pass).
- **Stray `v0` tag** — noted in the audit as a leftover. **⛔ Not deleted**
  by this pass (deleting a tag, even a stray one, is a git-history-editing
  action the ground rules for this remediation asked to avoid unless
  explicitly requested). To remove it yourself: `git tag -d v0` locally,
  then `git push origin :refs/tags/v0` if it was ever pushed.
- **DOC-07/REL-10, CHANGELOG heading format** — still `## vX.Y.Z - YYYY-MM-DD`,
  not `## [X.Y.Z] - YYYY-MM-DD`. The version-consistency grep added to
  `verify.yml` was written to match the *existing* format
  (`^## v?X\.Y\.Z( |$)`) rather than forcing a rename of six released
  changelog sections for a purely cosmetic standardization. Low priority
  polish (P3); revisit if/when CHANGELOG headings are touched anyway.
- **REL-20** — CHANGELOG-as-release-notes is still manual (not automated in
  the release workflow). Unchanged this pass.

## accessibility

**Closed 2026-07-16:** a blocking `pa11y-ci` gate now runs axe-core and
HTML_CodeSniffer at WCAG 2.1 AA against both the browser playground and a
fixture-generated HTML report. It found and fixed the report's invalid ARIA
labeling on scrollable table containers, and added the playground file-input
label, dark-mode contrast variables, and explicit focus treatment. The locked
npm dependency tree is checked at the same HIGH floor by a separate gate,
`make npm-audit`. `make verify` and the reusable release verifier both include
both gates.

**Corrected 2026-08-15:** the npm dependency audit used to be the first line of
the `a11y` recipe. Between 2026-07-16 and 2026-08-15 an unpatched HIGH advisory
in the pa11y-ci toolchain (GHSA-jmr9-qjv8-65gv, waivers.yml WVR-001) failed
that line, so `npm run a11y` never executed and the accessibility gate performed
no accessibility check at all while reporting itself red for a dependency
reason. The two are independent gates now, each reporting its own result, and
`make verify` runs every gate rather than stopping at the first failure.

The Pyodide CDN script in `web/index.html` also retains its SRI hash, closing
the supply-chain-flavored A11Y-17 note from the original audit.

**Updated 2026-08-27:** [`docs/a11y/STATEMENT.md`](a11y/STATEMENT.md) now
exists: dated, carried by the `docs-check` currency gate, naming **WCAG 2.1
Level AA** as the target and deliberately making no conformance *claim*,
because the only evaluation run is automated. It tables every surface against
what has actually been checked. Writing that table found an unaudited surface:
the 44 rule-catalog pages `pages.yml` publishes had never had a runner pointed
at them. They are in the blocking gate now, and entering it they failed with
141 colour-contrast errors and 43 link-distinguishability errors, both from one
shared stylesheet that declared `color-scheme: light dark` and then painted
neither scheme. Fixed; all four audited URLs pass.

**Still open:** no Lighthouse pass; no committed screen-reader/keyboard
walkthrough artifact; no ACR/VPAT; the *booted* playground state is still
unaudited, because the gate loads `?a11y-static=1`. Automated checks are a
floor, not evidence of screen-reader usability. The next accessibility artifact
should therefore be the manual keyboard and assistive-technology walkthrough,
not another scanner.

**2026-08-21:** an attempt at that walkthrough (#74) could not proceed --
no browser tool was available in that session, so it recorded a static
source review instead (`docs/a11y/2026-08-21-automated-only-not-a-substitute.md`,
explicitly not a substitute for the real thing) and surfaced a live-site
blocker: `web/index.html` pins `micropip.install("tods-validate==0.9.1")`,
and PyPI's latest published version is still 0.9.0 (v0.9.1 was tagged and
signed but never actually released -- #136). If that holds in a real
browser, the deployed playground does not currently boot at all, which
would block the walkthrough itself until #136 is resolved.

## quality-and-metrics

**Closed today:** `DEFINITION_OF_DONE.md` (root) and
`.github/PULL_REQUEST_TEMPLATE.md` added; `docs/roadmap.md` gained a
Metrics ledger table and a release checklist (QM-17).

QM-02 closed: the perf budget is a gate. `scripts/check_perf_budget.py` (the
`perf` job in `ci.yml`, `make perf-check` locally) validates a 50,000-trip
synthetic feed and fails when throughput regresses past
`perf/baseline.json`'s factor. Throughput is rows per CPU-second, not wall
clock, so a busy shared runner does not read as a regression; the baseline is
recorded from the CI runner's machine class, and the check fails rather than
passes when it has no baseline to compare against.

**Updated 2026-08-27:** QM-11 closed for this quarter.
[`docs/DORA-2026-Q3.md`](DORA-2026-Q3.md) is the first review, with
[`DORA-2026-Q3.json`](DORA-2026-Q3.json) as the machine-readable snapshot and
`scripts/delivery_metrics.py` as the collector. Cadence: quarterly, next due
**2026-11-30**, carried by the `docs-check` currency gate so the document
cannot drift without saying so.

Three of the five DORA metrics come back breached and one comes back N/A, which
is the point of measuring rather than a reason not to publish: deployment
frequency 1 per 7.9 days against a weekly floor, lead-time p90 131h against a
1-day floor, change fail rate 20% against 15%, and rework rate N/A because zero
reverts in 160 commits leaves no ratio to compute. The collector writes `null`
with a reason rather than `0` for anything it cannot measure, and
`tests/test_delivery_metrics.py` pins that, because the standard says the
collector "never fabricates a zero" and a 0% change fail rate that means "we
counted nothing" reads exactly like a good one.

## documentation

**Closed today:** `docs/standards/` vendored (pinned copy +
`.standards-version`, via the portfolio's `vendor-standards.sh`; `renovate.json`
already had the customManager watching that path, so freshness automation
was pre-wired and needed no change). `SECURITY.md` gained supported-versions
+ SLA. `CONTRIBUTING.md` now references `make verify` and `docs/standards/`.
The README Standards Conformance table (this file's parent) now exists.
README status line (`Status: Beta`) added.

**Closed 2026-07-09:** DOC-04/05 — `docs/adr/` exists (0000 + backfills
0001–0005; same closure as CQ-44/45 above).

**Closed 2026-08-04:** DOC-08 — a `citation` job (`ci.yml`, folded into
`make verify`) runs `cffconvert --validate` against `CITATION.cff` on every
push and PR, via `uvx` so it needs no addition to the dev dependency set.
Catches malformed citation metadata before a release ships it; the existing
release-checklist eyeball check (tag/pyproject/CITATION.cff version
agreement) still lives in `verify.yml`'s REL-03 step and is unaffected.

**Closed 2026-08-14:** DOC-15 — `docs/getting-started.md` and `docs/api.md`
carry `Last verified:` and `Recheck cadence:` lines per
`DOCUMENTATION-STANDARD.md` §6.5, stamped only after every command, exit code,
signature, and member on those pages was actually run against the current build.
`scripts/check_doc_currency.py` (folded into `make docs-check`, so the existing
`docs-drift` CI job runs it on every pull request) makes the claim falsifiable:
each stamp records a fingerprint of the page it describes, and the check fails
when the page changes without a fresh verification. What it cannot check is
whether a verification was any good — that stays a REVIEW gate, which is what
the cadence line is for.

**Still open:** nothing in this section.

## responsible-tech

**Closed today:** `docs/RESPONSIBLE-TECH-AUDITS.md` added, instantiating the
full A–F applicability matrix (B and AI-EVALUATION declared N/A with
reasons; A/C/D/F filled in with findings, commitments, and enforcement
citing what already existed in `SECURITY.md`/`CONTRIBUTING.md` plus what
this pass added) and a dated residual-risk register.

**Still open:** this is a first pass, not a steady-state practice yet —
RTF-08 wants it regenerated at every release, which has not yet been
exercised across a real release cycle. Revisit and re-date at the next tag.
