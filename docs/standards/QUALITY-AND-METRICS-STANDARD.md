# Quality & Metrics Standard

This is the canonical definition of the quality attributes every project targets and the mechanism by which their metrics are **enforced** rather than merely measured. It is the **spine** of `STANDARDS/`: it owns the vocabulary (ISO/IEC 25010:2023), the delivery-health backbone (DORA), and the merge-gate model. The cross-cutting depth for each domain lives in a dedicated sibling standard — this document **points to** them and does not restate them.

Projects override the *values* (a hobby logger needs less than a public benefits tool) but not the *structure*.

> **On "100% enforcement."** A metric is enforced when failing it **blocks the merge** — not when a dashboard shows it red after the fact. Everything mechanically checkable is a hard CI gate; everything requiring judgment (genuine bias, accessibility-of-experience, ethical edge cases) remains a *required human sign-off gate* with a checklist and a dated durable artifact (committed by default; an authenticated current-head PR/release record only where the owning standard authorizes it). An owning domain standard may authorize a narrowly scoped, truth-labeled **provisional release** from synthetic evidence plus maintainer residual-risk acceptance while an experiential REVIEW-GATE remains open. That disposition does not satisfy or reclassify the gate, establish conformance, or create a third gate type. Accessibility's bounded pathway is defined in `ACCESSIBILITY-STANDARD.md` §2.0.

## Sibling standards (reference, don't repeat)

This document is the index. Each row below is enforced **in** the named standard; the cell here states only the one-line interface this spine depends on.

| Domain | Owning standard | Interface this spine depends on |
|--------|-----------------|---------------------------------|
| Code quality / toolchain | `CODE-QUALITY-STANDARD.md` | ruff ≥0.15.x, mypy `--strict`, branch coverage ≥85% (libs ≥90%), single `pyproject.toml`, `uv lock --check` then `uv sync --frozen`, `make verify` byte-equal to CI |
| CI/CD hardening | `CI-CD-STANDARD.md` | top-level `permissions: contents: read`, OIDC-only cloud creds, `zizmor` on workflow PRs, concurrency groups, committed CODEOWNERS + branch ruleset |
| Security & supply chain | `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | ASVS 5.0 L2; SHA-pinned actions; Semgrep/CodeQL/gitleaks/pip-audit/Trivy blocking on HIGH+CRITICAL; SBOM + cosign + SLSA L2 |
| Release & versioning | `RELEASE-AND-VERSIONING-STANDARD.md` | SemVer 2.0.0; signed tags; CHANGELOG entry per release; trusted-main dispatch re-runs verification at the selected tag; Trusted Publishing (OIDC, no stored tokens); version-consistency gate |
| Observability | `OBSERVABILITY-STANDARD.md` | structured JSON logs, OTel spans, `/livez` + `/readyz`, SLOs + burn-rate alerts (tiered by deployment shape) |
| Performance | `PERFORMANCE-STANDARD.md` | k6 p95 budgets + Lighthouse-CI score/bundle budgets asserted against committed `perf/baseline.json`; >10% regression fails without product-owner sign-off; copyable `perf/` reference dir |
| Accessibility | `ACCESSIBILITY-STANDARD.md` | WCAG 2.2 AA floor; axe zero critical/serious/moderate; pa11y **blocking**; screen-reader walkthrough + ACR per release; provisional solo-maintainer disposition in §2.0 |
| Internationalization | `INTERNATIONALIZATION-STANDARD.md` | portable catalogs (gettext `.po` / MF2-ICU); EN/ES key-parity + placeholder-parity + pseudolocale gates |
| AI evaluation | `AI-EVALUATION-STANDARD.md` | RAGAS faithfulness ≥0.80; hallucination ≤5%; Garak/Promptfoo OWASP-LLM red-team; judge-calibration agreement ≥0.80 / κ ≥0.60 |
| Incident response | `INCIDENT-RESPONSE-STANDARD.md` | severity ladder (SEV1–4); `incident`/`sevN` labels feeding the DORA rows below; committed postmortem within 7 days (SEV1/2); secret-leak runbook |
| Data governance | `DATA-GOVERNANCE-STANDARD.md` | data classification (L0–L3); data cards + lineage per ingest source; retention schedules; backup/DR for local-first repos; license/provenance for civic data |

**Rule:** a repo records project-specific *values and findings* (its measured coverage, its ACR rows, its red-team results) in its own `ROADMAP.md` / audit artifacts. It does **not** restate the rigor — it cites the standard.

---

## The enforcement model (two gate types; provisional release is not a gate type)

Every control in every standard is exactly one of:

- **AUTO-GATE** — mechanically checkable, **merge-blocking in CI**, required status check under branch protection. Example: `pytest --cov-fail-under=85`.
- **REVIEW-GATE** — requires human judgment, paired with **(a)** a checklist item in the PR template and **(b)** a dated durable artifact (normally committed; authenticated current-head PR/release metadata only where explicitly authorized). The transition is blocked until the box is checked and the artifact is in the diff or linked, unless the owning domain standard explicitly authorizes a truth-labeled provisional release while leaving that box open.

A control that is "run but `|| true`," "advisory," or "on the roadmap" is a **defect**. The owning standard must make the check blocking or classify it honestly as a non-gate; project-specific findings stay in the private remediation registry.

---

## Falsifiability: observed failing, or it is not a gate

**A claim that cannot come out differently is not a measurement.** A gate nobody has
ever seen fail is indistinguishable from a gate that *cannot* fail, and its green tick
proves nothing about either. Every one of the following was green, in this portfolio,
on a real merge:

- a check named for full-history scanning that read exactly one commit;
- a consent evaluation whose oracle was the component under test;
- an alarm whose threshold comparison could never be true, because the value arrived
  from the datastore as a `Decimal` and was compared against a `float`;
- four security checks that matched the words `semgrep`, `gitleaks` and `pip-audit`
  inside a `# TODO:` comment;
