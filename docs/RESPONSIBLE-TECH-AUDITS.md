# Responsible-Tech Audits — tods-validate

Instantiates `docs/standards/RESPONSIBLE-TECH-FRAMEWORK.md` (vendored
2026-07-05, portfolio-standards v1.0.1). Last regenerated: 2026-07-05,
Chelsea Kelly-Reif (sole maintainer). Regenerate this file at every release
(RTF-08); the "findings" below should be re-read against the current code,
not assumed still true.

## Applicability

- **A Ethics:** applies — a validator that gets it wrong (false-clean or
  false-error) can mislead a real transit agency's compliance decisions.
- **B Bias:** N/A — `tods-validate` checks CSV rows against a published
  schema and spec citations. It does not rank, recommend, classify, or serve
  different outcomes to different people or groups; there are no protected
  attributes, no personalization, and no per-user/per-agency behavioral
  differences in the check logic. Nothing here to disaggregate a metric by.
- **C Privacy:** applies (DPIA-lite below) — `employee_run_dates.txt` and
  `vehicles.txt` can carry person- and vehicle-identifying values; the
  `anonymize` subcommand exists specifically to address this.
- **D Transparency:** applies — every finding cites a spec section and is
  meant to be an honest, checkable claim (see "Findings" below).
- **E Accessibility:** applies, scoped — `--format html` report + `web/`
  playground. See README `## Accessibility`; a formal ACR/VPAT and automated
  axe/pa11y/Lighthouse CI gates are tracked as an open gap
  (`docs/CONFORMANCE-GAPS.md#accessibility`), not yet built.
- **F Security:** applies (threat model: `SECURITY.md`).
- **AI-EVALUATION:** N/A — no LLM, embedding model, or other AI/ML
  component anywhere in `src/` or `scripts/`. Verified: no LLM SDK imports
  (`anthropic`, `openai`, `transformers`, etc.) in the codebase. The rule
  engine is a deterministic, hand-written registry of check functions
  (`src/tods_validate/rules/`); there is no model to card, red-team, or
  classify under the EU AI Act.
- **I18N:** N/A — see `docs/I18N.md` (declared, dated, CI-enforced).

## A. Ethics & responsibility audit

**Findings.** Primary users are transit-agency schedulers and the vendors
who export TODS feeds on their behalf; the working group (MobilityData/
Cal-ITP successors) is a secondary audience judging the tool as a
contribution candidate. Non-users affected: the employees and vehicles named
in `employee_run_dates.txt`/`vehicles.txt`, who did not choose to be in this
data and cannot see or correct it through this tool.

Worst plausible misuse: none identified that is specific to this tool beyond
what any CSV-reading CLI carries (see loader hardening in Security below) —
there is no network effect, no aggregation across agencies, and no output
that leaves the operator's machine unless they choose to share it.

