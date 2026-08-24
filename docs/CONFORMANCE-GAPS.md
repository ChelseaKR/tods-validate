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

**Still open:** the repository records delivery and quality metrics in
`docs/roadmap.md`, but it has no dated AI-development diagnostic baseline or
graduation decision. AI-product evaluation remains separately N/A because the
validator itself has no model runtime.

## data-governance

**Current boundary:** validation is local and process-lifetime only;
`docs/RESPONSIBLE-TECH-AUDITS.md` records that feeds are not retained.

**Still open:** classify bundled, fixture, and user-supplied feed data under the
v2.0.0 tiers and add a mechanically checked data-card/source inventory without
claiming ownership of users' input feeds.

## incident-response

**Still open:** security reporting and release recovery exist, but the v2.0.0
`incident`/`sevN` label convention, committed postmortem template, and
secret-exposure response runbook have not been adopted as one checked contract.

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

**Updated 2026-08-24:** dev dependencies migrated from
`[project.optional-dependencies].dev` to PEP 735 `[dependency-groups].dev` (#145),
closing **CQ-27**. CI workflows, Makefile, and docs updated to `uv sync --group dev`.

**Still open:**
- **CQ-37–43** — no committed branch-ruleset artifact (PR-required, stale-
  review dismissal, required status checks, linear history, no
  force-push, no admin bypass). ⛔ **Needs a live GitHub Settings change**
  this remediation pass intentionally did not make (see ci-cd below for the
  exact ruleset and the reasoning).
- **CQ-47** — mutation kill-rate on the rules engine is ~65% (advisory,
  weekly), below the 70% target. Unchanged this pass; ratchet, don't jump.

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
- **CICD-03/11-18** — ⛔ **the branch-ruleset gap.** No committed ruleset
  artifact exists, and this pass did not enable one live. This needs an
  interactive decision on GitHub (Settings → Rules → Rulesets, or `gh api
  repos/ChelseaKR/tods-validate/rulesets` with a write payload), which the
  ground rules for this remediation pass explicitly excluded (branch
  protection is a listed no-write-API item). **What to do:** create a
  ruleset targeting `main` with: require a pull request (≥1 approval),
  dismiss stale reviews, require status checks in strict mode (name every
  `ci.yml` job plus `zizmor`, `Semgrep`, `CodeQL`/`analyze`), require
  CODEOWNERS review, require linear history, block force-pushes, no admin
  bypass. Export the resulting ruleset JSON
  (`gh api repos/ChelseaKR/tods-validate/rulesets/<id>`) and commit it to
  `docs/rulesets/main.json` so it's an artifact, not tribal knowledge. Note
  honestly once done: solo-maintainer self-review remains a structural
  limitation no ruleset fixes by itself (`CODEOWNERS`, added this pass, is
  ready for when a second maintainer joins).
- **CICD-06** — the PyPI trusted-publisher scoping leaves the GitHub
  Environment blank (`pypi-publish.yml` comment already notes this). ⛔
  Fixing it requires creating a `pypi` GitHub Environment (Settings →
  Environments) *and* updating the trusted-publisher config on PyPI's
  project settings page to match — both are live, interactive, and
  specific to the maintainer's PyPI account. Not done this pass.
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

**Still open:** no Lighthouse pass; no committed screen-reader/keyboard
walkthrough artifact; no ACR/VPAT; the README `## Accessibility` section is a
genuine, specific statement but is not yet promoted to a dated
`docs/a11y/STATEMENT.md` with a named WCAG conformance target. Automated checks
are a floor, not evidence of screen-reader usability. The next accessibility
artifact should therefore be the manual keyboard and assistive-technology
walkthrough, not another scanner.

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

**Still open:** QM-11 (DORA quarterly review — no cadence established yet).

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
