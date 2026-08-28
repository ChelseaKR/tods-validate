#!/usr/bin/env python3
"""Notice when a phase gated on somebody else has become workable.

`docs/MULTIYEAR-PLAN.md` separates work this repository can do from work gated
on other people: the TODS Board, an agency with a feed, a person with a screen
reader. Phase 5 is entirely in the second category and phase 6's two bets each
carry a written trigger. The plan's own rule is that "a phase is not scheduled
until it can be worked", which leaves one question nothing answered: how would
anybody find out that it can be?

By re-reading the gates. `docs/phase-gates.json` records the state each was
last observed in and when. This fetches them again and reports every one whose
state has moved. `.github/workflows/phase-gates.yml` runs it monthly and opens
an issue on any change.

The failure mode this is written against is the one phase 1 fixed three times
over. A tripwire that reports "nothing changed" for a document it could not
read is worse than no tripwire, because it converts an outage into a green
tick. So:

* A gate it could not read is a **failure**, never "unchanged". The report
  names it and the exit code is non-zero.
* A run that read nothing at all raises rather than reporting eight unchanged
  gates.
* Every run prints the gates it compared, including on a clean run, so a
  report that inspected two of eight cannot be mistaken for one that inspected
  all of them.

Usage:

    python scripts/check_phase_gates.py
    python scripts/check_phase_gates.py --update    # rewrite the recorded states
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATES = ROOT / "docs" / "phase-gates.json"
# The heading .github/workflows/phase-gates.yml greps stdout for. A change and
# an unreadable gate both land under it, because "we could not look" is news in
# the same way "it moved" is.
REPORT_HEADING = "## Phase gates: attention needed"


class Unreadable(Exception):
    """A gate could not be read. Never treated as 'unchanged'."""


def fetch_state(repo: str, kind: str, number: int) -> str:
    """The live state of one issue or pull request, or raise.

    Raises rather than returning a sentinel, so a caller cannot accidentally
    compare a failure against a recorded value and find them equal.
    """
    path = "issues" if kind == "issue" else "pulls"
    try:
        out = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["/usr/bin/env", "gh", "api", f"repos/{repo}/{path}/{number}", "--jq", ".state"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise Unreadable(f"{repo}#{number}: {exc}") from exc
    state = out.stdout.strip()
    if not state:
        raise Unreadable(f"{repo}#{number}: empty state")
    return state


def compare(document: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Return (changed, unreadable, compared) for every recorded gate."""
    changed: list[str] = []
    unreadable: list[str] = []
    compared: list[str] = []
    for gate in document["gates"]:
        label = f"{gate['repo']}#{gate['number']} ({gate['id']}, phase {gate['phase']})"
        try:
            state = fetch_state(gate["repo"], gate["kind"], int(gate["number"]))
        except Unreadable as exc:
            unreadable.append(f"{label}: could not be read: {exc}")
            continue
        compared.append(f"{label}: {state}")
        if state != gate["recordedState"]:
            changed.append(
                f"{label}: was {gate['recordedState']!r}, now {state!r}. "
                f"Trigger: {gate['trigger']} Unblocks: {gate['unblocks']}"
            )
    if not compared and not unreadable:
        raise Unreadable("no gates were compared; the recorded list is empty")
    return changed, unreadable, compared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="rewrite the recorded states")
    args = parser.parse_args()

    document = json.loads(GATES.read_text(encoding="utf-8"))
    changed, unreadable, compared = compare(document)

    print(
        f"gates recorded {document['recordedAt']}, compared {len(compared)} of "
        f"{len(document['gates'])}:"
    )
    for line in compared:
        print(f"  {line}")

    if args.update:
        states = {
            line.rsplit(": ", 1)[0].split("#")[1].split(" ")[0]: line.rsplit(": ", 1)[1]
            for line in compared
        }
        for gate in document["gates"]:
            if str(gate["number"]) in states:
                gate["recordedState"] = states[str(gate["number"])]
        document["recordedAt"] = datetime.now(UTC).date().isoformat()
        GATES.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(f"\nrewrote {GATES.relative_to(ROOT)}")
        return 0

    if changed or unreadable:
        print(f"\n{REPORT_HEADING}\n")
        for line in changed:
            print(f"- **Moved.** {line}")
        for line in unreadable:
            print(f"- **Not read.** {line} A gate nobody could read is not a gate that held.")
        print(
            f"\nCompared {len(compared)} of {len(document['gates'])} recorded gates. "
            "Re-record with `python scripts/check_phase_gates.py --update` once the "
            "change has been read into docs/MULTIYEAR-PLAN.md."
        )
        return 1

    print("\nevery recorded gate still holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