- a confidence interval labeled 95% that every one of its 31 tests still passed at
  *z* = 1.0, because every test asserted a property and no test pinned the width;
- a report whose `ok` field was `all(...)` over zero results;
- two mutation-control harnesses that reported *caught*: one had read only the
  last three lines of the test run's output, the other had read pytest's exit
  status 4 — a usage error, in which no test ran — as *caught*;
- a permission-denied write that an automated agent retried until it went
  through: a boundary that held only for as long as the actor chose to respect it.

These are not eight bugs. They are one defect wearing eight costumes, and "absence rendered
as a value" is only its most common costume. The others are a constant no test pins, a
verdict computed over an empty set, a check that matched a comment, and a comparison
between two types that never compare equal.

**What counts as a gate here.** Anything that emits a pass/fail verdict, an exit code a
caller branches on, or a published figure: a CI job, a `make verify` stage, a pre-push
hook, a checker under `automation/`, an evaluation harness, a scorer, a badge, and a
number in a README.

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| Executed falsifiability evidence, per gate [QM-19] | Every gate ships a committed, byte-reproducible execution record showing it **was observed failing** on (a) a planted defect it exists to catch, (b) an input of which it examined nothing, and (c) a mutation of a decisive literal in its own source | `automation/check_falsifiability.py` validates the record; `--execute` re-runs every case against the real gate and requires the committed record back, byte for byte | AUTO-GATE (advisory until promoted, §Promotion below) |
| The covered gate set is derived, not declared [QM-20] | The gates the record covers are enumerated **from the repository tree**. A gate that exists and appears in no case is reported `not measured` — never counted among the passes, never silently outside the scope | the same checker expands the record's declared globs against the tree and diffs the two sets | AUTO-GATE (advisory until promoted, §Promotion below) |
| Negative-control discipline [QM-21] | Any claim — in a pull request, an ADR, a report, or a commit message — that a gate "was verified to fail" carries the four artifacts named below, or it is not made | reviewer checks the four artifacts are in the diff or linked from it | REVIEW-GATE |

### What evidence satisfies QM-19

Four artifacts per case. Three of them exist because each has already been produced
wrongly and believed.

1. **A baseline identified by content hash, not by a scratch copy.** Record the
   SHA-256 of the file about to be sabotaged, and the SHA-256 of the gate program
   itself. A baseline kept as `foo.py.bak` is a file anything can overwrite; a hash is
   a claim that can be checked later by someone who was not there.
