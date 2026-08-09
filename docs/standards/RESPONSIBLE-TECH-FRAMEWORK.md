# Responsible-Tech Framework

**Doc index: 0 of 15** in the `STANDARDS/` set (see `DOCUMENTATION-STANDARD.md` §1).

This is the *methodology* behind every repo's `docs/RESPONSIBLE-TECH-AUDITS.md`. It is deliberately **not** a gate catalog. The mechanically-enforced thresholds live in the sibling standards and are referenced here once, never restated:

| Concern | Owning standard | This doc's role |
| --- | --- | --- |
| Lint / types / coverage / toolchain floors | `CODE-QUALITY-STANDARD.md` | references |
| DORA, DoD, merge gates | `QUALITY-AND-METRICS-STANDARD.md` | references |
| CI/CD hardening, token perms, OIDC, branch rulesets | `CI-CD-STANDARD.md` | references |
| SAST / SCA / secret-scan / SBOM / signing / SHA-pinning | `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` | references (audit F narrative) |
| WCAG gates, axe/pa11y/Lighthouse, SR matrix | `ACCESSIBILITY-STANDARD.md` | references (audit E narrative) |
| OTel, structured logs, SLOs, health probes | `OBSERVABILITY-STANDARD.md` | references |
| Catalogs, key-parity, pseudolocale, BCP-47 | `INTERNATIONALIZATION-STANDARD.md` | references (audit B/D narrative) |
| RAG faithfulness, red-team, hallucination, model cards | `AI-EVALUATION-STANDARD.md` | references (audits B/D narrative) |

**Reference, don't repeat.** When an audit needs a number — coverage %, axe impact level, faithfulness floor, SHA-pin requirement — it cites the owning standard. This document supplies the *frame* (what could go wrong, who is hurt, what we commit to) and the *governance scaffolding* (NIST AI RMF, ISO 42001, EU AI Act) that no single gate standard owns. If you find a numeric threshold duplicated here, it is a defect: delete it and link.

Each project instantiates these audits with concrete findings and commits the resulting reports into its own repo, so the responsible-tech work is *in* the codebase, version-controlled and reviewable, not in a slide deck nobody reads.

Each audit answers four questions in the same order: **What could go wrong? · How do we test for it? · What do we commit to? · How is that commitment enforced (auto-gate or review-gate)?**

There is no third category. A control is **AUTO-GATED** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATED** (requires human judgment, paired with a checklist item and a dated durable artifact—committed by default, authenticated current-head PR/release metadata only when explicitly authorized). An owning domain standard may authorize a truth-labeled provisional release from synthetic evidence plus maintainer residual-risk acceptance while an experiential REVIEW-GATE stays open; that disposition is neither gate satisfaction nor conformance. "Aspirational" is not an enforcement model; it is an unfinished audit.

---

## How to apply this framework to a repo

1. Open `docs/RESPONSIBLE-TECH-AUDITS.md` in the repo (scaffold it from the template below if absent).
2. For each audit A–F, decide **applies** or **N/A-with-reason**. N/A is a first-class decision and must be written down — a one-line justification, not silence. "No audit B section" is a defect; "Audit B N/A: single-user local tool, no ranking/classification of people" is conformant.
3. For each applicable audit, fill the four questions and mark every commitment AUTO or REVIEW.
4. Wire the AUTO commitments into `make verify` / CI per the owning standard. Generate the REVIEW artifacts and commit them dated.
5. Re-run on every release; artifacts are regenerated, never hand-edited stale.

### The applicability matrix (declare this per repo)

Which archetype a repo belongs to — and its per-standard `applies` / `na: "<reason>"` calls — is declared in **`STANDARDS/applicability.yml`**, the scoping registry every repo must be registered in (the weekly conformance run fails on an unregistered repo). The matrix below maps archetype → audit obligations; repo names are illustrative examples only:

| Supported repository archetype | A Ethics | B Bias | C Privacy | D Transparency | E A11y | F Security | AI-EVAL | I18N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI/RAG/evaluation service | yes | yes | yes | yes | if HTML/UI output | yes | **yes** | civic ⇒ yes |
| Privacy-first / local-first tool | yes | case-by-case | **yes** | yes | if UI | yes | if LLM | declare |
| Civic / nonprofit data product | yes | yes (geographic/linguistic) | yes | yes | yes | yes | if LLM | **yes for supported public languages** or declare |
| Web frontend | yes | if personalization | yes | yes | **yes** | yes | if LLM | yes |
| Pure library / CLI | yes (lite) | usually N/A | usually N/A | yes | N/A (declare) | yes | N/A | N/A (declare entry point) |

