# v1 public-contract audit

Status: candidate, reviewed for v0.9.0. This becomes the v1 contract only when
v1.0.0 is released.

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