2. **Proof that the sabotage landed.** Record the SHA-256 *after* the edit, and require
   it to differ from the baseline. A sabotage that silently no-ops — a `find` string
   that was not present, a constant that was imported from elsewhere, a patched file
   the gate never reads — produces a green run that reads exactly like a passing
   negative control. **The most common way to fake this evidence is to fake it by
   accident.**
3. **The red, observed — not the exit code alone.** Record the command, its exit code,
   *and* the line of output that changed. An exit code is not a verdict on a runner
   that has been seen printing `gate FAILED` and exiting 0. Where a gate's exit code is
   genuinely not its verdict, the case says so in a field of its own and names what was
   read instead; it does not quietly treat 0 as red.

   **The observation is the gate's own words, quoted.** For a checker, the finding line
   it printed; for a test suite, the assertion message — `AssertionError: 0 != 1`, not
   `FAILED (failures=2)`. A harness's summary label (`FAIL`, `FAILED`, `caught`,
   `killed`, `red`, `blocked`) is a claim *about* the run made by a second program,
   and that second program is exactly what has been seen reading a truncated tail, or
   mistaking "nothing ran" for "something failed". Quote the line that proves the
   gate examined the defect and objected to it, from the complete output.
4. **The tree restored, byte-identical.** Record the SHA-256 after restoration and
   require it to equal the baseline. Cases run against a copy of the tree satisfy this
   by construction, and must still record the source tree's digest before and after, so
   "the generator did not touch the working tree" is a checked fact rather than a
   design intention.

And one assertion per case that is about the *other* gates:

5. **Collateral is declared, not tolerated.** Record the outcome of every other gate
   the case ran. A gate that fails on a defect it was not written to catch is a
   coupling, and an undeclared coupling **fails the case**. This is the assertion that
   makes trivial sabotage useless: planting a syntax error trips everything, so every
   row it appears in fails on undeclared collateral. It is also the assertion that
   turns this record into a map of which gates measure distinct things — a finding to
   report, not a number to tune.

### What does not satisfy it

- A test *named* `test_gate_rejects_empty_input` that calls the gate and asserts
  nothing. The name is not the execution.
- A checked box, a screenshot, or a sentence in a pull-request body.
- An argument that the gate *would* fail. Every gate in the list at the top of this
  section would have survived that argument.
- A case whose planted defect is a syntax error, a deleted file, or anything else that
  makes the gate program fail to start. That demonstrates the interpreter works.
- A harness's label for the run — `FAILED`, `caught`, `killed`, `red`, a non-zero
  count — in place of the quoted assertion message or finding line.
- An exit status that means the suite did not run. pytest's 4 (usage error) and 5
  (no tests collected), and unittest's `NO TESTS RAN`, are non-zero and are not
  failures: a mutant that nothing tested was not caught.
- A verdict read from part of the output: a `tail`, a first page, a grep for the
  word `FAIL`.
- A case that regenerates differently on a second run. Evidence that is not
  reproducible is an anecdote; no network, no clock, no randomness, no ordering that
  depends on a hash seed.

### The third state is mandatory

A gate with no falsifiability evidence is reported `not measured`. It is **not** a
pass, **not** a failure, and — unlike `n/a` — it **stays in the denominator**, because
`not measured` is a statement about this portfolio's knowledge and `n/a` is a statement
about the repository. A headline that improves when evidence goes missing is the same
defect this section exists to name.

### Negative-control discipline (QM-21)

Written down here once, rather than rediscovered by whoever runs the next one:

- Identify the baseline by git object hash or content hash. Never by a scratch copy.
- Assert the sabotage landed before trusting anything the run printed.
- Sabotage a **literal**, not a named constant: a named constant may be re-exported,
  defaulted, or shadowed, and the edit then changes nothing the gate reads.
- Clear `__pycache__` between runs. A stale bytecode file makes a landed edit invisible.
- If the control does not fire, widen the fixture before doubting the sabotage. A
  fixture too small to exhibit the defect is the usual cause, and "the gate must be
  fine" is the usual wrong conclusion.
