"""Run any validator over the conformance corpus and report where it disagrees.

The corpus is published so that other people can run it, and "run it and diff
the result against ``expectations.json``" has so far been left to each reader.
This module is that step, done once: it executes an external command over every
fixture, reads the rule identifiers back out of that command's own output
through a small declared adapter, and reports per fixture whether the two
agree.

Disagreement is the useful signal. A fixture where a second implementation
reports a rule this one does not -- or misses one this one produces -- is
either a bug in one of them or an ambiguity in the specification, and this
harness exists to find those, not to declare a winner. Nothing here judges
which side is right.

Fail-closed, and that is the whole design constraint
=====================================================

The failure this must not have is an adapter that reads nothing being reported
as a validator that found nothing. Both produce an empty list of rule
identifiers, and for the ``valid`` fixture -- whose expectation *is* the empty
list -- the second one would print ``agrees`` over a run that measured
nothing at all. That is this project's own "absence rendered as a value"
defect, in the tool built to compare measurements.

So the two states are separated structurally rather than by counting:

* a ``json`` adapter has read the output when the document parses **and** the
  array its pointer names is present. An empty array there is an answer: the
  validator ran and reported no rule. A document that does not parse, or a
  pointer that names nothing, is ``unreadable``.
* a ``regex`` adapter cannot tell those apart from the identifier pattern
  alone, so it must also declare ``no_findings_pattern`` -- an expression that
  matches what the tool prints when it is happy. Neither matching is
  ``unreadable``. This makes the regex strategy slightly more work to write,
  deliberately: the alternative is a strategy that reports agreement whenever
  it is pointed at the wrong stream.

An outcome of ``unreadable`` or ``timed_out`` is never folded into either
``agrees`` or ``disagrees``, and it decides the exit code, because "the
comparison did not happen" and "the comparison happened and matched" are the
two answers a summary must never merge.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess  # noqa: S404 - running a named validator is this module's purpose
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__

__all__ = [
    "AGREES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DISAGREES",
    "OUTCOMES",
    "PATH_PLACEHOLDER",
    "TIMED_OUT",
    "UNREADABLE",
    "Adapter",
    "AdapterError",
    "ConformanceReport",
    "Corpus",
    "CorpusError",
    "FixtureResult",
    "build_argv",
    "conformance_to_dict",
    "load_adapter",
    "load_corpus",
    "read_identifiers",
    "render_conformance_markdown",
    "render_conformance_text",
    "run_conformance",
]

# The command template must name this once, or every fixture would run the
# same command and the harness would report a hundred identical answers as a
# hundred measurements.
PATH_PLACEHOLDER = "{path}"

AGREES = "agrees"
DISAGREES = "disagrees"
UNREADABLE = "unreadable"
TIMED_OUT = "timed_out"

OUTCOMES = (AGREES, DISAGREES, UNREADABLE, TIMED_OUT)

_STRATEGIES = ("json", "regex")
_SOURCES = ("stdout", "stderr", "combined")

_EXPECTATIONS_NAME = "expectations.json"

DEFAULT_TIMEOUT_SECONDS = 120.0


class AdapterError(ValueError):
    """The adapter description cannot be used to read a validator's output."""


class CorpusError(ValueError):
    """The corpus cannot be read, so there is nothing to compare against."""


@dataclass(frozen=True)
class Adapter:
    """How to get rule identifiers out of one validator's output."""

    name: str
    strategy: str
    source: str
    pointer: tuple[str, ...] = ()
    pattern: re.Pattern[str] | None = None
    no_findings_pattern: re.Pattern[str] | None = None
    mapping: dict[str, str] | None = None

    def stream(self, stdout: str, stderr: str) -> str:
        if self.source == "stderr":
            return stderr
        if self.source == "combined":
            return f"{stdout}\n{stderr}"
        return stdout


