"""Handoff records: a go/no-go decision bound to the bytes it was made about.

The ``ingest-ready`` profile answers whether a CAD/AVL system should import a
feed, and ``--stamp`` says which tool version answered. Neither binds the
answer to the bytes. A handoff record does. It carries the SHA-256 of every
file in the package and in its companion GTFS feed, the settings the decision
was reached under, the coverage manifest, the merge manifest, and the decision
with the rule IDs behind it. ``handoff verify`` re-hashes what it is handed and
recomputes the record, so the receiving system can check that the record
describes the bytes it received instead of taking the sender's word for it.

What "accept" requires
----------------------
Nothing at or above the settings' ``fail-on`` severity, and every check that
wanted an input got one. A record made without a companion GTFS feed carries
"reject" whatever its findings say: its reference checks never ran, and a
go/no-go record that said "go" about references nobody resolved would be a
confident answer to a question nobody asked. That is ``--require-complete-run``'s
rule, and a handoff always applies it.

Why there is no timestamp
-------------------------
The record is a pure function of the input bytes, the settings and the tool
version, so ``verify`` can recompute it exactly and compare. A timestamp would
make every record unique and every recomputation a mismatch.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from . import __version__
from .findings import Finding, Severity
from .loader import PackageNotFoundError
from .merge import _iter_raw_files, merge_feeds
from .policy import EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE, GatingPolicy
from .report import summarize
from .rules import RunCoverage
from .runner import run_with_coverage
from .schema import GTFS_COMPANION_FILENAMES

HANDOFF_VERSION = "1.0.0"
# The SSH signature namespace. Separate from the "git" namespace release tags
# are signed under, so a tag signature can never be replayed as a signature
# over a handoff record, or the other way round.
SIGNATURE_NAMESPACE = "tods-validate-handoff"
ACCEPT = "accept"
REJECT = "reject"

_THRESHOLD = {"error": Severity.ERROR, "warning": Severity.WARNING, "info": Severity.INFO}


@dataclass(frozen=True)
class HandoffSettings:
    """Everything that decides a handoff, resolved, so a record can be replayed.

    The record stores these values rather than the profile's name alone: a
    profile is a preset this tool may change, and a record replayed next year
    has to mean what it meant the day it was written.
    """

    profile: str | None
    fail_on: str
    enable: tuple[str, ...]
    ignore: tuple[str, ...]
    spec_version: str
    encoding: str | None
    severity_remap: tuple[tuple[str, str], ...]
    max_implied_speed_kph: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "failOn": self.fail_on,
            "enable": list(self.enable),
            "ignore": list(self.ignore),
            "specVersion": self.spec_version,
            "encoding": self.encoding,
            "severityRemap": dict(self.severity_remap),
            "maxImpliedSpeedKph": self.max_implied_speed_kph,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> HandoffSettings:
        """Read settings back out of a record. ValueError when they cannot be used."""
        remap, enable, ignore = data["severityRemap"], data["enable"], data["ignore"]
        if not isinstance(remap, dict) or not isinstance(enable, list):
            raise ValueError("severityRemap must be an object and enable a list")
        if not isinstance(ignore, list):
            raise ValueError("ignore must be a list")
        fail_on = str(data["failOn"])
        if fail_on not in _THRESHOLD:
            raise ValueError(f"failOn {fail_on!r} is not one of {', '.join(_THRESHOLD)}")
        profile, encoding, speed = data["profile"], data["encoding"], data["maxImpliedSpeedKph"]
        return cls(
            profile=profile if isinstance(profile, str) else None,
            fail_on=fail_on,
            enable=tuple(str(item) for item in enable),
            ignore=tuple(str(item) for item in ignore),
            spec_version=str(data["specVersion"]),
            encoding=encoding if isinstance(encoding, str) else None,
            severity_remap=tuple((str(k), str(v)) for k, v in remap.items()),
            max_implied_speed_kph=float(speed) if isinstance(speed, (int, float)) else None,
        )


def file_digests(path: Path) -> list[dict[str, object]]:
    """``{name, sha256, bytes}`` for every top-level file of a directory or zip.

    Read by the same function ``merge`` reads a package with, so "the files of
    the package" means one thing in this project rather than two.
    """
    return [
        {"name": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name, data in _iter_raw_files(path)
    ]


def decide(
    findings: list[Finding], coverage: RunCoverage, settings: HandoffSettings
) -> tuple[str, dict[str, list[str]]]:
    """``accept`` or ``reject``, and the rule IDs behind it."""
    gate = GatingPolicy(fail_on=settings.fail_on, ignore=frozenset(settings.ignore)).apply(findings)
    threshold = _THRESHOLD[settings.fail_on]
    blocking = sorted({f.rule_id for f in gate.gating if f.severity >= threshold})
    if bool(blocking) != gate.failed:
        # Two readings of one gate. If they ever disagree, a record would say
        # one thing and the exit code another, so refuse rather than pick one.
        raise RuntimeError("handoff decision and gating policy disagree about the findings")
    not_run = sorted(outcome.id for outcome in coverage.unrequested_skips)
    decision = REJECT if blocking or not_run else ACCEPT
    return decision, {"blockingRules": blocking, "checksNotRun": not_run}


def _merge_manifest(feed: Path, gtfs: Path | None) -> dict[str, object]:
    """The supplement merge's per-file accounting, and a digest of what it writes."""
    with TemporaryDirectory() as tmp:
        output = Path(tmp) / "merged"
        try:
            result = merge_feeds(feed, gtfs, output)
        except PackageNotFoundError as exc:
            return {"status": "not-produced", "reason": str(exc)}
        return {
            "status": "produced",
            "files": {name: asdict(stats) for name, stats in sorted(result.stats.items())},
            "written": file_digests(output),
        }