- A denial is an observation, not an obstacle. When a permission system, a hook, a
  ruleset or a guard refuses an action, stop and report the exact command that was
  refused. Never retry it and never route around it: a retry that succeeds is
  evidence that the boundary cannot fail, which is the finding — not a path to the goal.
- Read the full output when judging a control. A run that printed a failure and exited
  0 has been observed here; so has a rising pass count inside a run that ultimately
  failed.
- A determinism claim is tested **across processes**, with `PYTHONHASHSEED` varied, over
  a fixture large enough that ordering is observable.

### Cost, and where each half runs

The cheap half — validating the committed record, and diffing the covered gate set
against the tree — is offline, deterministic and belongs in `make verify` and on every
pull request. The expensive half — re-executing every case against the real gate
(`--execute`) — belongs on a schedule and on any pull request that touches gate code.
A portfolio that already measured `make verify` roughly doubling when a mutation gate
was added to it should not put that cost on every push.

### Promotion

QM-19 and QM-20 land **advisory**, on the same terms as
`DISCOVERY-AND-ADOPTION-STANDARD.md` §8: the checker runs, reports each gate as `pass`,
`fail`, `n/a` or `not measured`, and is excluded from the score and from the weekly
sweep's red/green. A repository's number cannot move because this section was written.

Advisory is not "`|| true`". **A record that lies fails now, in the advisory phase and
on every push:** a case whose sabotage did not land, whose restoration digest does not
match its baseline, whose gate program has changed since the case was recorded, whose
outcome was a pass, or whose collateral was undeclared, is a hard failure at every
posture. Only the *absence* of evidence is advisory, and absence is what `not measured`
reports.

They are promoted to scored — and the three decisions below are made at the same time,
because promotion is where they start to cost something — when, and only when:

1. four consecutive weekly sweeps show QM-19 passing on at least 80% of the gates it
   applies to (`n/a` and `not measured` excluded from that pass rate but printed
   beside it), and
2. every remaining gate without evidence carries a waiver in `waivers.yml` or an open
   issue, and
3. the promotion is recorded in `CHANGELOG.md` with the four sweep dates and the rate
   on each.

Three decisions are deferred to promotion and are the owner's, not an implementer's:
whether a survivor allowlist exists at all (an existing mutation-gate ADR says no, in terms,
and a portfolio-wide allowlist reopens it); whether the posture at promotion is
*refuse* or *disclose* (an existing evaluation-harness ADR chose disclose, on the
grounds that refusing a partial configuration also refuses the legitimate case of
phasing coverage in); and whether exit codes are ever unified across gates — four
deliberate and incompatible schemes are in use, the record carries each gate's own
non-passing outcome, and nothing here requires changing that.

### What this control does not do

Scope is where it is soft. The covered set is derived from the tree, but the *globs*
that say which programs are gates are still a judgment, and a thin declaration is not
detectable from inside. This control raises the cost of a fake pass from zero to real.
It does not make one impossible, and it should not be described as though it did.

---

## Quality-attribute taxonomy — ISO/IEC 25010:2023

**Updated to the 2023 second edition** (replaces 2011). Nine top-level product-quality characteristics; the deltas from 2011 are load-bearing and called out. Each feature/story **must** map to ≥1 measurable acceptance criterion under ≥1 characteristic; an untested characteristic is an **out-of-scope violation** and must be declared N/A-with-reason (see *Scoping*). **Recheck the standard version at build time.**

> 2023 deltas you must use the new vocabulary for: *Usability* → **Interaction Capability** (adds inclusivity, self-descriptiveness, user-engagement); *Portability* → **Flexibility** (adds **scalability**); Security adds **resistance**; and **Safety** is a brand-new ninth characteristic. ISO/IEC 25010:2023 covers only the product-quality model; the *Quality-in-Use* model moved to the companion **ISO/IEC 25019:2023** (Beneficialness, Freedom from Risk, Acceptability) — used in REVIEW-GATE acceptance criteria for civic/public-facing repos.

### 1. Functional Suitability *(completeness, correctness, appropriateness)*
- **Targets:** all acceptance criteria pass; no `P0`/`P1` open at release; acceptance tests mapped 1:1 to roadmap features.
- **Gate (AUTO):** full suite green; mapping checked in CI.