@dataclass(frozen=True)
class Corpus:
    """The fixtures to run, and the digest naming exactly which ones."""

    root: Path
    label: str
    digest: str
    digest_kind: str
    expectations: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class FixtureResult:
    fixture: str
    outcome: str
    expected: tuple[str, ...]
    reported: tuple[str, ...]
    extra: tuple[str, ...]
    missing: tuple[str, ...]
    reason: str
    exit_code: int | None


@dataclass(frozen=True)
class ConformanceReport:
    adapter: str
    command: str
    corpus_label: str
    corpus_digest: str
    corpus_digest_kind: str
    harness_version: str
    timeout_seconds: float
    results: tuple[FixtureResult, ...]

    def count(self, outcome: str) -> int:
        return sum(1 for result in self.results if result.outcome == outcome)

    @property
    def unmeasured(self) -> int:
        """Fixtures that produced no comparison at all."""
        return self.count(UNREADABLE) + self.count(TIMED_OUT)

    @property
    def compared(self) -> int:
        return self.count(AGREES) + self.count(DISAGREES)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


def load_adapter(text: str) -> Adapter:
    """Parse an adapter description, refusing anything it could misread with."""

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"adapter is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise AdapterError("adapter must be a JSON object")

    name = str(raw.get("name") or "").strip()
    if not name:
        raise AdapterError("adapter needs a 'name', so a report says whose output it read")

    strategy = str(raw.get("strategy") or "")
    if strategy not in _STRATEGIES:
        raise AdapterError(f"adapter 'strategy' must be one of {', '.join(_STRATEGIES)}")

    source = str(raw.get("source") or "stdout")
    if source not in _SOURCES:
        raise AdapterError(f"adapter 'source' must be one of {', '.join(_SOURCES)}")

    mapping = raw.get("map")
    if mapping is not None and (
        not isinstance(mapping, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items())
    ):
        raise AdapterError("adapter 'map' must be an object of string to string")

    if strategy == "json":
        return _json_adapter(raw, name, source, mapping)
    return _regex_adapter(raw, name, source, mapping)


def _json_adapter(
    raw: dict[str, Any], name: str, source: str, mapping: dict[str, str] | None
) -> Adapter:
    pointer = str(raw.get("pointer") or "")
    if not pointer.startswith("/"):
        raise AdapterError(
            "a json adapter needs a 'pointer' like '/findings/-/rule_id', where '-' "
            "means every element of the array at that step"
        )
    steps = tuple(pointer.split("/")[1:])
    if "-" not in steps:
        raise AdapterError(
            "a json adapter's 'pointer' must contain a '-' step naming the array of "
            "findings; without one it can only ever read a single identifier"
        )
    if steps[-1] == "-":
        raise AdapterError("a json adapter's 'pointer' must end at the identifier, not at '-'")
    return Adapter(name=name, strategy="json", source=source, pointer=steps, mapping=mapping)


def _regex_adapter(
    raw: dict[str, Any], name: str, source: str, mapping: dict[str, str] | None
) -> Adapter:
    pattern = _compile(raw.get("pattern"), "pattern")
    if pattern is None:
        raise AdapterError("a regex adapter needs a 'pattern' matching one rule identifier")
    if pattern.groups != 1:
        raise AdapterError(
            "a regex adapter's 'pattern' needs exactly one capture group, holding the "
            f"identifier; this one has {pattern.groups}"
        )
    clean = _compile(raw.get("no_findings_pattern"), "no_findings_pattern")
    if clean is None:
        raise AdapterError(
            "a regex adapter needs a 'no_findings_pattern' matching what the tool prints "
            "when it reports nothing. Without it, output this adapter cannot read is "
            "indistinguishable from a validator that found no rule, and the harness would "
            "report agreement over a run it never understood"
        )
    return Adapter(
        name=name,
        strategy="regex",
        source=source,
        pattern=pattern,
        no_findings_pattern=clean,
        mapping=mapping,
    )