Worst plausible failure mode ("who could be hurt if this works exactly as
intended?"): a false negative — the validator reports "no problems found"
on a feed that is actually wrong — could let a bad operational feed ship
unnoticed into a scheduling system, with downstream effects on real crew
assignments. This is the reason `RunCoverage`/the coverage manifest
(`docs/report.schema.json` `coverage` field, added in schema 1.2.0) exists:
a clean report now discloses which rules ran versus were skipped and why,
rather than implying a full check happened when it did not (e.g. no
companion GTFS was supplied, so GTFS-cross-reference rules were skipped).
"Ran" has to mean ran for that disclosure to be worth anything: a rule whose
GTFS file the companion feed does not carry is reported
`skipped:needs_gtfs_table`, because a check with nothing to read has not
earned the clean result it would otherwise contribute to.

**Commitments.**
- Non-goals, stated in README `## What this does not check`: this tool does
  not validate GTFS itself and does not judge feed quality beyond the spec
  ("facts about a feed, not a quality score" — `tods-validate stats`).
- No kill-switch is applicable (local CLI, no hosted service to disable).
- Accountable owner: Chelsea Kelly-Reif (sole maintainer today).

**Enforcement.**
- REVIEW-GATE: this consequence scan, committed and dated above.
- AUTO-GATE: the coverage-manifest disclosure (`tests/test_coverage_advisory.py`)
  is a mechanical guarantee that a report states its own scope. There is no
  mechanical "misuse" test beyond the loader-safety tests covered under
  Security, because the ethical risk here is a correctness/completeness
  risk, not a misuse-of-the-tool risk.

## B. Bias & fairness audit

N/A (see Applicability). Recorded here rather than silently omitted, per
RTF-03: `tods-validate` has no ranking, recommendation, or classification
surface across people or groups. If a future feature ever scores or ranks
agencies, vendors, or individuals, this section must be revisited before
that feature ships.

## C. Privacy & data-protection audit (DPIA-lite)

**Data inventory.** `employee_run_dates.txt` (employee identifiers) and
`vehicles.txt` (vehicle/license identifiers) are the only TODS files that
can carry person- or asset-identifying values. `tods-validate` reads them
locally to check references and never transmits them anywhere (`SECURITY.md`
"No network access"). Lawful basis / justification is out of this tool's
control — it validates whatever feed the operator points it at — but the
tool's own footprint is: read in, findings out, nothing persisted beyond
what the operator chooses to write (`--format`, `fix -o`, `anonymize -o`).

**Threat model for the people in the data.** The realistic threat is
re-identification if a feed (or a validation report quoting feed values,
e.g. an error message echoing an `employee_id`) is shared outside the
agency — for example pasted into a public GitHub issue while reporting a
bug. `anonymize` exists to let an operator scrub identifying fields before
sharing; CONTRIBUTING's "No real agency data" house rule additionally
forbids real feeds from ever entering this repo's own issue tracker or
fixtures.

**Commitments.**
- No retention: the tool holds data only for the lifetime of the process.
- No third-party exfiltration: enforced structurally (no network calls
  anywhere in `validate`/`merge`/`stats`/`anonymize`; see Security).
- `anonymize` pseudonymizes person/vehicle-identifying fields before a feed
  is shared; `SECURITY.md` is explicit that pseudonymization is not a
  guarantee of anonymity (correlation with other datasets could still
  re-identify someone), and recommends a random (not stable) salt unless
  cross-export stable pseudonyms are specifically required.
- No subject-access/deletion path is applicable: this tool holds no data of
  its own, only whatever the operator feeds it and discards output paths
  they control.

**Enforcement.**
- AUTO-GATE: `tests/test_loader_safety.py` (no path traversal, no zip-bomb
  resource exhaustion); no-network is structural (no HTTP client dependency
  in the runtime install — `dependencies = ["click>=8.1"]`); gitleaks
  pre-commit + CI secret scanning added 2026-07-05 (`make secrets`).
- REVIEW-GATE: this DPIA-lite, committed and dated above. Promote to a
  fuller DPIA if this tool ever ingests a data field not already named here.

## D. Transparency & explainability audit

**Findings.** Every finding names a rule ID, a file/row/field, a message,
and a spec citation (`spec_section` on every `Rule`, surfaced via
`tods-validate rules --format json` and `docs/rules.md`). Ambiguous spec
readings are tracked as first-class findings for the working group in
`docs/spec-questions.md` rather than silently guessed. The `stats` and
`anonymize` subcommands are explicit about what they are *not*: `stats` is
documented as "facts about a feed, not a quality score"; `anonymize` is
documented as pseudonymization, not anonymity (see C above). The JSON report
schema (`docs/report.schema.json`) is versioned and additive-only, so a
consumer can tell what shape of claim it is parsing.

**Commitments.** Every finding is attributable to a spec section; every
suggestion (`--suggest`) states whether it is `auto` (meaning-preserving,
safe to apply unattended) or `review` (derived but needs a human to confirm
intent) — never presented as more certain than it is.

**Enforcement.**
- AUTO-GATE: `tests/test_conformance.py` requires every registered rule to
  have a fixture and a spec citation (no rule without a `spec_section`);
  `scripts/generate_rules_doc.py --check` keeps the published catalog from
  drifting from the code that actually runs.
- REVIEW-GATE: honesty-of-framing review is exercised informally on every
  PR per CONTRIBUTING's "Honesty in claims" house rule; no dedicated
  artifact beyond this document today.

## E. Accessibility audit

Findings, commitments, and current gaps are tracked in
`docs/CONFORMANCE-GAPS.md#accessibility` and the README `## Accessibility`
section, per the scope note in Applicability above. Not duplicated here —
see `docs/standards/ACCESSIBILITY-STANDARD.md` for the owning gate
thresholds.

## F. Security audit

**Findings and threat model:** `SECURITY.md` (untrusted TODS/GTFS input;
zip-bomb, path-traversal, and no-code-execution defenses in
`src/tods_validate/loader.py`, tested in `tests/test_loader_safety.py`).

**ASVS level:** not formally scored. This tool is a local CLI/library with
no network listener, no authentication surface, and no persistent storage
of its own, so most ASVS v5.0 controls (session management, access control,
authenticated communications) do not have a surface to apply to. The
applicable subset — input validation (V1/V5-style: size caps, format
rejection), and secure coding practice (no `eval`/`exec` on feed content,
dependency and secret scanning) — is met per the residual-risk register
below. Declaring a numeric ASVS level (e.g. "L1") would overstate rigor for
a tool with no auth/session boundary; the honest statement is: *ASVS's
authenticated-application controls are N/A by shape; the input-handling and
supply-chain controls that do apply are enforced and tested.*

**Residual-risk register (dated 2026-07-05):**

| Risk | Residual likelihood/impact | Mitigation | Owner |
|---|---|---|---|
| Zip-bomb / oversized archive exhausts CI runner memory | Low / Medium — caps are unit-tested but a future format change could bypass them | `MAX_FILE_BYTES`/`MAX_TOTAL_BYTES`/`MAX_COMPRESSION_RATIO` in `loader.py`, tested | Chelsea Kelly-Reif |
| Pseudonymization re-identification via cross-dataset correlation | Medium / Medium — inherent to pseudonymization, not fixable by this tool alone | Documented limitation in `SECURITY.md` and here; default random salt | Chelsea Kelly-Reif |
| Playground (`web/`) depends on a third-party CDN (jsdelivr) for the Pyodide runtime | Low / Low — SRI hash added 2026-07-05 constrains it to a byte-exact, verified artifact | `integrity`/`crossorigin` on the `<script>` tag (`web/index.html`) | Chelsea Kelly-Reif |
| Solo-maintainer self-review — no independent second reviewer on any merge | Medium / Medium — structural, not a code fix | Noted honestly in `docs/CONFORMANCE-GAPS.md#ci-cd`; CODEOWNERS added ahead of a second maintainer joining | Chelsea Kelly-Reif |

**Enforcement.**
- AUTO-GATE (added/confirmed 2026-07-05): Semgrep (`ci --config auto`),
  CodeQL (`python` + `actions`), gitleaks (pre-commit + CI, no
  `continue-on-error`), `pip-audit --strict` (blocking, no mute pattern),
  Trivy image scan (`CRITICAL,HIGH`, blocking) in `docker.yml`, zizmor
  workflow-SAST on any PR touching `.github/workflows/**`, all `uses:`
  SHA-pinned (33/33, verified in the 2026-07-05 audit).
- REVIEW-GATE: this residual-risk register, committed and dated above;
  regenerate at each release per RTF-08.

## Governance (AI repos only)

N/A — no AI system in this repo (see Applicability, AI-EVALUATION). No risk
register, impact assessment, SoA, or EU AI Act classification artifact is
applicable.
