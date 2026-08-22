# 0001 — Python floor stays at 3.11; dev interpreter pinned to CI's gate version

- Status: superseded by 0006 (2026-08-21; decision was in force 2026-07-09 to 2026-08-21)
- Date: 2026-07-09

## Context

The portfolio code-quality standard prefers a newer minimum Python. This
project's audience includes transit agencies and vendors running validators
inside CI images and analyst workstations that move slowly; a high floor
costs exactly the adopters the tool exists for. README states "Requires
Python 3.11 or newer" and CI tests 3.11, 3.12, and 3.13.

## Decision

- `requires-python = ">=3.11"` stands. The floor rises only when a runtime
  dependency forces it or 3.11 leaves upstream support, and the change gets
  its own ADR and a minor-version release note.
- `.python-version` pins the local development interpreter to 3.12, the same
  version CI uses for its lint/typecheck/docs gates, so `make verify` locally
  sees what CI sees. (The audit note suggested 3.13; gate parity with CI was
  judged more valuable than the newest interpreter. CI workflows pass
  explicit versions everywhere, so the file changes nothing in CI.)

## Consequences

- Source stays inside the 3.11 feature set (no 3.12+-only syntax).
- The 3.11/3.12/3.13 test matrix remains the proof the floor is real.
- Deviation from the standard's preferred floor is declared in
  `docs/CONFORMANCE-GAPS.md` (CQ-01) and is now documented here rather than
  only implied by the README.
