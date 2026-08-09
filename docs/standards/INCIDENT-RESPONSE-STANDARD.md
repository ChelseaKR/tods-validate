# Incident Response Standard

The canonical incident-response rigor for every repo in this portfolio: the severity ladder, the postmortem artifact, the secret-leak runbook, and the `incident` label convention that feeds `QUALITY-AND-METRICS-STANDARD.md`'s DORA rows. Repos override the *values* (who gets paged, which channel) but not the *structure* — a severity, a label, and a committed postmortem are not optional.

**Why this exists.** Without one labeling and postmortem convention, DORA's Change Fail Rate and Failed-Deployment Recovery Time rows have no reliable incident feed. This standard does not re-invent detection or scanning — `OBSERVABILITY-STANDARD.md` owns alerting and `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` owns secret-scanning mechanics. It owns what happens **after** something fires: who decides how bad it is, what gets rotated, and what gets written down.

**Solo-maintainer profile.** For an eligible one-person project, "paged" means a direct phone or monitoring notification to its owner rather than a fictitious rotation. SEV1/SEV2 targets are therefore stated as *time-to-acknowledge-by-the-owner*. A repository with a collaborator or paid on-call arrangement may tighten these targets; none may loosen them.

---

## 0. Scope & applicability

| Repo class | Examples | Applies |
|---|---|---|
| **Deployed service / Lambda / hosted app** | APIs, workers, serverless handlers, and web frontends | Full force: severity ladder, `incident` labels feeding DORA, postmortems, secret-leak runbook. |
| **Library / CLI / local-first tool** | reusable libraries, operator CLIs, and privacy-sensitive local tools | No deployment-availability incidents (no SEV1 "service down"), but data-exposure and secret-leak incidents still apply in full — a local-first tool with an identity-inference or privacy-guard failure is a SEV1 regardless of hosting. |
| **Standards/governance repository** | the repository that owns this standard | Applies in full; a governance repository is not exempt from the rigor it defines. |
| **Pre-code repository** | specification with no executable feature code | N/A until code exists; scaffolds `docs/incidents/` and the `incident` label with the initial engineering controls. |

**N/A is a declaration, not a default.** A repo with no incident history to date still declares this standard `Applies` — the absence of an incident is not the same as the absence of the convention. Only a genuinely pre-code repo declares `N/A — pre-code, scaffolds at M0` in its README.

---

## 1. Severity ladder

Every incident gets exactly one severity at open, re-assessed as facts emerge. There is no unnumbered "just a bug" escape hatch once the `incident` label is applied — see §2 for what triggers labelling in the first place.

| Sev | Definition | Illustrative examples | Ack target (owner) | Resolve target |
|---|---|---|---|---|
| **SEV1 — Critical** | Data breach or credential/secret exposure reaching a public surface (pushed commit, public log, public issue); PII or civic-rider-identity exposure; an ethics guardrail failure (no-outing, no-identity-inference, consent gate) that fired in production; a deployed service fully down for users | secret committed and pushed to a public remote | ≤ 4 h | ≤ 24 h to contain (rotate/revoke); full resolution per §4 |
| **SEV2 — High** | Partial outage or a core function degraded (RAG returns ungrounded answers, GTFS scorecard serves stale-past-SLA data as current); a secret staged but caught **before** push/publish; a dependency CVE with a public exploit and no patch yet | secret caught by pre-commit gitleaks before commit lands | ≤ 24 h | ≤ 3 days |
| **SEV3 — Moderate** | Bug affecting a subset of users/inputs with no data exposure; a scanning/CI gate silently disabled (`\|\| true`, `continue-on-error`) discovered in audit, not yet exploited | dependency scanner neutralized by `\|\| true` | ≤ 3 days | ≤ 2 weeks |
| **SEV4 — Low / near-miss** | No user impact; a control almost failed (a scanner would have caught a real secret but this one was a test fixture); process gap noticed, not yet triggered | — | best-effort | tracked, no SLA |

**Escalation is one-directional and cheap.** Any repo maintainer (i.e., the owner) may raise a severity on new information; lowering a severity requires the postmortem's root-cause section to justify it (a SEV1 does not quietly become a SEV3 without a written reason).

---

## 2. The `incident` label convention — the DORA feed

`QUALITY-AND-METRICS-STANDARD.md`'s DORA table measures **Change Fail Rate** and **Failed-Deployment Recovery Time** from "incident events" and states plainly that "incidents get labelled and tracked" — this section is the process that makes that true instead of aspirational.