def _compile(value: object, field: str) -> re.Pattern[str] | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdapterError(f"adapter '{field}' must be a string")
    try:
        return re.compile(value)
    except re.error as exc:
        raise AdapterError(f"adapter '{field}' is not a valid regular expression: {exc}") from exc


def read_identifiers(adapter: Adapter, stdout: str, stderr: str) -> tuple[list[str] | None, str]:
    """Rule identifiers from one run, or ``(None, reason)`` if unreadable."""

    text = adapter.stream(stdout, stderr)
    if adapter.strategy == "json":
        found, reason = _read_json(adapter, text)
    else:
        found, reason = _read_regex(adapter, text)
    if found is None:
        return None, reason
    mapping = adapter.mapping or {}
    return [mapping.get(identifier, identifier) for identifier in found], ""


def _read_json(adapter: Adapter, text: str) -> tuple[list[str] | None, str]:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"the {adapter.source} of this run is not JSON: {exc}"
    return _walk(document, adapter.pointer, "/".join(("", *adapter.pointer)))


def _walk(node: Any, steps: tuple[str, ...], pointer: str) -> tuple[list[str] | None, str]:
    """Resolve the pointer, distinguishing 'no such path' from 'an empty array'."""

    if not steps:
        if isinstance(node, str):
            return [node], ""
        return None, f"{pointer} does not name a string in this output"
    head, rest = steps[0], steps[1:]
    if head == "-":
        if not isinstance(node, list):
            return None, f"{pointer} expects an array where the output has {type(node).__name__}"
        collected: list[str] = []
        for element in node:
            values, reason = _walk(element, rest, pointer)
            if values is None:
                return None, reason
            collected.extend(values)
        # An array that is present and empty is a read, not a failure to read:
        # the validator ran and named no rule. This return is the difference
        # between this harness and one that cannot tell those apart.
        return collected, ""
    if not isinstance(node, dict) or head not in node:
        return None, f"{pointer} names nothing in this output (no {head!r})"
    return _walk(node[head], rest, pointer)


def _read_regex(adapter: Adapter, text: str) -> tuple[list[str] | None, str]:
    pattern, clean = adapter.pattern, adapter.no_findings_pattern
    if pattern is None or clean is None:
        # `load_adapter` refuses a regex adapter missing either, so this is a
        # hand-built Adapter. Report it rather than reading half an adapter.
        return None, "this regex adapter has no pattern or no no_findings_pattern"
    matches = pattern.findall(text)
    if matches:
        return [str(match) for match in matches], ""
    if clean.search(text) is not None:
        return [], ""
    return None, (
        "no identifier matched and the adapter's no_findings_pattern did not match either, "
        "so this output was not understood rather than found clean"
    )


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