### 2. Performance Efficiency *(time behaviour, resource utilization, capacity)*
- **Targets (web/API default):** p95 server response <500 ms (non-LLM routes); p95 first-token <1.5 s and full-response <6 s (LLM routes); Lighthouse Performance ≥90; critical-path JS <200 KB gzip. Regression budget: no numeric regression >10% vs committed baseline without product-owner sign-off.
- **Gate (AUTO):** **see `PERFORMANCE-STANDARD.md`** (reference implementation in `perf/`: copyable k6 script, `lighthouserc` budget, baseline schema). k6 asserts p95 budgets; Lighthouse CI asserts score + bundle budgets; `perf/baseline.json` committed, updated per PR touching latency-sensitive paths; >10% regression vs baseline fails without product-owner sign-off.

### 3. Compatibility *(co-existence, interoperability)*
- **Targets:** two latest versions of Chrome/Firefox/Safari/Edge; documented minimum Node/Python runtimes; no undeclared global state; declared, versioned API contracts.
- **Gate (AUTO):** Playwright cross-browser smoke; runtime/dependency matrix in CI.

### 4. Interaction Capability *(recognizability, learnability, operability, user-error protection, engagement, inclusivity, self-descriptiveness, user assistance)* — *formerly Usability*
- **Targets:** **WCAG 2.2 AA** floor (retain any higher conformance a repository has declared); keyboard-only completion of every primary task; visible focus; `prefers-reduced-motion` respected; readable at 200% zoom / 320 px; 2.5.8 target-size ≥24×24 CSS px; real multilingual content where civic.
- **Gate:** **see `ACCESSIBILITY-STANDARD.md` and `INTERNATIONALIZATION-STANDARD.md`.** AUTO: axe zero critical/serious/moderate; pa11y-ci **blocking**; Lighthouse a11y ≥0.9, or a higher self-declared floor. REVIEW: screen-reader walkthrough + ACR per release. Any provisional accessibility disposition follows `ACCESSIBILITY-STANDARD.md` §2.0 and leaves the REVIEW-GATE open.

### 5. Reliability *(faultlessness, availability, fault tolerance, recoverability)*
- **Targets:** declared SLO (default 99.5% monthly for hosted services); graceful degradation on dependency failure; no data loss on crash; idempotent writes; MTTR clock starts at alert-fire, not customer report.
- **Gate:** AUTO: chaos/fault-injection test for top dependency failure; restart-recovery test; `/livez` + `/readyz` (**see `OBSERVABILITY-STANDARD.md`**). REVIEW: error-budget burn reviewed at release.

### 6. Security *(confidentiality, integrity, non-repudiation, accountability, authenticity, **resistance**)* — *`resistance` new in 2023*
- **Targets:** ASVS 5.0 **L2** for anything touching sensitive PII, including transit/location data and civic RAG; L1 floor elsewhere; no HIGH/CRITICAL SAST/SCA findings; secrets never in source; least-privilege tokens; signed commits + signed releases.
- **Gate:** **see `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` + `CI-CD-STANDARD.md`.** AUTO: Semgrep/CodeQL, gitleaks (pre-commit **and** CI, **no `|| true`**), pip-audit/OSV/Trivy blocking on **CRITICAL,HIGH**, SHA-pinned `uses:`, SBOM+cosign+SLSA L2. REVIEW: threat model per new attack surface; Scorecard ≥8/10 with critical checks 10/10.

### 7. Maintainability *(modularity, reusability, analysability, modifiability, testability)*
- **Targets:** branch coverage ≥85% (libraries ≥90%); cyclomatic complexity ≤10 (`ruff C90`); typed (TS strict / `mypy --strict` or `pyright`); lint/format clean; duplication ≤3% on new code; no `TODO` without a linked issue.
- **Gate:** **see `CODE-QUALITY-STANDARD.md`.** AUTO: coverage/complexity/type/lint all merge-blocking via `make verify` (byte-equal to CI).

### 8. Flexibility *(adaptability, **scalability**, installability, replaceability)* — *formerly Portability; adds scalability*
- **Targets:** one-command local bring-up; containerized; IaC where hosted; documented teardown; horizontal-scale path documented for hosted services; no machine-specific assumptions.
- **Gate (AUTO):** CI builds container + runs from-scratch bring-up; IaC `plan` validates.

