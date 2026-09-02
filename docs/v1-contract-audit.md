# v1 public-contract audit

Status: candidate, reviewed for v0.9.0, re-reviewed 2026-08-27. This becomes
the v1 contract only when v1.0.0 is released, and only after the preconditions
in [Before this becomes the contract](#before-this-becomes-the-contract) are
met. It is still a candidate today; every one of them is open.

The machine-readable snapshot is
[`v1-contract-candidate.json`](v1-contract-candidate.json). CI compares it to
the implementation on every pull request (`.github/workflows/ci.yml`, the
`contract` job), and `tests/test_public_contract.py` runs the same comparison in
the test suite, so contract changes cannot land as an incidental code edit.
Updating the snapshot is allowed before v1, but its diff must be reviewed as a
product compatibility decision.

Every field in the snapshot except `contractVersion` is recomputed from the
implementation and compared. `contractVersion` names the snapshot rather than
describing the code, so it is excluded by name instead of being compared
against itself.

The candidate contract covers:

- CLI exit codes: 0 for a clean gate, 1 for findings at or above the selected
  threshold, and 2 for usage or input errors. These are read from
  `tods_validate.policy` (`EXIT_CLEAN`/`EXIT_FINDINGS`/`EXIT_USAGE`), which is
  what `cli.py` exits with; the behavioral golden tests are in
  `tests/test_policy.py`.
- all rule IDs, their declared severity, and whether they are core, coverage,
  or advisory checks;
- the supported TODS spec versions;
- the public exports from `tods_validate`, `tods_validate.read`, and
  `tods_validate.testing`;
- the JSON report schema version and required top-level/finding fields.

Within v1, existing rule IDs will not be removed, reused, or renumbered. A
minor release may add rules. A rule's severity or default category is a
compatibility decision and must update this snapshot. JSON report fields may
be added within report schema major version 1, but existing fields will not be
removed or renamed. Public Python members may gain optional behavior without
removing or renaming existing members.

## v0.9 conformance decision

Skyqrose's response in
[upstream issue #152](https://github.com/MobilityData/transit-operational-data-standard/issues/152)
specifies the behavior now proposed in
[upstream PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156):
(`date`, `service_id`, `run_id`, `employee_id`) as the explicit
`employee_run_dates.txt` primary key. This candidate therefore makes exact
duplicates produce `TODS-E204`. `TODS-W408` remains in the registry as a
compatibility signal for consumers that already track that rule ID.
Human-readable reports group it under the `TODS-E204` root finding. The
downstream behavior is not release-eligible until the upstream wording lands.

The v1.0.0 release review should confirm this snapshot after one conformance-
only release has shipped without unreviewed rule-ID, severity, exit-code, or
report-schema drift.

## Before this becomes the contract

Phase 2 of [`MULTIYEAR-PLAN.md`](MULTIYEAR-PLAN.md) owns the promotion. As of
2026-08-27 these are what stand between the candidate and the contract. None
of them is an engineering task this repository can finish on its own, which is
why the document still says "candidate".

1. **A conformance-only release has to ship first**, and none has. The
   snapshot's promise is that it went one full release cycle unchanged;
   `v0.10.0` disqualified itself in its own release note (it added
   `TODS-E207` and changed coverage-manifest behavior in three commands), and
   the current `Unreleased` section changes validator behavior again. So the
   next release cannot be the qualifying one either, and the one after it can
   only qualify if it changes no rule ID, severity, category, exit code,
   export, or report schema field. Nothing enforces that but the reviewer;
   `make contract-check` tells you whether the snapshot drifted, not whether
   the release was allowed to.
2. **The `employee_run_dates.txt` primary key is undecided upstream.**
   [PR #156](https://github.com/MobilityData/transit-operational-data-standard/pull/156)
   was still open and last updated 2026-07-17 when this was written. Until it
   lands, `TODS-E204` versus `TODS-W408` is this repository's reading of a
   response in an issue thread, not published spec text, and freezing a
   contract on it would freeze a guess. This is the single hardest blocker,
   and it is gated on other people.
3. **The branch ruleset is live** as of 2026-09-01, and
   [`rulesets/main.json`](rulesets/main.json) is now the export of it rather
   than a statement of intent. `contract` is among the sixteen required
   checks, so the gate that protects this document's subject can no longer be
   red on a pull request that merges. Closed.
4. **`CICD-06`**, the PyPI trusted-publisher environment scoping, is still
   unset. Both halves are live settings changes.

What this pass did instead of promoting the document: closed the fail-open in
the gate the promotion would rest on. `pythonExports` was compared against
each module's `__all__`, so a rename that left the list behind passed this
gate, and the whole test suite, with a public export that no longer imported.
Freezing a contract verified that way would have frozen the verification
defect with it.