> A pre-code privacy-sensitive tool authors these audits into its initial
> scaffold rather than retrofitting them. Its consent gate (audits A/C)
> precedes feature work. Duplicate or forked implementations first record one
> canonical audit owner in the private registry.

---

## A. Ethics & responsibility audit
**Frame:** map stakeholders (users, non-users affected, the people *in* the data), name the worst plausible misuse and the worst plausible failure, and state the line the product will not cross.

- **Method:** a one-page consequence scan — primary users, bystanders, worst-case individual harm, and a "who could be hurt if this works exactly as intended?" question (the most useful one). For AI features, cross-reference the **12 NIST AI 600-1 GenAI risks** (CBRN, confabulation, dangerous/violent/hateful content, data privacy, environmental, harmful bias/homogenization, human-AI configuration, information integrity, information security, IP, obscene/degrading, value-chain) and record which apply.
- **Commitments:** an explicit non-goals / "this is not for" statement; a misuse-resistance design note; a kill-switch or rollback plan for harmful behavior; a named accountable owner (ISO 42001 Clause 6.2 — owner, timeline, success metric).
- **Enforcement:**
  - **REVIEW-GATE** — sign-off on the consequence scan + non-goals statement, committed dated.
  - **AUTO-GATE** — misuse-resistance unit tests where the misuse is *mechanical*:
    - no-outing guarantees use injected sentinel identities in an isolated CI job;
    - "no identity inference ever" is enforced by an **AST-level static test**;
    - privacy-sensitive local tools sequence the consent gate before any feature (CI fails if feature code lands without the gate).

## B. Bias & fairness audit
**Frame:** wherever the system ranks, recommends, classifies, or serves different groups differently, measure whether it does so equitably.

- **Method:** define the relevant groups/segments up front (states, languages — **EN vs ES is a first-class segment** for the California-serving civic repos — neighborhoods, identities); run disaggregated tests (does quality hold across segments?); for AI, run targeted probe suites and per-group eval breakdowns; check for **representational** harms (stereotyping, erasure) not just allocational ones.
- **Commitments:** documented segments, measured disparities, mitigations; a stance on inferred attributes — **default: never infer sensitive attributes**; use self-identification or omit. An AST/static-analysis gate is the enforcement pattern for code paths that could infer identity.
- **Enforcement:**
  - **AUTO-GATE** — where a metric exists. Per-segment eval pass rates and per-group fairness breakdowns live in `AI-EVALUATION-STANDARD.md` (model-card per-group eval rows). EN/ES parity of *capability* (not just strings) is checked against the catalog gate in `INTERNATIONALIZATION-STANDARD.md`.
  - **REVIEW-GATE** — representational-harm review (stereotyping/erasure), committed dated. Maps to NIST AI 600-1 Risk 6 (Harmful Bias & Homogenization).

## C. Privacy & data-protection audit (DPIA-style)
**Frame:** know exactly what data exists, why, where, and for how long — then minimize all four.

