# 0000 — Record architecture decisions

- Status: accepted
- Date: 2026-07-09

## Context

Several load-bearing decisions in this repo (the Python 3.11 floor, the i18n
N/A declaration, the nested VS Code extension project, the rules-as-registry
design, the uv lockfile migration) existed only as scattered README sentences
or commit messages. The 2026-07-05 conformance audit flagged the missing
decision log (CQ-44/45, DOC-04/05 in `docs/CONFORMANCE-GAPS.md`): a reviewer
could see each choice but not why it was made or what would change it.

## Decision

Keep architecture decision records in `docs/adr/`, numbered sequentially,
one decision per file, using this lightweight MADR-style shape: Status, Date,
Context, Decision, Consequences. A record is written when a decision would
surprise a competent new contributor, constrains future work, or deviates
from a standard the repo declares conformance to.

Records are immutable history: a reversed decision gets a new ADR that
supersedes the old one (the old record's Status changes to "superseded by
NNNN"), rather than an edit that rewrites the past.

## Consequences

- Decisions become reviewable in PRs like code.
- ADRs 0001–0005 backfill the decisions already in force; later decisions
  land with the change that makes them.
- One more doc surface to keep honest; the staleness cost is bounded because
  records are append-only.