### 9. Safety — **NEW in 2023** *(operational constraint, risk identification, fail-safe, hazard warning, safe integration)*
- **Definition (ISO/IEC 25010:2023):** "capability of a product under defined conditions to avoid a state in which human life, health, property, or the environment is endangered." For **non-safety-critical but high-stakes** surfaces such as civic benefits, transit, identity, or public-data tools, Safety applies via **fail-safe** and **safe-integration** sub-characteristics.
- **Targets / measured-by per repo (illustrative, values live in-repo):**
  - no-outing guarantee — injected sentinel identities never surface (isolated CI job). **AUTO.**
  - "no identity inference ever" via AST-level static test. **AUTO.**
  - civic RAG or public-service AI: no ungrounded code path; citation/grounding guards. **AUTO** (see `AI-EVALUATION-STANDARD.md`).
  - evidence-integrity pipeline: reproducibility tamper-tripwire. **AUTO.**
  - privacy-sensitive local tools: consent gate sequenced before any feature. **AUTO** gate + **REVIEW** consent artifact.
- **Gate:** AUTO where the guard is code-enforced (the above); REVIEW: residual-risk register + fail-safe walkthrough per release. For genuinely safety-critical features, the acceptance criteria must address all five Safety sub-characteristics explicitly.

### 10. Data quality & lineage *(portfolio addendum — civic/transit ingest)*
- **Owned by `DATA-GOVERNANCE-STANDARD.md`.** Data-card presence, source + fetch-timestamp traceability, schema validation on ingest, staleness alarms, and per-source freshness SLAs are specified in full there (§1–2); this taxonomy slot exists only so "data quality" has a home in the ISO 25010 characteristic list.
- **Targets/Gate:** see `DATA-GOVERNANCE-STANDARD.md` §1 (data cards) and §2 (retention). Applies to civic/transit data products, monitoring pipelines, and civic RAG. Untrusted external archives or subprocess paths additionally carry a Safety + Security note owned by `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`.

---

## DORA — portfolio-level delivery-health signal

ISO 25010 says *what* quality is; DORA says *how fast and safely* it ships. This is a **portfolio-level health signal**, not a per-PR gate — measured automatically from CI/CD + incident events, reviewed quarterly. Manual tracking is prohibited for any repo claiming a performance tier.

**Five-metric model (2024, supersedes the original four keys):**

| DORA metric | Portfolio floor (alert if breached) | Elite reference | Measured by | Gate |
|-------------|-------------------------------------|-----------------|-------------|------|
| Deployment Frequency | ≥ weekly per active repo; alert if < deploy for 14 d | on-demand / multiple per day | release/deploy events from GH Actions | health signal (REVIEW quarterly) |
| Change Lead Time (commit→prod) | P90 < 1 day; alert if > 1 day | < 1 hour | commit→deploy timestamps | health signal |
| Change Fail Rate | < 15%; alert if > 10% (14-d rolling) | ≤ 5% | failed-deploy / incident events | health signal |
| Failed-Deployment Recovery Time | < 1 day; alert if any incident > 4 h | < 1 hour | incident open→resolve | health signal |
| Deployment Rework Rate *(new 2024)* | < 10%; alert if > 5% (30-d) | low | unplanned-fix deploy ratio | health signal |

**Implementation contract:** a `gh api`-based collector reads deploy, release,
and publish workflow runs plus `incident`-labeled issues, then writes a
committed quarterly `DORA-<year>-Q<n>.md` report and JSON snapshot. Hosted
repositories and Lambdas feed deploy events; library/CLI repositories report
DF/LT only. Failed-Deployment Recovery Time reads N/A until the repository has
adopted the incident-label convention; the collector never fabricates a zero.