| Rule | Requirement | Gate |
|---|---|---|
| Every incident is a GitHub issue [IR-01] | Opened in the affected repo (or `STANDARDS/` for cross-portfolio process incidents) the moment an event meets the SEV1–4 bar in §1 | REVIEW-GATE (judgment call: does this meet the bar) |
| Labelled `incident` + `sev1`…`sev4` [IR-02] | Both labels applied at open; severity label updated on re-assessment, never silently deleted (a label change is itself part of the postmortem timeline) | AUTO-GATE — CI/scheduled check on `automation/`-side tooling asserts every open issue with `incident` also carries exactly one `sevN` label |
| Open→close timestamps are the recovery-time signal [IR-03] | Issue `created_at` → `closed_at` feeds `QUALITY-AND-METRICS-STANDARD.md`'s Failed-Deployment Recovery Time row; an incident is not closed until its postmortem (§3) is committed | AUTO-GATE — the postmortem-presence check (§3) blocks closing the loop, not the issue itself (GitHub doesn't gate issue-close; the weekly conformance run **flags** any closed `incident` issue with no matching `docs/incidents/*.md` file as a regression) |
| Deploy-triggered incidents count toward Change Fail Rate [IR-04] | An incident opened within 24h of a deploy/release event in the same repo is tagged `deploy-caused` (or `deploy-caused: no` once ruled out) | REVIEW-GATE |

```bash
# automation/check_incident_postmortems.py (sketch — mirrors check_staleness.py's shape)
# For every issue closed with label `incident` in the last N days, assert a
# docs/incidents/YYYY-MM-DD-*.md exists referencing the issue number.
# Exit non-zero (feeds the weekly conformance regression report) if not.
```

---

## 3. Postmortem artifact convention

**Blameless, committed, dated.** A postmortem is a `docs/incidents/YYYY-MM-DD-<slug>.md` file in the affected repo, committed within the cadence below. It is not a GitHub issue comment (issues get deleted, transferred, or lost when a repo is archived; a committed file survives with the repo). Blameless means the document explains *what the system and process allowed to happen*, never *who screwed up* — a person's name appears only as "responder," never as "cause."

| Metric | Target | Gate |
|---|---|---|
| File exists per closed SEV1/SEV2 `incident` issue [IR-05] | `docs/incidents/YYYY-MM-DD-<slug>.md`, referencing the issue number | AUTO-GATE (§2 weekly check) |
| Committed within cadence [IR-06] | SEV1/SEV2: ≤ 7 days after resolution. SEV3: ≤ 14 days. SEV4: optional, encouraged as a one-paragraph near-miss note in the same directory | REVIEW-GATE (date-diff against issue close) |
| Required sections present [IR-07] | Summary, Severity, Timeline (UTC), Impact, Detection, Root cause, What went well, What went poorly, Action items (owner + due date), Related links | AUTO-GATE — a template-conformance lint (heading presence) |
| Blameless language [IR-08] | No individual named as cause; systemic/process framing | REVIEW-GATE — self-check against the template's blameless note before commit |
| Action items tracked to closure [IR-09] | Each action item is either a linked, open tracking issue or a linked, closed one with a merge reference | REVIEW-GATE |

### 3.1 Template

```markdown
# Incident: <one-line description> — YYYY-MM-DD

**Severity:** SEV1–4 (§1 of INCIDENT-RESPONSE-STANDARD)
**Status:** Resolved / Monitoring / Postmortem-only (near-miss)
**Related issue:** #NN

## Summary
Two to three sentences: what happened, what was affected, how it ended.

## Timeline (UTC)
| Time | Event |
|---|---|
| HH:MM | Detected — how, by whom/what |
| HH:MM | Acknowledged |
| HH:MM | Contained / mitigated |
| HH:MM | Resolved |

## Impact
Who/what was affected, for how long, and — for data-adjacent incidents —
whether §data was exposed (cross-reference `DATA-GOVERNANCE-STANDARD.md` if
so; this triggers that standard's breach-notification review).

## Detection
How the incident was found (alert, manual discovery, external report,
scheduled scan) — a "found by accident" entry is itself an action item
against `OBSERVABILITY-STANDARD.md` alerting.

## Root cause
Five-Whys or equivalent. Systemic framing — the process/tooling gap, not a
person.

## What went well / What went poorly
Two short lists.

## Action items
| Action | Owner | Due | Tracking issue |
|---|---|---|---|

## Related
Links: the `incident` issue, PRs, the affected release/tag, and — for a
secret-leak incident — the rotation record per §4.
```