def _companion(feed: Path, gtfs: Path | None) -> dict[str, object] | None:
    if gtfs is not None:
        return {"source": "flag", "files": file_digests(gtfs)}
    # Mirrors runner.run_with_coverage: a package carrying GTFS files that TODS
    # IDs resolve against is its own companion. Its files are already hashed
    # under "package", so nothing is repeated here.
    names = {entry["name"] for entry in file_digests(feed)}
    if names & set(GTFS_COMPANION_FILENAMES):
        return {"source": "package"}
    return None


def build_record(feed: Path, gtfs: Path | None, settings: HandoffSettings) -> dict[str, object]:
    """The handoff record for ``feed`` (and ``gtfs``) under ``settings``."""
    package_files = file_digests(feed)
    companion = _companion(feed, gtfs)
    _, findings, coverage = run_with_coverage(
        feed,
        gtfs,
        enabled=frozenset(settings.enable),
        encoding=settings.encoding,
        severity_remap=dict(settings.severity_remap),
        spec_version=settings.spec_version,
        max_implied_speed_kph=settings.max_implied_speed_kph,
    )
    decision, basis = decide(findings, coverage, settings)
    kept = [f for f in findings if f.rule_id not in settings.ignore]
    if len(kept) != len(findings):
        coverage = coverage.with_ignored(settings.ignore)
    counts = summarize(kept)
    return {
        "handoffVersion": HANDOFF_VERSION,
        "tool": {"name": "tods-validate", "version": __version__},
        "specVersion": settings.spec_version,
        "inputs": {"package": {"files": package_files}, "companion": companion},
        "settings": settings.to_dict(),
        "decision": decision,
        "decisionBasis": basis,
        "summary": {
            "errors": counts[Severity.ERROR],
            "warnings": counts[Severity.WARNING],
            "infos": counts[Severity.INFO],
        },
        "coverage": coverage.to_dict(),
        "merge": _merge_manifest(feed, gtfs),
    }


def render_record(record: dict[str, object]) -> str:
    """The record as written to disk. Stable: same record, same bytes."""
    return json.dumps(record, indent=2) + "\n"


@dataclass(frozen=True)
class VerifyResult:
    exit_code: int
    lines: list[str]


def _shape_problem(record: object) -> str | None:
    """Why ``record`` cannot be checked by this version, or None."""
    if not isinstance(record, dict):
        return "it is not a JSON object"
    version = record.get("handoffVersion")
    if not isinstance(version, str) or version.split(".")[0] != HANDOFF_VERSION.split(".")[0]:
        return f"handoffVersion {version!r} is not a {HANDOFF_VERSION.split('.')[0]}.x record"
    for key in ("inputs", "settings", "decision", "decisionBasis", "tool"):
        if key not in record:
            return f"it has no {key!r}"
    inputs = record["inputs"]
    if not isinstance(inputs, dict) or not isinstance(inputs.get("package"), dict):
        return "its inputs do not name a package"
    if not isinstance(record["settings"], dict):
        return "its settings are not an object"
    return None


def _file_differences(label: str, recorded: object, actual: list[dict[str, object]]) -> list[str]:
    if not isinstance(recorded, list) or not all(isinstance(e, dict) for e in recorded):
        return [f"{label}: the record's file list cannot be read"]
    before = {str(entry.get("name")): entry.get("sha256") for entry in recorded}
    after = {str(entry["name"]): entry["sha256"] for entry in actual}
    missing = sorted(before.keys() - after.keys())
    added = sorted(after.keys() - before.keys())
    changed = sorted(name for name in before.keys() & after.keys() if before[name] != after[name])
    return [
        *(f"{label}: {name} is in the record and not in what was given" for name in missing),
        *(f"{label}: {name} was given and is not in the record" for name in added),
        *(
            f"{label}: {name} differs (record {before[name]}, given {after[name]})"
            for name in changed
        ),
    ]


def _input_differences(record: dict[str, object], feed: Path, gtfs: Path | None) -> list[str]:
    inputs = record["inputs"]
    package = inputs.get("package") if isinstance(inputs, dict) else None
    if not isinstance(inputs, dict) or not isinstance(package, dict):
        return ["the record's inputs cannot be read"]
    lines = _file_differences("package", package.get("files"), file_digests(feed))
    companion = inputs.get("companion")
    flagged = isinstance(companion, dict) and companion.get("source") == "flag"
    if flagged and gtfs is None:
        lines.append(
            "companion: the record was made with a companion GTFS feed, and none was given"
        )
    elif not flagged and gtfs is not None:
        lines.append(
            "companion: the record was made without a separate companion GTFS feed, and "
            "one was given"
        )
    elif isinstance(companion, dict) and gtfs is not None:
        lines += _file_differences("companion", companion.get("files"), file_digests(gtfs))
    return lines