def load_corpus(path: Path, extract_to: Path) -> Corpus:
    """Open a corpus zip or directory and read its committed expectations."""

    if path.is_dir():
        root, label, digest, kind = path, path.name, _tree_digest(path), "sha256-tree"
    elif zipfile.is_zipfile(path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with zipfile.ZipFile(path) as archive:
            archive.extractall(extract_to)  # noqa: S202 - corpus is the user's own artifact
        root, label, kind = extract_to, path.name, "sha256-archive"
    else:
        raise CorpusError(f"{path} is neither a directory nor a zip archive")

    expectations_path = root / _EXPECTATIONS_NAME
    if not expectations_path.is_file():
        raise CorpusError(f"{path} has no {_EXPECTATIONS_NAME}, so there is nothing to compare to")
    try:
        raw = json.loads(expectations_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusError(f"{_EXPECTATIONS_NAME} in {path} could not be read: {exc}") from exc
    if not isinstance(raw, dict) or not raw:
        raise CorpusError(f"{_EXPECTATIONS_NAME} in {path} names no fixtures")

    expectations: dict[str, tuple[str, ...]] = {}
    for fixture, rules in sorted(raw.items()):
        if not isinstance(fixture, str) or not isinstance(rules, list):
            raise CorpusError(f"{_EXPECTATIONS_NAME} entry {fixture!r} is not a list of rule ids")
        expectations[fixture] = tuple(sorted(str(rule) for rule in rules))

    missing = [name for name in expectations if not (root / name).is_dir()]
    if missing:
        raise CorpusError(
            f"{_EXPECTATIONS_NAME} names {len(missing)} fixture(s) the corpus does not "
            f"contain: {', '.join(sorted(missing)[:5])}"
        )
    return Corpus(
        root=root, label=label, digest=digest, digest_kind=kind, expectations=expectations
    )


def _tree_digest(root: Path) -> str:
    """A digest over the fixture bytes, for a corpus that is a directory.

    Named ``sha256-tree`` in the report so it is never mistaken for the digest
    of a published archive: the two are computed over different things and
    would not match for the same fixtures.
    """

    accumulator = hashlib.sha256()
    for file in sorted(p for p in root.rglob("*") if p.is_file()):
        accumulator.update(file.relative_to(root).as_posix().encode("utf-8"))
        accumulator.update(b"\0")
        accumulator.update(hashlib.sha256(file.read_bytes()).digest())
    return accumulator.hexdigest()


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def build_argv(command: str, fixture_path: Path) -> list[str]:
    """Split the template, then substitute, so a path with a space stays one word."""

    if PATH_PLACEHOLDER not in command:
        raise ValueError(
            f"the command template must contain {PATH_PLACEHOLDER} once, or every fixture "
            "would run the same command and the harness would report one measurement as many"
        )
    # No emptiness check below: the placeholder is itself a word, so a template
    # that contains it always splits to at least one token. A guard here would
    # be a branch nothing can reach, which reads as a defence and is not one.
    tokens = shlex.split(command)
    return [token.replace(PATH_PLACEHOLDER, str(fixture_path)) for token in tokens]


def run_conformance(
    command: str,
    adapter: Adapter,
    corpus: Corpus,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ConformanceReport:
    """Run ``command`` over every fixture and compare what it reports."""

    results: list[FixtureResult] = []
    for fixture, expected in corpus.expectations.items():
        results.append(
            _run_fixture(command, adapter, corpus.root / fixture, fixture, expected, timeout)
        )
    return ConformanceReport(
        adapter=adapter.name,
        command=command,
        corpus_label=corpus.label,
        corpus_digest=corpus.digest,
        corpus_digest_kind=corpus.digest_kind,
        harness_version=__version__,
        timeout_seconds=timeout,
        results=tuple(results),
    )


def _run_fixture(
    command: str,
    adapter: Adapter,
    fixture_path: Path,
    fixture: str,
    expected: tuple[str, ...],
    timeout: float,
) -> FixtureResult:
    argv = build_argv(command, fixture_path)
    try:
        completed = subprocess.run(  # noqa: S603 - argv from shlex, no shell, user's own command
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        # Only this fixture. A command that hangs on one input has said nothing
        # about the others, and stopping the run would turn one hang into a
        # report about a corpus that was never executed.
        return _unmeasured(
            fixture, expected, TIMED_OUT, f"the command did not finish within {timeout:g}s", None
        )
    except OSError as exc:
        return _unmeasured(fixture, expected, UNREADABLE, f"the command could not run: {exc}", None)

    reported, reason = read_identifiers(adapter, completed.stdout, completed.stderr)
    if reported is None:
        return _unmeasured(fixture, expected, UNREADABLE, reason, completed.returncode)

    seen = tuple(sorted(set(reported)))
    extra = tuple(sorted(set(seen) - set(expected)))
    missing = tuple(sorted(set(expected) - set(seen)))
    return FixtureResult(
        fixture=fixture,
        outcome=AGREES if not extra and not missing else DISAGREES,
        expected=expected,
        reported=seen,
        extra=extra,
        missing=missing,
        reason="",
        exit_code=completed.returncode,
    )


def _unmeasured(
    fixture: str, expected: tuple[str, ...], outcome: str, reason: str, exit_code: int | None
) -> FixtureResult:
    return FixtureResult(
        fixture=fixture,
        outcome=outcome,
        expected=expected,
        reported=(),
        extra=(),
        missing=(),
        reason=reason,
        exit_code=exit_code,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def conformance_to_dict(report: ConformanceReport) -> dict[str, Any]:
    return {
        "harness": "tods-validate conformance",
        "harnessVersion": report.harness_version,
        "adapter": report.adapter,
        "command": report.command,
        "corpus": {
            "label": report.corpus_label,
            "digest": report.corpus_digest,
            "digestKind": report.corpus_digest_kind,
        },
        "timeoutSeconds": report.timeout_seconds,
        "summary": {
            "fixtures": len(report.results),
            "compared": report.compared,
            **{outcome: report.count(outcome) for outcome in OUTCOMES},
        },
        "results": [
            {
                "fixture": result.fixture,
                "outcome": result.outcome,
                "expected": list(result.expected),
                "reported": list(result.reported),
                "extra": list(result.extra),
                "missing": list(result.missing),
                "reason": result.reason,
                "exitCode": result.exit_code,
            }
            for result in report.results
        ],
    }


def _headline(report: ConformanceReport) -> str:
    """Both numbers, always: compared out of found, then the breakdown.

    ``42 agree`` on its own cannot be told from ``42 agree, 1 never ran``, and
    the second is the one a reader has to act on.
    """

    return (
        f"{report.compared} of {len(report.results)} fixtures compared "
        f"({report.count(AGREES)} agree, {report.count(DISAGREES)} disagree, "
        f"{report.count(UNREADABLE)} unreadable, {report.count(TIMED_OUT)} timed out)"
    )


def render_conformance_text(report: ConformanceReport) -> str:
    lines = [
        f"Conformance comparison: {report.adapter}",
        f"  command: {report.command}",
        f"  corpus:  {report.corpus_label} ({report.corpus_digest_kind}:{report.corpus_digest})",
        f"  harness: tods-validate {report.harness_version}",
        "",
        _headline(report),
    ]
    for result in report.results:
        if result.outcome == AGREES:
            continue
        lines.append("")
        lines.append(f"{result.fixture}: {result.outcome.replace('_', ' ')}")
        if result.reason:
            lines.append(f"  {result.reason}")
        if result.extra:
            lines.append(f"  reported and not expected: {', '.join(result.extra)}")
        if result.missing:
            lines.append(f"  expected and not reported: {', '.join(result.missing)}")
    if report.compared == len(report.results) and report.count(DISAGREES) == 0:
        lines.append("")
        lines.append("Every fixture agreed.")
    return "\n".join(lines)


def render_conformance_markdown(report: ConformanceReport) -> str:
    lines = [
        "# Conformance comparison",
        "",
        f"- Adapter: `{report.adapter}`",
        f"- Command: `{report.command}`",
        f"- Corpus: `{report.corpus_label}` (`{report.corpus_digest_kind}:{report.corpus_digest}`)",
        f"- Harness: tods-validate {report.harness_version}",
        "",
        _headline(report),
        "",
        "| Fixture | Outcome | Reported, not expected | Expected, not reported | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in report.results:
        lines.append(
            f"| `{result.fixture}` | {result.outcome.replace('_', ' ')} "
            f"| {', '.join(f'`{r}`' for r in result.extra) or '—'} "
            f"| {', '.join(f'`{r}`' for r in result.missing) or '—'} "
            f"| {result.reason or '—'} |"
        )
    lines.append("")
    lines.append(
        "Rule identifiers and severities are tods-validate's, not the TODS "
        "specification's. A disagreement is a question about one implementation or "
        "about the spec text; this table does not answer which."
    )
    return "\n".join(lines)
