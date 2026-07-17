"""Fail when the implementation drifts from the reviewed v1 candidate."""

from __future__ import annotations

import json
from pathlib import Path

import tods_validate
import tods_validate.read
import tods_validate.testing
from tods_validate.report import REPORT_SCHEMA_VERSION
from tods_validate.rules import all_rules
from tods_validate.schema import SUPPORTED_SPEC_VERSIONS

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs" / "v1-contract-candidate.json"
REPORT_SCHEMA = ROOT / "docs" / "report.schema.json"


def _actual_contract() -> dict[str, object]:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    report_schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
    finding_schema = report_schema["properties"]["findings"]["items"]
    return {
        "contractVersion": expected["contractVersion"],
        # Behavioral tests in tests/test_policy.py exercise all three values.
        "cliExitCodes": {
            "clean": 0,
            "findingsAtOrAboveThreshold": 1,
            "usageOrInputError": 2,
        },
        "supportedSpecVersions": list(SUPPORTED_SPEC_VERSIONS),
        "jsonReport": {
            "reportVersion": REPORT_SCHEMA_VERSION,
            "requiredTopLevel": report_schema["required"],
            "requiredFindingFields": finding_schema["required"],
        },
        "pythonExports": {
            "tods_validate": tods_validate.__all__,
            "tods_validate.read": tods_validate.read.__all__,
            "tods_validate.testing": tods_validate.testing.__all__,
        },
        "rules": [
            [rule.id, rule.severity.name, rule.category]
            for rule in sorted(all_rules(), key=lambda item: (int(item.id[-3:]), item.id))
        ],
    }


def main() -> int:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    actual = _actual_contract()
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
