# Responsible-Tech Framework

**Doc index: 9**

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

There is no third category. A control is **AUTO-GATED** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATED** (requires human judgment, paired with a checklist item and a dated committed artifact). "Aspirational" is not an enforcement model; it is an unfinished audit.

---

## How to apply this framework to a repo

1. Open `docs/RESPONSIBLE-TECH-AUDITS.md` in the repo (scaffold it from the template below if absent).
2. For each audit A–F, decide **applies** or **N/A-with-reason**. N/A is a first-class decision and must be written down — a one-line justification, not silence. "No audit B section" is a defect; "Audit B N/A: single-user local tool, no ranking/classification of people" is conformant.
3. For each applicable audit, fill the four questions and mark every commitment AUTO or REVIEW.
4. Wire the AUTO commitments into `make verify` / CI per the owning standard. Generate the REVIEW artifacts and commit them dated.
5. Re-run on every release; artifacts are regenerated, never hand-edited stale.

### The applicability matrix (declare this per repo)

| Repo archetype (this portfolio) | A Ethics | B Bias | C Privacy | D Transparency | E A11y | F Security | AI-EVAL | I18N |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI/RAG/eval (`govchat-eval`, `civic-ai-eval-harness`, `civic-rag-starter-kit`, `fare-assistant`, `women-artist-discovery`, `jobradar`) | yes | yes | yes | yes | if HTML/UI output | yes | **yes** | civic ⇒ yes |
| Privacy-first / local-first (`ledger`, `self-osint-monitor`, `nearmiss`, `swelter`) | yes | case-by-case | **yes** | yes | if UI | yes | if LLM | declare |
| Civic transit data (`gtfs-scorecard`, `tods-validate`, `fare-assistant`, `davis-bike-hazard-map`) | yes | yes (geographic/linguistic) | yes | yes | yes | yes | if LLM | **yes (EN/ES)** |
| Frontend (`personal-site`, `davis-bike-hazard-map`, `trans-docs-navigator`) | yes | if personalization | yes | yes | **yes** | yes | if LLM | yes |
| Pure library / CLI | yes (lite) | usually N/A | usually N/A | yes | N/A (declare) | yes | N/A | N/A (declare entry point) |

> `self-osint-monitor` is spec-only (M0). These audits are authored as the **M0/M1 scaffold**, not retrofitted. Its consent gate (audit A/C) must sequence *before* any feature work, per its own spec.
> `queer-the-stacks` / `queer-specfic-reader` share a package and are an undocumented fork. Reconcile to one repo before duplicating audit work; until then, the audit lives in the canonical repo and the fork carries a one-line "audit upstream" pointer.

---

## A. Ethics & responsibility audit
**Frame:** map stakeholders (users, non-users affected, the people *in* the data), name the worst plausible misuse and the worst plausible failure, and state the line the product will not cross.

- **Method:** a one-page consequence scan — primary users, bystanders, worst-case individual harm, and a "who could be hurt if this works exactly as intended?" question (the most useful one). For AI features, cross-reference the **12 NIST AI 600-1 GenAI risks** (CBRN, confabulation, dangerous/violent/hateful content, data privacy, environmental, harmful bias/homogenization, human-AI configuration, information integrity, information security, IP, obscene/degrading, value-chain) and record which apply.
- **Commitments:** an explicit non-goals / "this is not for" statement; a misuse-resistance design note; a kill-switch or rollback plan for harmful behavior; a named accountable owner (ISO 42001 Clause 6.2 — owner, timeline, success metric).
- **Enforcement:**
  - **REVIEW-GATE** — sign-off on the consequence scan + non-goals statement, committed dated.
  - **AUTO-GATE** — misuse-resistance unit tests where the misuse is *mechanical*. This portfolio already ships exemplary instances; treat them as the bar:
    - `ledger` — no-outing guarantee tested with injected sentinel identities as an isolated CI job.
    - `women-artist-discovery` — "no identity inference ever" enforced by an **AST-level static test**.
    - `self-osint-monitor` — consent gate sequenced before any feature (CI fails if feature code lands without the gate).

## B. Bias & fairness audit
**Frame:** wherever the system ranks, recommends, classifies, or serves different groups differently, measure whether it does so equitably.