### 3.2 Backfilled records

An incident that predates this standard may be reconstructed from
contemporaneous evidence. Unknown fields stay explicitly unknown rather than
being invented, and the record states that it is a backfill. Backfilling does
not relax any requirement for incidents occurring after adoption.

---

## 4. Secret-leak runbook

This ordered runbook covers a common high-impact incident class: a secret
reaching a commit, log, or public surface. Detection mechanics (gitleaks in
pre-commit/CI and scheduled TruffleHog scans) are owned by
`SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` §4; this section owns the response.

| Step | Action | Owner | Gate |
|---|---|---|---|
| **1. Rotate** [IR-10] | Generate a replacement credential *before* anything else — assume the leaked value is already compromised the instant it's public, regardless of exposure duration | human, immediate | REVIEW-GATE (no automation should auto-rotate a production credential unattended) |
| **2. Revoke** [IR-11] | Invalidate the leaked credential at its issuer (GitHub PAT/App token revocation, cloud IAM key deletion, API-provider key rotation) — confirm revocation, don't just assume the rotate step disabled it | human, ≤ 1 h from confirmation | AUTO-GATE assist: `gh api` / provider API call scripted, but the confirm step is human |
| **3. Scope the blast radius** [IR-12] | What could the credential access? Check provider audit logs (GitHub audit log, cloud CloudTrail-equivalent) for any use of the credential between exposure and revocation | human | REVIEW-GATE |
| **4. History-scrub decision** [IR-13] | **Default: do not rewrite history.** A public repo's history is already exfiltratable the moment it's pushed — scrubbing (`git filter-repo`/BFG) removes the string from the tree but not from forks, caches, or anyone who already cloned. Scrub only when (a) the repo is private and confirmed to have no external clones, or (b) a compliance/contractual obligation requires it. Either way, rotation (step 1) is what actually neutralizes the exposure — the scrub is cleanup, not the fix. Document the decision and reasoning in the postmortem regardless of which way it goes | human | REVIEW-GATE (documented either way — "scrubbed" and "did not scrub, because…" are both valid closes) |
| **5. Close the entry point** [IR-14] | Fix the mechanism that let the secret in: a missing `.gitignore` pattern, an explicit-paths violation (`git add -A` instead of named paths — the rule this standard's exemplar exists to enforce), a missing pre-commit hook in that repo. Verify the fix with a red-team test: stage the same file pattern again and confirm gitleaks blocks it | human | AUTO-GATE (the regression test itself, committed) |
| **6. Postmortem** [IR-05] | File per §3, within the SEV1/SEV2 cadence | human | AUTO-GATE (§3 presence check) |

**Never git-add wildcard in automation.** Every scripted `git commit` stages
**explicit, named paths only** — never `git add -A` or `git add .`. This is a
portfolio-wide AUTO-GATE:

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| No wildcard `git add` in committed automation [IR-15] | zero `git add -A`, `git add .`, or `git add --all` in any tracked `.sh`/`.py`/CI workflow that runs unattended | `grep -rn` lint in CI (`automation/check_staleness.py`-style script) over `automation/` and `.github/workflows/` | AUTO-GATE |
| Secret-scan runs before any automated commit [IR-16] | gitleaks (or equivalent) invoked on the staged diff immediately before any scripted `git commit` in unattended automation | presence check in the workflow/script | AUTO-GATE |

---

## 5. Metrics ledger (per repo)

| Metric | Target | Measured by | Gate |
|---|---|---|---|
| `incident` + `sevN` labels exist in the repo [IR-17] | both label sets created | `gh label list` check | AUTO-GATE |
| Every closed `incident` issue has a postmortem [IR-05] | 100% for SEV1/SEV2, tracked for SEV3 | §2/§3 weekly check | AUTO-GATE |
| Postmortem committed within cadence [IR-06] | SEV1/2 ≤ 7 days, SEV3 ≤ 14 days | issue-close-to-commit date diff | REVIEW-GATE |
| No wildcard `git add` in automation [IR-15] | zero matches | §4 lint | AUTO-GATE |
| DORA Failed-Deployment Recovery Time / Change Fail Rate populated [IR-18] | non-null for any repo with ≥1 closed incident | `QUALITY-AND-METRICS-STANDARD.md` DORA table sourced from `incident` issue timestamps | health signal (REVIEW quarterly) |

---

Last verified: 2026-07-08 · Recheck cadence: after any SEV1/SEV2 incident (the postmortem's action items feed back into this standard), or quarterly, whichever is first.