**2024/2025 findings we act on (not survey trivia):**
- AI adoption is **positively** associated with throughput but **negatively** with stability — so automated safety nets (coverage gate, SAST, merge queue, red-team) are **prerequisite infrastructure**, not optional hygiene. This directly justifies the AUTO-GATE-everything stance.
- **DORA 2025 AI Capabilities Model** is a REVIEW-GATE governance checklist before expanding AI tooling scope in any AI/RAG repo: (1) clear and communicated AI stance, (2) healthy data ecosystems, (3) AI-accessible internal data, (4) strong version control practices, (5) working in small batches, (6) user-centric focus, (7) quality internal platforms. Do not expand scope until all seven hold. Portfolio requirement in addition (not one of DORA's seven): **AI-generated code is segmented in DORA metrics**.
- High-performance tier shrank (31%→22%) and AI amplifies existing gaps → the standard sets **minimum floors**, not just elite targets (above).

---

## Definition of Done (per-repo `DEFINITION_OF_DONE.md`)

Every repo ships a checked-in `DEFINITION_OF_DONE.md` at root, CODEOWNER-protected (engineering-leadership approval to modify), reviewed quarterly. Three tiers:

**AUTO-GATE (CI on every PR — required status checks under branch protection):**

```
1. format + lint            → ruff/eslint, zero errors            [CODE-QUALITY]
2. type-check               → mypy --strict / tsc strict, zero    [CODE-QUALITY]
3. unit + integration       → coverage branch ≥85% (libs ≥90%),   [CODE-QUALITY]
                              complexity ≤10, --cov-fail-under
4. security                 → semgrep+codeql+gitleaks+pip-audit/   [SECURITY]
                              osv+trivy, blocking HIGH+CRITICAL,
                              SHA-pinned uses:, SBOM+cosign+SLSA
5. workflow SAST            → zizmor on any .github/workflows/ PR  [CI-CD]
6. accessibility            → axe 0 crit/serious/mod; pa11y BLOCK; [ACCESSIBILITY]
                              Lighthouse a11y ≥0.9 / ≥95 declared
7. i18n (bilingual repos)   → key-parity + placeholder-parity +   [I18N]
                              msgfmt --check + pseudolocale
8. ai-eval (prompt/retr.)   → faithfulness ≥0.80, hallucination   [AI-EVALUATION]
                              ≤5%, red-team, judge κ ≥0.60
9. observability            → structured-JSON log shape (jq test), [OBSERVABILITY]
                              secret-in-logs SAST rule
10. performance             → k6/Lighthouse budgets, ≤10% regress  [PERFORMANCE]
                              vs committed perf/baseline.json
11. build + container + IaC plan
12. falsifiability evidence → every gate observed failing on a planted   [QUALITY-AND-METRICS]
                              defect, an empty input and a mutated
                              literal; advisory until promoted
```

`make verify` runs stages 1–4 (and 6–9 where applicable) locally, **byte-for-byte identical to CI** — the portfolio's drift-killing discipline; propagate it to every Python repo.

**REVIEW-GATE (human sign-off committed as PR attestation + artifact):**
- PR template checklist: acceptance criteria linked to issue; observability added (OTel spans on new paths); docs updated; rollback plan for schema/infra changes; ISO 25010 characteristic(s) named.
- New external attack surface → threat-model sign-off (`SECURITY`).
- New custom interactive component → ARIA APG audit; screen-reader walkthrough (`ACCESSIBILITY`; §2.0 governs any provisional disposition).
- New AI feature → NIST AI RMF risk register + EU AI Act / ISO 42001 impact assessment (`AI-EVALUATION`).

**RELEASE-GATE:** performance baseline regression passed; runbook updated; ACR (or the accessibility §2.0 provisional status record) + SBOM + provenance regenerated ("audit-as-artifact"); rollback documented. A domain-authorized provisional release must carry the synthetic-evidence record and maintainer residual-risk acceptance while keeping the human gate visibly open; it is not a conformance result.

**Branch protection (per `CI-CD-STANDARD.md`, org rulesets preferred):** PR required (≥1 independent approval, ≥2 for Safety/Security-critical paths), stale reviews dismissed, CODEOWNERS routing `.github/workflows/` + Safety-critical files to a required reviewer, required status checks in **strict** mode, **signed commits**, **linear history**, and **blocked force-pushes**. The accountable maintainer keeps a standing repository-admin bypass and may use it only under the documented CICD-15 emergency procedure, which records every bypassed merge; an empty bypass list is a locked-out repository, not a stricter gate. An eligible exactly-one-maintainer project uses CQ §7.1/CICD §5.1: platform approval count 0 plus an authenticated current-head owner decision and all checks green; it never labels self/synthetic review as independent approval. Accessibility §2.0 preserves linear history by merging the product change first, testing that protected-main commit, and merging the record through a separate evidence-only PR. Merge queue on high-velocity branches.

---

## Metrics ledger (per repo)

Each repo's `ROADMAP.md` carries a **Metrics** table with this exact shape so enforcement is unambiguous. Project-specific *values* go here; the *rigor* is cited to the owning standard.

| Metric | Target | Measured by | Gate | Owner |
|--------|--------|-------------|------|-------|
| Branch coverage [CQ-08] | ≥ 85% (libs ≥ 90%) | `pytest --cov` in CI | AUTO | — |
| axe violations [A11Y-01] | 0 crit/serious/mod | `axe-core` / `pa11y-ci` | AUTO | — |
| p95 first-token [QM-02] | < 1.5 s | k6 load test | AUTO | — |
| SHA-pinned `uses:` [SEC-25] | 100% | `zizmor` / Scorecard Pinned-Deps ≥9 | AUTO | — |
| RAG faithfulness [AIEV-02] | ≥ 0.80 | RAGAS in CI | AUTO | — |
| EN/ES key parity [I18N-08] | 100% | extract + parity check | AUTO | — |
| Screen-reader walkthrough [A11Y-11, A11Y-14] | per release | committed checklist + ACR | REVIEW | — |
| Threat model [QM-14] | per new surface | committed `THREATS.md`/ADR | REVIEW | — |

A metric is **AUTO-GATE** or **REVIEW-GATE** — never "aspirational." If it cannot be made merge-blocking, it is review-gated with a checklist item and a dated durable artifact under the owning standard.

---

## Scoping: declare N/A, never silently skip

A standard that does not apply to a repo must be recorded as **N/A-with-reason** in that repo's `ROADMAP.md` — a silent skip is a defect. Common cases:

- **i18n N/A** for single-user / English-only libraries — but the repo must still record the one-line entry point (wrap strings in `_()`). Locale key-parity is AUTO-GATE for **every** shipping multilingual repository.
- **Observability (OTel/SLO) out-of-scope** for libraries/CLIs — but `--log-format json` opt-in must exist and the out-of-scope decision must be documented.
- **Accessibility (browser-engine) N/A** for headless libraries — but tools whose own HTML output is user-facing **must** gate on their report's accessibility.
- **AI-eval N/A** for non-AI repos.

A pre-code repository authors these standards as its initial scaffold rather
than retrofitting them: the code-quality toolchain, `make verify`, and any
applicable consent gate land before feature code. Duplicate or forked packages
must be reconciled or documented before conformance is counted.

## DORA implementation — no longer aspirational

The portfolio implementation of the DORA section is **`automation/delivery_metrics.py`**
(git + `gh` mining, no LLM), emitting `metrics/PORTFOLIO-METRICS.md` on the weekly
launchd cadence: deployment frequency, lead time and a change-fail proxy, plus the
AI-quality-debt counterweights (churn, short-term-churn-14d, unreviewed-merge rate,
revert rate). Failed-deployment recovery time and deployment rework rate come from
the quarterly **`automation/dora_collector.py`** report
(`automation/dora/DORA-<year>-Q<n>.md`). `delivery_metrics.py` **segments AI-authored
vs human-authored** work via the `Co-Authored-By: Claude …` commit trailer, which
satisfies the portfolio's AI-segmentation requirement (a portfolio addition beside the
DORA 2025 AI Capabilities Model, not one of its seven capabilities). The full Track A methodology — the BASELINE/graduation gate state,
the never-gate list, telemetry privacy, and the quarterly DORA AI-Capabilities
self-assessment — lives in **`AI-DEVELOPMENT-MEASUREMENT-STANDARD.md`**.

---

Last verified: 2026-10-01 · Recheck cadence: quarterly, or on any new revision of ISO/IEC 25010, the DORA annual report, WCAG, OWASP ASVS, or OpenSSF Baseline — whichever is sooner.
