"""Fail when the implementation drifts from the reviewed v1 candidate.

Every field compared here is recomputed from the implementation. Anything that
cannot be is not compared at all, because a field built out of the snapshot and
then compared to the snapshot reports a pass it did not earn: ``contractVersion``
used to be read straight out of the file it was checked against, so it could not
mismatch under any code change, and ``cliExitCodes`` was three literals retyped
inside this script rather than the numbers the CLI exits with.

``pythonExports`` was the third of those, less obviously: it read each module's
``__all__``, which is a declaration of the export list and not the export list
itself. See :func:`_exports`.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import tods_validate
import tods_validate.read
import tods_validate.testing
from tods_validate.policy import EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE
from tods_validate.report import REPORT_SCHEMA_VERSION
from tods_validate.rules import all_rules
from tods_validate.schema import SUPPORTED_SPEC_VERSIONS

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs" / "v1-contract-candidate.json"
REPORT_SCHEMA = ROOT / "docs" / "report.schema.json"

# In the snapshot but deliberately not recomputed: it names the snapshot rather
# than describing the implementation, so there is nothing to derive it from and
# nothing it could disagree with. main() checks it is present and non-empty.
UNCHECKED_FIELDS = ("contractVersion",)


def _exports(name: str, module: ModuleType) -> list[str]:
    """``module.__all__``, resolved against the module rather than trusted.

    ``__all__`` is what a module *says* it exports. The v1 contract is a
    promise about what ``from tods_validate import X`` does, and the two part
    company on any rename that leaves the list behind: the name disappears
    from the package while the list, the snapshot, and this comparison all
    still agree with each other. Reading the list alone made this field the
    same self-comparison ``contractVersion`` used to be, and a stale
    ``tods_validate.__all__`` entry passed this gate and the entire test suite
    with the export gone.
    """
    unresolved = [export for export in module.__all__ if not hasattr(module, export)]
    if unresolved:
        raise SystemExit(
            f"{name} lists {', '.join(unresolved)} in __all__ but does not define "
            f"{'them' if len(unresolved) > 1 else 'it'}: the published export is broken, "
            "so there is no contract to compare."
        )
    return list(module.__all__)


def _actual_contract() -> dict[str, object]:
    report_schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    finding_schema = report_schema["properties"]["findings"]["items"]
    return {
        # Read from tods_validate.policy, which is what cli.py exits with; the
        # behavioral goldens for all three are in tests/test_policy.py.
        "cliExitCodes": {
            "clean": EXIT_CLEAN,
            "findingsAtOrAboveThreshold": EXIT_FINDINGS,
            "usageOrInputError": EXIT_USAGE,
        },
        "supportedSpecVersions": list(SUPPORTED_SPEC_VERSIONS),
        "jsonReport": {
            "reportVersion": REPORT_SCHEMA_VERSION,
            "requiredTopLevel": report_schema["required"],
            "requiredFindingFields": finding_schema["required"],
        },
        "pythonExports": {
            name: _exports(name, module)
            for name, module in (
                ("tods_validate", tods_validate),
                ("tods_validate.read", tods_validate.read),
                ("tods_validate.testing", tods_validate.testing),
            )
        },
        "rules": [
            [rule.id, rule.severity.name, rule.category]
            for rule in sorted(all_rules(), key=lambda item: (int(item.id[-3:]), item.id))
        ],
    }


def drift() -> tuple[dict[str, object], dict[str, object]]:
    """The snapshot's checkable fields and the implementation's, for comparison.

    Both sides carry exactly the same keys, so a field that stops being
    recomputed shows up as a mismatch instead of quietly dropping out of the
    comparison.
    """
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    missing = [f for f in UNCHECKED_FIELDS if not snapshot.get(f)]
    if missing:
        raise SystemExit(f"snapshot is missing {', '.join(missing)}")
    expected = {k: v for k, v in snapshot.items() if k not in UNCHECKED_FIELDS}
    return expected, _actual_contract()


def main() -> int:
    expected, actual = drift()
    if actual == expected:
        print("v1 public-contract candidate is current")
        return 0
    print("v1 public-contract candidate has drifted")
    print("Expected snapshot:")
    print(json.dumps(expected, indent=2))
    print("Actual implementation:")
    print(json.dumps(actual, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