- **Method:** a data inventory (what is collected, lawful basis/justification, storage, retention, who can access); a threat model for the *specific people* in the data (for example, hostile-jurisdiction, abusive-partner, or transit-rider-PII models); a data-flow diagram; check against data-minimization and purpose-limitation. For AI, this maps to NIST AI 600-1 Risk 4 (Data Privacy) and ISO 42001 Annex A data-quality controls.
- **Commitments:** retention limits (the specific per-tier numbers are owned by `DATA-GOVERNANCE-STANDARD.md` §2 — this audit checks a repo's actual retention against that floor, it does not set the number), encryption at rest/in transit, local-first where feasible (backup/DR expectations for local-first repos: `DATA-GOVERNANCE-STANDARD.md` §3), no third-party exfiltration, subject-access/deletion paths, and a plain-language privacy notice. The **DPIA is a committed, regenerated artifact**, not a one-time doc. A confirmed breach or unexpected L2/L3 exposure triggers `INCIDENT-RESPONSE-STANDARD.md`'s process, with the data-specific questions in `DATA-GOVERNANCE-STANDARD.md` §6.
- **Enforcement:**
  - **AUTO-GATE** — no-PII-in-logs (the secret-in-logs SAST rule lives in `OBSERVABILITY-STANDARD.md`: no password/token/email field values, classified per `DATA-GOVERNANCE-STANDARD.md` §4; validated by `jq` on structured logs in an integration test); encryption asserted in tests; retention jobs tested against the `DATA-GOVERNANCE-STANDARD.md` §2 schedule; secret scanning (gitleaks pre-commit **and** CI, no `|| true`) per `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`.
  - **REVIEW-GATE** — DPIA sign-off, committed dated. For AI features processing personal data, this is also the **ISO 42001 Clause 6.1.4 AI System Impact Assessment** (see Governance §).

## D. Transparency & explainability audit
**Frame:** a person should be able to understand what the system did and how far to trust it.

- **Method:** inventory every place the system makes a claim or a recommendation; verify each is attributable (source + last-verified date) and carries appropriate uncertainty; for AI, produce a **model card** (Hugging Face spec — YAML: `language`, `license`, `datasets`, `base_model`, `pipeline_tag`, `library_name`, ≥1 `model-index` eval result, CO2/environmental row, intended/out-of-scope use) and a **datasheet for datasets** (7 mandatory sections: Motivation, Composition, Collection, Preprocessing, Uses, Distribution, Maintenance).
- **Commitments:** visible sourcing/citations, confidence or limitation signposting, clear "AI-generated / not legal-or-medical advice" labeling where relevant, open documentation of what the system *cannot* do, and **EU AI Act Art. 50** machine-readable AI-content labeling where applicable.
- **Enforcement:**
  - **AUTO-GATE** — citation/grounding guards with **no ungrounded code path**, as codified in `AI-EVALUATION-STANDARD.md`. Disclosure-string presence tests. Model-card / datasheet YAML completeness lint (JSON-Schema step — see AI-EVAL standard).
  - **REVIEW-GATE** — honesty-of-framing review; model card approved by the accountable owner before production deploy.

## E. Accessibility audit
**Frame:** **WCAG 2.2 AA is the floor, not the goal**; retain any higher conformance a repository declares. The goal is that the primary task is completable by someone using a screen reader, a keyboard, magnification, or reduced motion. Tools whose *own HTML output* is user-facing must gate on their output's accessibility, not only their UI's.

- **Method:** automated (`axe-core --tags wcag2a,wcag2aa,wcag22aa`, Lighthouse, `pa11y-ci`) for the mechanical ~30–57%, plus a manual pass: keyboard-only walkthrough, screen-reader walkthrough (VoiceOver + NVDA), 200% zoom, 320 px reflow, contrast, motion, form-error clarity, and the **WCAG 2.2 additions** (2.4.11 Focus Not Obscured, 2.5.7 Dragging, **2.5.8 Target Size 24×24 px**, 3.2.6 Consistent Help, 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication).
- **Commitments:** zero automated violations at AA, a recorded manual walkthrough per primary task, and an accessibility statement (ACR/VPAT 2.4 format).
- **Enforcement:** thresholds, the SR-matrix checklist, and any provisional disposition are owned by `ACCESSIBILITY-STANDARD.md` (§2.0); this audit supplies the narrative. In summary:
  - **AUTO-GATE** — axe zero critical/serious/moderate; Lighthouse a11y ≥ 0.9 (≥95 where self-declared); **`pa11y-ci` is blocking** with a curated, justified ignore list. `continue-on-error` and `|| true` are forbidden. The structural Python/lint checker and browser engine both block.
  - **REVIEW-GATE** — committed screen-reader walkthrough (NVDA+Firefox/Chrome, VoiceOver+Safari macOS/iOS) + ACR per release; ARIA APG pattern audit for any custom widget. Project-specific pending rows remain in the private remediation registry until completed.

A solo-maintainer synthetic-evidence disposition under `ACCESSIBILITY-STANDARD.md` §2.0 may permit a provisional release, but it does not complete this REVIEW-GATE or support a conformance claim.

## F. Security audit
**Frame:** this audit adds the *narrative* threat model and the residual-risk register on top of the mechanical scanners. Gates live in `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` and `CI-CD-STANDARD.md`; target posture is **OWASP ASVS 5.0 Level 2** for any PII-holding or externally-exposed system.

- **Method:** STRIDE-style threat model of the data flows; abuse-case tests; dependency, secret, and supply-chain hygiene. Pay special attention to repositories processing transit/location PII, fetching untrusted archives, or spawning subprocesses.
- **Commitments:** documented threat model, **no fixed HIGH/CRITICAL findings**, encrypted sensitive stores, least-privilege, and a residual-risk register with owners.
- **Enforcement:** owned by the security standard; narrative summary here:
  - **AUTO-GATE** — Semgrep `ci --sarif` blocking on HIGH/CRITICAL + CodeQL nightly/required; gitleaks pre-commit **and** CI with no `|| true`; `pip-audit`/`npm audit --audit-level=high`/OSV-Scanner blocking on fixed HIGH+CRITICAL; Trivy/Grype image scan blocking on **CRITICAL,HIGH** for every repository with a Dockerfile; **every `uses:` pinned to a full 40-char SHA**; CycloneDX 1.7 SBOM + cosign keyless signing + SLSA L2 provenance on every release artifact/image.
  - **REVIEW-GATE** — threat-model + residual-risk-register sign-off, committed dated; `zizmor` workflow-SAST review for any PR touching `.github/workflows/` (the required status check itself is AUTO).

---

## Governance scaffolding for AI systems (the part no gate standard owns)

The gate standards measure faithfulness, red-team findings, and model-card completeness. They do **not** establish the management-system spine that NIST AI RMF, ISO 42001, and the EU AI Act require. That spine lives here, as REVIEW-GATES, with committed artifacts.

| Governance artifact | Frame / source | Trigger | Gate | Owner artifact path |
| --- | --- | --- | --- | --- |
| **AI system inventory + risk register** [RTF-09] | NIST AI RMF MAP; ISO 42001 Clause 6.1 | before any AI feature ships; quarterly review | REVIEW-GATE | `docs/audits/ai-risk-register.md` (signed) |
| **AI System Impact Assessment** [RTF-10] | ISO 42001 Clause 6.1.4 | any AI feature processing personal data, making consequential decisions, or exposed to external users | REVIEW-GATE | `docs/audits/ai-impact-assessment.md` |
| **Statement of Applicability** (42 Annex A controls) [RTF-11] | ISO 42001 | production AI system; annual + post-architecture-change | REVIEW-GATE | `docs/audits/iso42001-soa.md` |
| **EU AI Act risk classification** [RTF-12] | EU AI Act Annex III + GPAI | every AI feature; re-run on material change | REVIEW-GATE | `docs/audits/eu-ai-act-classification.md` |
| **Conformity-assessment package** [RTF-13] | EU AI Act Art. 17/18/47 | only if classified high-risk (Annex III) | REVIEW-GATE | gated artifact bundle |
| **Red-team report** [RTF-14] | OWASP LLM Top 10 v2.0; PyRIT/Garak | before each major model release; after prompt/arch change | REVIEW-GATE | `docs/audits/redteam-<date>.md` |
| **Environmental footprint** [RTF-15] | NIST AI 600-1 Risk 5; EU AI Act GPAI | within one sprint of any training/fine-tune run | REVIEW-GATE | model-card CO2 row |

**Current framework versions (verify at build time):**

| Framework | Version / status as of 2026-06-21 | Relevance to this portfolio |
| --- | --- | --- |
| NIST AI RMF | 1.0 (Jan 2023) + **GenAI Profile NIST AI 600-1** (Jul 2024); Agentic Profile concept note Apr 2026 | living risk register; 12 GenAI risks; 72 subcategories |
| ISO/IEC 42001 | :2023 (Dec 2023) — only certifiable AIMS | SoA, impact assessments, risk register |
| EU AI Act | Reg. (EU) 2024/1689 — **full high-risk application Aug 2, 2026**; GPAI obligations live since Aug 2025; Annex III conformity deadline Dec 2, 2027 | classify every AI feature and write down the decision |
| OWASP Top 10 for LLM Apps | **v2.0 (Nov 2024)**, LLM01–LLM10:2025 | red-team checklist (see AI-EVAL standard) |
| WCAG | **2.2 AA** (Oct 2023, upd. Dec 2024) — floor; WCAG 3.0 still Working Draft, no compliance action | audit E (see A11Y standard) |
| OWASP ASVS | **5.0** | audit F target = L2 (see security standard) |
| Model Cards / Datasheets | Mitchell et al. / Gebru et al.; HF Hub spec current | audit D transparency artifacts |

> The obligation is not automatically certification; it is an explicit,
> evidence-backed classification artifact. A two-line "EU AI Act
> classification: minimal-risk, not Annex III, rationale: …" committed file can
> satisfy the REVIEW-GATE where that classification is accurate. Silence does
> not.

---

## What gets committed into each repo

For each applicable audit, the repo's `docs/RESPONSIBLE-TECH-AUDITS.md` (and, where the audit is machine-generated, `docs/audits/*.md` or `*.json` artifacts) contains:

1. The **findings** (risks specific to this project).
2. The **checklist** (each item marked AUTO-GATED or REVIEW-GATED, with the owning standard linked for the numeric threshold).
3. The **committed report/artifact** (the eval run, the axe report, the DPIA, the model card, the risk register), regenerated by `make verify` / release CI and updated on every release.

This is the literal meaning of "baking the reports into the repo": the audit is a **build artifact**, regenerated and re-committed, never a one-time PDF. The required audit-as-artifact set includes DPIAs, ACR/VPATs, threat models, data/model cards, and residual-risk registers regenerated on release. Repository-specific adoption evidence and gaps remain private.

### Scaffold template (`docs/RESPONSIBLE-TECH-AUDITS.md`)

```markdown
# Responsible-Tech Audits — <repo>
Instantiates STANDARDS/RESPONSIBLE-TECH-FRAMEWORK.md. Last regenerated: <date>.

## Applicability
- A Ethics:        applies
- B Bias:          N/A — single-user local tool, ranks no people
- C Privacy:       applies (DPIA: docs/audits/dpia.md)
- D Transparency:  applies
- E Accessibility: applies (ACR: docs/audits/acr.md)  | or: N/A — no UI, headless CLI
- F Security:      applies (threat model: docs/audits/threat-model.md)
- AI-EVAL:         N/A — no LLM in the stack
- I18N:            N/A — English-only personal tool; entry point: wrap strings in _()

## A. Ethics  — [findings] [checklist: AUTO/REVIEW] [artifact]
## B. Bias    — ...
...
## Governance (AI repos only) — risk register / impact assessment / SoA / EU classification
```

Every `N/A` line carries a reason. A missing audit section is a defect; a justified `N/A` is conformance.

---

## Publication state — public visibility is a recorded decision, not a default

Making a repository public is irreversible in the way that matters: it can be
un-published, but it cannot be un-seen. So publication is treated here the same
way this framework treats every other consequential choice — as a decision that
is **written down before it takes effect**, not inferred from whatever a
repository's settings happen to say.

Each entry in `applicability.yml` carries a `publication:` state:

| State | Meaning |
|---|---|
| `restricted` | Not approved for public visibility. **The default**, including for any entry that omits the field — a repo cannot become publishable by oversight. |
| `pending` | A publication review is underway. Still not publishable. |
| `cleared` | Approved to be public. Only this state permits a public repository. |

**The gate [RTF-16]:** the weekly run reads each repo's live GitHub visibility
and fails when a repo is public without being `cleared`. It skips gracefully
when visibility cannot be determined (no `gh`, offline, auth failure), matching
the branch-protection control — a network blip must not fail a run, but it also
never counts as a pass.

**Why the state and not the reasoning lives here:** the analysis behind a
clearance — ownership, employment obligations, third-party commitments — is the
owner's own record and often privileged. Duplicating it into a repository would
put the sensitive part in the least appropriate place. This field records *the
decision and its date*; the reasoning stays wherever the owner keeps it.

This control protects against visibility drift caused by automation or manual
settings changes. The scheduled comparison is detection, not prevention;
hosting policy and the local publication guard must stop an unsafe visibility
change or push before it becomes externally readable.

---

Last verified: 2026-06-21 · Recheck cadence: quarterly, and immediately on any revision to NIST AI RMF / AI 600-1, ISO 42001, EU AI Act enforcement phases, WCAG, or OWASP ASVS / LLM Top 10. (Confirm current framework versions at build time.)
