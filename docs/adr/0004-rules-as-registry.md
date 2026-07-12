# 0004 — Rules are registry entries plus small functions, not a plugin system

- Status: accepted (backfilled 2026-07-09; design in force since v0.1.0)
- Date: 2026-07-09

## Context

A validator's rule set invites framework-building: plugin discovery,
third-party rule packages, dynamic loading. Every layer of that machinery
widens the API surface the project must keep stable, and this tool's core
promises are elsewhere: stable rule IDs, spec citations, scheduler-readable
messages, and a fixture-per-rule conformance contract enforced in CI.

## Decision

A rule is a registry entry (stable ID, severity, title, description, spec
citation, optional interpretation note) plus one check function yielding
`Finding`s, registered with the `@rule` decorator in
`src/tods_validate/rules/__init__.py` and grouped into band modules
(structure, fields, references, semantics, coverage). There is no external
plugin mechanism. Everything downstream — `docs/rules.md` generation and its
drift gate, the per-rule web pages, `explain`, the conformance corpus
`expectations.json`, SARIF descriptors — derives from the one registry.

Rule IDs are permanent: never renumbered, never reused (see
`docs/authoring-rules.md`).

## Consequences

- Adding a rule is a data change plus a function; contributors follow one
  documented path.
- Generated artifacts cannot drift from the source of truth without CI
  noticing.
- Third parties cannot ship out-of-tree rules; the extension point is a PR.
  If real demand for external rules appears, that is a new ADR with an
  explicit stability contract, not an incremental loosening.