- **Method:** define the relevant groups/segments up front (states, languages — **EN vs ES is a first-class segment** for the California-serving civic repos — neighborhoods, identities); run disaggregated tests (does quality hold across segments?); for AI, run targeted probe suites and per-group eval breakdowns; check for **representational** harms (stereotyping, erasure) not just allocational ones.
- **Commitments:** documented segments, measured disparities, mitigations; a stance on inferred attributes — **default: never infer sensitive attributes**; use self-identification or omit (`women-artist-discovery`'s AST gate is the enforcement pattern; `self-osint-monitor`/`ledger` inherit it).
- **Enforcement:**
  - **AUTO-GATE** — where a metric exists. Per-segment eval pass rates and per-group fairness breakdowns live in `AI-EVALUATION-STANDARD.md` (model-card per-group eval rows). EN/ES parity of *capability* (not just strings) is checked against the catalog gate in `INTERNATIONALIZATION-STANDARD.md`.
  - **REVIEW-GATE** — representational-harm review (stereotyping/erasure), committed dated. Maps to NIST AI 600-1 Risk 6 (Harmful Bias & Homogenization).

## C. Privacy & data-protection audit (DPIA-style)
**Frame:** know exactly what data exists, why, where, and for how long — then minimize all four.

- **Method:** a data inventory (what is collected, lawful basis/justification, storage, retention, who can access); a threat model for the *specific people* in the data (a hostile-jurisdiction model for some projects, an abusive-ex model for others, a transit-rider-PII model for `fare-assistant`); a data-flow diagram; check against data-minimization and purpose-limitation. For AI, this maps to NIST AI 600-1 Risk 4 (Data Privacy) and ISO 42001 Annex A data-quality controls.
- **Commitments:** retention limits, encryption at rest/in transit, local-first where feasible, no third-party exfiltration, subject-access/deletion paths, and a plain-language privacy notice. The **DPIA is a committed, regenerated artifact**, not a one-time doc.
- **Enforcement:**
  - **AUTO-GATE** — no-PII-in-logs (the secret-in-logs SAST rule lives in `OBSERVABILITY-STANDARD.md`: no password/token/email field values; validated by `jq` on structured logs in an integration test); encryption asserted in tests; retention jobs tested; secret scanning (gitleaks pre-commit **and** CI, no `|| true`) per `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md`.
  - **REVIEW-GATE** — DPIA sign-off, committed dated. For AI features processing personal data, this is also the **ISO 42001 Clause 6.1.4 AI System Impact Assessment** (see Governance §).

## D. Transparency & explainability audit
**Frame:** a person should be able to understand what the system did and how far to trust it.

- **Method:** inventory every place the system makes a claim or a recommendation; verify each is attributable (source + last-verified date) and carries appropriate uncertainty; for AI, produce a **model card** (Hugging Face spec — YAML: `language`, `license`, `datasets`, `base_model`, `pipeline_tag`, `library_name`, ≥1 `model-index` eval result, CO2/environmental row, intended/out-of-scope use) and a **datasheet for datasets** (7 mandatory sections: Motivation, Composition, Collection, Preprocessing, Uses, Distribution, Maintenance).
- **Commitments:** visible sourcing/citations, confidence or limitation signposting, clear "AI-generated / not legal-or-medical advice" labeling where relevant, open documentation of what the system *cannot* do, and **EU AI Act Art. 50** machine-readable AI-content labeling where applicable.
- **Enforcement:**
  - **AUTO-GATE** — citation/grounding guards (the portfolio's signature: `fare-assistant` and the civic RAG repos code-enforce citation coverage with **no ungrounded code path**; this is now codified portfolio-wide in `AI-EVALUATION-STANDARD.md`). Disclosure-string presence tests. Model-card / datasheet YAML completeness lint (JSON-Schema step — see AI-EVAL standard).
  - **REVIEW-GATE** — honesty-of-framing review; model card approved by the accountable owner before production deploy.

## E. Accessibility audit
**Frame:** **WCAG 2.2 AA is the floor, not the goal** (AAA where already achieved, e.g. `personal-site`); the goal is that the primary task is completable by someone using a screen reader, a keyboard, magnification, or reduced motion. Tools whose *own HTML output* is user-facing (the eval harnesses) must gate on their output's a11y, not only their UI's.

- **Method:** automated (`axe-core --tags wcag2a,wcag2aa,wcag22aa`, Lighthouse, `pa11y-ci`) for the mechanical ~30–57%, plus a manual pass: keyboard-only walkthrough, screen-reader walkthrough (VoiceOver + NVDA), 200% zoom, 320 px reflow, contrast, motion, form-error clarity, and the **WCAG 2.2 additions** (2.4.11 Focus Not Obscured, 2.5.7 Dragging, **2.5.8 Target Size 24×24 px**, 3.2.6 Consistent Help, 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication).
- **Commitments:** zero automated violations at AA, a recorded manual walkthrough per primary task, and an accessibility statement (ACR/VPAT 2.4 format).
- **Enforcement:** thresholds and the SR-matrix checklist are owned by `ACCESSIBILITY-STANDARD.md`; this audit supplies the narrative. In summary:
  - **AUTO-GATE** — axe zero critical/serious/moderate; Lighthouse a11y ≥ 0.9 (≥ 95 where self-declared, e.g. `gtfs-scorecard` MUST wire it); **`pa11y-ci` graduated from advisory to blocking** with a curated, justified ignore list — this kills the `continue-on-error`/`|| true` pattern in `civic-ai-eval-harness`, `govchat-eval`, `civic-rag`, `fare-assistant`. The structural Python/lint checker remains the hard gate; the browser engine is now also blocking.
  - **REVIEW-GATE** — committed screen-reader walkthrough (NVDA+Firefox/Chrome, VoiceOver+Safari macOS/iOS) + ACR per release; ARIA APG pattern audit for any custom widget. Resolve the pending NVDA/VoiceOver rows in `habitable`, `nearmiss`, `queer-the-stacks`.

## F. Security audit
**Frame:** this audit adds the *narrative* threat model and the residual-risk register on top of the mechanical scanners. Gates live in `SECURITY-AND-SUPPLY-CHAIN-STANDARD.md` and `CI-CD-STANDARD.md`; target posture is **OWASP ASVS 5.0 Level 2** for any PII-holding or externally-exposed system.

- **Method:** STRIDE-style threat model of the data flows; abuse-case tests; dependency, secret, and supply-chain hygiene. Pay special attention to the high-sensitivity / thin-scanning repos: `fare-assistant` (transit PII), `gtfs-scorecard` (fetches external zips + spawns a Java subprocess).
- **Commitments:** documented threat model, **no fixed HIGH/CRITICAL findings**, encrypted sensitive stores, least-privilege, and a residual-risk register with owners.
- **Enforcement:** owned by the security standard; narrative summary here:
  - **AUTO-GATE** — Semgrep `ci --sarif` blocking on HIGH/CRITICAL + CodeQL nightly/required; gitleaks pre-commit **and** CI (drop every `|| true` — currently neutered in `ledger`, `nearmiss`); `pip-audit`/`npm audit --audit-level=high`/OSV-Scanner blocking on fixed HIGH+CRITICAL; Trivy/Grype image scan blocking on **CRITICAL,HIGH** (standardized portfolio-wide — close the gaps in `davis`, `habitable`, `civic-rag`, `queer-the-stacks`, `trans-docs`) for every repo with a Dockerfile; **every `uses:` pinned to a full 40-char SHA**; CycloneDX 1.7 SBOM + cosign keyless signing + SLSA L2 provenance on every release artifact/image. `habitable`, `trans-docs-navigator`, and `civic-ai-eval-harness`/`govchat-eval` already demonstrate this full posture — it is the propagation target.
  - **REVIEW-GATE** — threat-model + residual-risk-register sign-off, committed dated; `zizmor` workflow-SAST review for any PR touching `.github/workflows/` (the required status check itself is AUTO).

---

## Governance scaffolding for AI systems (the part no gate standard owns)

The gate standards measure faithfulness, red-team findings, and model-card completeness. They do **not** establish the management-system spine that NIST AI RMF, ISO 42001, and the EU AI Act require. That spine lives here, as REVIEW-GATES, with committed artifacts.

| Governance artifact | Frame / source | Trigger | Gate | Owner artifact path |
| --- | --- | --- | --- | --- |
| **AI system inventory + risk register** | NIST AI RMF MAP; ISO 42001 Clause 6.1 | before any AI feature ships; quarterly review | REVIEW-GATE | `docs/audits/ai-risk-register.md` (signed) |
| **AI System Impact Assessment** | ISO 42001 Clause 6.1.4 | any AI feature processing personal data, making consequential decisions, or exposed to external users | REVIEW-GATE | `docs/audits/ai-impact-assessment.md` |
| **Statement of Applicability** (42 Annex A controls) | ISO 42001 | production AI system; annual + post-architecture-change | REVIEW-GATE | `docs/audits/iso42001-soa.md` |
| **EU AI Act risk classification** | EU AI Act Annex III + GPAI | every AI feature; re-run on material change | REVIEW-GATE | `docs/audits/eu-ai-act-classification.md` |
| **Conformity-assessment package** | EU AI Act Art. 17/18/47 | only if classified high-risk (Annex III) | REVIEW-GATE | gated artifact bundle |
| **Red-team report** | OWASP LLM Top 10 v2.0; PyRIT/Garak | before each major model release; after prompt/arch change | REVIEW-GATE | `docs/audits/redteam-<date>.md` |
| **Environmental footprint** | NIST AI 600-1 Risk 5; EU AI Act GPAI | within one sprint of any training/fine-tune run | REVIEW-GATE | model-card CO2 row |

**Current framework versions (verify at build time):**

| Framework | Version / status as of 2026-06-21 | Relevance to this portfolio |
| --- | --- | --- |
| NIST AI RMF | 1.0 (Jan 2023) + **GenAI Profile NIST AI 600-1** (Jul 2024); Agentic Profile concept note Apr 2026 | living risk register; 12 GenAI risks; 72 subcategories |
| ISO/IEC 42001 | :2023 (Dec 2023) — only certifiable AIMS | SoA, impact assessments, risk register |
| EU AI Act | Reg. (EU) 2024/1689 — **full high-risk application Aug 2, 2026**; GPAI obligations live since Aug 2025; Annex III conformity deadline Dec 2, 2027 | classify every AI feature; most portfolio AI is **not** high-risk, but the classification decision must be written down |
| OWASP Top 10 for LLM Apps | **v2.0 (Nov 2024)**, LLM01–LLM10:2025 | red-team checklist (see AI-EVAL standard) |
| WCAG | **2.2 AA** (Oct 2023, upd. Dec 2024) — floor; WCAG 3.0 still Working Draft, no compliance action | audit E (see A11Y standard) |
| OWASP ASVS | **5.0** | audit F target = L2 (see security standard) |
| Model Cards / Datasheets | Mitchell et al. / Gebru et al.; HF Hub spec current | audit D transparency artifacts |

> **Most repos in this portfolio are not EU-AI-Act-high-risk and not ISO-42001-certified.** The obligation is not certification; it is the *decision artifact*. A two-line "EU AI Act classification: minimal-risk, not Annex III, rationale: …" committed file satisfies the REVIEW-GATE. Silence does not.

---

## What gets committed into each repo

For each applicable audit, the repo's `docs/RESPONSIBLE-TECH-AUDITS.md` (and, where the audit is machine-generated, `docs/audits/*.md` or `*.json` artifacts) contains:

1. The **findings** (risks specific to this project).
2. The **checklist** (each item marked AUTO-GATED or REVIEW-GATED, with the owning standard linked for the numeric threshold).
3. The **committed report/artifact** (the eval run, the axe report, the DPIA, the model card, the risk register), regenerated by `make verify` / release CI and updated on every release.

This is the literal meaning of "baking the reports into the repo": the audit is a **build artifact**, regenerated and re-committed, never a one-time PDF. This "audit-as-artifact" discipline — DPIA, ACR/VPAT, threat models, data/model cards, residual-risk registers, regenerated on release — is already this portfolio's signature strength and is rare even in regulated industries. The work ahead is propagating it to the repos that lag, not inventing it.

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

Last verified: 2026-06-21 · Recheck cadence: quarterly, and immediately on any revision to NIST AI RMF / AI 600-1, ISO 42001, EU AI Act enforcement phases, WCAG, or OWASP ASVS / LLM Top 10. (Confirm current framework versions at build time.)
