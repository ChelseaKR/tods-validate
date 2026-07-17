# Real-feed validation record

Updated: 2026-07-16

The maintainer confirms that multiple real, non-synthetic TODS feed exports
have been used while testing `tods-validate`. Those feeds are private and are
not committed, attached to issues, or quoted in this repository. Exact feed
counts, producer identities, and operational values are intentionally not
claimed here because that metadata has not been recorded in a shareable form.

This closes the stale roadmap assumption that the project has no access to real
feeds. It does not turn private feeds into a reproducible public conformance
suite, establish adoption by a particular vendor, or prove producer diversity.
The fixture corpus remains the reviewable evidence for each rule.

## Evidence policy

When a private feed exposes a validator defect or an ambiguous interpretation:

1. reduce it to the smallest synthetic or irreversibly anonymized reproducer;
2. add the reproducer to the rule fixture or a focused regression test;
3. record the behavior change in the changelog without naming the producer;
4. link an upstream specification decision when the fix depends on one.

A clean private validation run may be recorded only at a coarse level: date,
validator version, TODS version, broad size band, and whether any regression
fixture resulted. Do not record agency names, vendor names, employee or vehicle
identifiers, exact routes, or feed contents.

## v1 implication

Real-feed access is no longer the v1 blocker. The remaining evidence bar is to
keep converting observed failures into reviewable regression cases and to ship
one conformance-only release without unreviewed drift in rule IDs, severities,
exit codes, or the report schema. See
[`v1-contract-audit.md`](v1-contract-audit.md).