def verify_record(record_path: Path, feed: Path, gtfs: Path | None) -> VerifyResult:
    """Check that the record at ``record_path`` describes ``feed`` and ``gtfs``.

    Exit codes follow the CLI's: 0 the record matches; 1 re-running under the
    record's settings does not reproduce it (its decision, or anything else it
    states); 2 the bytes differ from the ones it hashed, or it cannot be read.
    """
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return VerifyResult(EXIT_USAGE, [f"the record {record_path} could not be read: {exc}"])
    problem = _shape_problem(record)
    if problem is not None:
        return VerifyResult(
            EXIT_USAGE, [f"{record_path} is not a handoff record this version can check: {problem}"]
        )
    try:
        differences = _input_differences(record, feed, gtfs)
    except PackageNotFoundError as exc:
        return VerifyResult(EXIT_USAGE, [str(exc)])
    if differences:
        return VerifyResult(
            EXIT_USAGE,
            ["hashes differ: the record does not describe the bytes it was given.", *differences],
        )
    try:
        settings = HandoffSettings.from_dict(record["settings"])
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        return VerifyResult(EXIT_USAGE, [f"{record_path}: its settings cannot be read ({exc!r})"])
    fresh = build_record(feed, gtfs, settings)
    recorded_tool = record["tool"].get("version") if isinstance(record["tool"], dict) else None
    tool_note = (
        []
        if recorded_tool == __version__
        else [
            f"note: the record was written by tods-validate {recorded_tool} and checked by "
            f"{__version__}; a different version can reach a different result about the same "
            "bytes."
        ]
    )
    # Everything but the tool block is recomputed and compared: a record whose
    # decision was left alone but whose coverage was edited to hide a skipped
    # check is as wrong as one whose decision was flipped.
    differing = [key for key in fresh if key != "tool" and fresh[key] != record.get(key)]
    unexpected = sorted(set(record) - set(fresh))
    if differing or unexpected:
        lines = [
            "not reproduced: re-running under the record's settings gives a different "
            f"{', '.join(differing + unexpected)} than the record states."
        ]
        if "decision" in differing:
            lines.append(
                f"decision: the record says {record['decision']!r}; these bytes give "
                f"{fresh['decision']!r} ({json.dumps(fresh['decisionBasis'])})."
            )
        return VerifyResult(EXIT_FINDINGS, lines + tool_note)
    return VerifyResult(
        EXIT_CLEAN,
        [
            "verified: the record describes these bytes, and re-running under its settings "
            f"reproduces it, decision {record['decision']!r}.",
            *tool_note,
        ],
    )


def signature_path(record_path: Path) -> Path:
    return record_path.with_name(record_path.name + ".sig")


def _ssh_keygen() -> str:
    found = shutil.which("ssh-keygen")
    if found is None:
        raise RuntimeError(
            "ssh-keygen was not found on PATH; signing and checking a record needs OpenSSH 8.1 "
            "or later"
        )
    return found


def sign_record(record_path: Path, key_path: Path) -> Path:
    """Write a detached SSH signature beside the record, ``<record>.sig``.

    ``ssh-keygen -Y sign`` under :data:`SIGNATURE_NAMESPACE`: the convention
    the release tags use, in a namespace of its own. A signature left over from
    an earlier record is removed first, so a failed signing cannot leave a
    valid-looking signature over different bytes.
    """
    signature_path(record_path).unlink(missing_ok=True)
    argv = [_ssh_keygen(), "-Y", "sign", "-f", str(key_path), "-n", SIGNATURE_NAMESPACE]
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell; paths are the caller's
        [*argv, str(record_path)], capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode(errors="replace").strip() or "ssh-keygen failed")
    return signature_path(record_path)


def verify_signature(record_path: Path, allowed_signers: Path, signer: str) -> str | None:
    """None when ``<record>.sig`` verifies for ``signer``; otherwise why it does not."""
    sig = signature_path(record_path)
    if not sig.is_file():
        return f"there is no signature at {sig}"
    argv = [_ssh_keygen(), "-Y", "verify", "-f", str(allowed_signers), "-I", signer]
    argv += ["-n", SIGNATURE_NAMESPACE, "-s", str(sig)]
    with record_path.open("rb") as handle:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell; paths are the caller's
            argv, stdin=handle, capture_output=True, check=False
        )
    if completed.returncode == 0:
        return None
    return completed.stderr.decode(errors="replace").strip() or "ssh-keygen -Y verify refused it"


__all__ = [
    "ACCEPT",
    "HANDOFF_VERSION",
    "REJECT",
    "SIGNATURE_NAMESPACE",
    "HandoffSettings",
    "VerifyResult",
    "build_record",
    "decide",
    "file_digests",
    "render_record",
    "sign_record",
    "signature_path",
    "verify_record",
    "verify_signature",
]
