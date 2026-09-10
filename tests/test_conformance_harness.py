"""The conformance harness, and the one way it must not be wrong.

`conformance run` executes another validator over the corpus and compares what
it reports with `expectations.json`. The defect it exists to avoid is an
adapter that read nothing being reported as a validator that found nothing:
both produce the empty rule set, and for the `valid` fixture -- whose
expectation *is* the empty set -- the second reading would print `agrees` over
a run that measured nothing.

So the tests below pin both directions of every state. A harness that reports
`unreadable` for everything satisfies the fail-closed half on its own and is
useless, and a harness that reports `agrees` for everything satisfies the
agreement half and is worse than useless.

The fake validators are shell-free scripts run through `sys.executable`, so
nothing here needs a second tool installed. Three tests drive the real
tods-validate CLI over real fixtures, because the JSON pointer in the shipped
adapter example is a claim about this project's own report format and a fake
validator cannot check it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tods_validate.conformance import (
    AGREES,
    DISAGREES,
    TIMED_OUT,
    UNREADABLE,
    AdapterError,
    CorpusError,
    build_argv,
    conformance_to_dict,
    load_adapter,
    load_corpus,
    read_identifiers,
    render_conformance_markdown,
    render_conformance_text,
    run_conformance,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Two invalid fixtures and the valid feed. The valid one is not optional
# scenery: it is the only fixture whose expected rule set is empty, which is
# the case an unreadable adapter can impersonate.
_REAL_FIXTURES = ("invalid/TODS-E103", "invalid/TODS-E307")

_ADAPTER_EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "conformance-adapters"

# The adapter the documentation ships, read from the file rather than retyped.
# A second copy here would let the example rot while these tests stayed green,
# which is the failure this whole module is about one level up.
_JSON_ADAPTER = json.loads((_ADAPTER_EXAMPLES / "tods-validate.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Building a corpus and a validator to point at it
# ---------------------------------------------------------------------------


def _corpus_dir(tmp_path: Path, expectations: dict[str, list[str]]) -> Path:
    """A minimal corpus: one directory per fixture plus the oracle."""

    root = tmp_path / "corpus"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    for fixture in expectations:
        directory = root / fixture
        directory.mkdir(parents=True)
        (directory / "run_events.txt").write_text("run_id\nR1\n", encoding="utf-8")
    (root / "expectations.json").write_text(json.dumps(expectations), encoding="utf-8")
    return root


def _fake_validator(tmp_path: Path, body: str) -> Path:
    """A validator whose whole behaviour is a Python expression over its argv."""

    script = tmp_path / "fake_validator.py"
    script.write_text(
        "import json, sys, time\n"
        "path = sys.argv[1]\n"
        "name = path.rstrip('/').rsplit('/', 1)[-1]\n" + body,
        encoding="utf-8",
    )
    return script


def _adapter(tmp_path: Path, **overrides: object) -> Path:
    description = {**_JSON_ADAPTER, **overrides}
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps(description), encoding="utf-8")
    return path


def _report_ids(rule_ids: dict[str, list[str]]) -> str:
    """A fake validator body printing this project's own report shape."""

    return (
        f"ids = {rule_ids!r}.get(name, [])\n"
        "print(json.dumps({'findings': [{'rule_id': i} for i in ids]}))\n"
    )


def _run(
    tmp_path: Path,
    expectations: dict[str, list[str]],
    body: str,
    *,
    adapter: Path | None = None,
    timeout: float = 30.0,
) -> object:
    root = _corpus_dir(tmp_path, expectations)
    script = _fake_validator(tmp_path, body)
    corpus = load_corpus(root, tmp_path / "extract")
    description = load_adapter((adapter or _adapter(tmp_path)).read_text(encoding="utf-8"))
    command = f"{sys.executable} {script} {{path}}"
    return run_conformance(command, description, corpus, timeout=timeout)


def _outcomes(report: object) -> dict[str, str]:
    return {result.fixture: result.outcome for result in report.results}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# The fail-closed property, in both directions
# ---------------------------------------------------------------------------


def test_a_validator_that_reproduces_the_oracle_agrees_on_every_fixture(
    tmp_path: Path,
) -> None:
    """The positive control. Without it, every refusal below is satisfied by
    a harness that refuses the world."""

    expectations = {"invalid/A": ["TODS-E103"], "invalid/B": ["TODS-E307"], "valid": []}
    report = _run(tmp_path, expectations, _report_ids({"A": ["TODS-E103"], "B": ["TODS-E307"]}))
    assert _outcomes(report) == dict.fromkeys(expectations, AGREES)
    assert report.compared == 3  # type: ignore[attr-defined]
    assert report.unmeasured == 0  # type: ignore[attr-defined]


def test_an_adapter_that_reads_nothing_reports_unreadable_and_never_agreement(
    tmp_path: Path,
) -> None:
    """The whole reason this harness needs an adapter format at all.

    The validator here is correct — it reproduces the oracle exactly. Only the
    adapter is pointed at a key that does not exist. Every fixture must come
    back unreadable, `valid` included: its expected rule set is empty, so an
    adapter that returned "no identifiers" would agree with it by accident and
    the report would show one green row earned by a failure to read.
    """

    expectations = {"invalid/A": ["TODS-E103"], "valid": []}
    report = _run(
        tmp_path,
        expectations,
        _report_ids({"A": ["TODS-E103"]}),
        adapter=_adapter(tmp_path, pointer="/violations/-/code"),
    )
    assert _outcomes(report) == dict.fromkeys(expectations, UNREADABLE)
    assert report.compared == 0  # type: ignore[attr-defined]
    assert all("names nothing in this output" in r.reason for r in report.results)  # type: ignore[attr-defined]


def test_an_empty_findings_array_is_a_reading_and_not_a_failure_to_read(
    tmp_path: Path,
) -> None:
    """The other side of the same coin, and the reason the pointer walks.

    `{"findings": []}` is a validator saying it found nothing. The array is
    present, so the pointer resolved; the harness must call that a comparison
    and agree with the valid fixture. A pointer resolver that returned "no
    values" for both this and a missing key could not tell them apart.
    """

    report = _run(tmp_path, {"valid": []}, "print(json.dumps({'findings': []}))\n")
    assert _outcomes(report) == {"valid": AGREES}


def test_output_that_is_not_json_is_unreadable_rather_than_clean(tmp_path: Path) -> None:
    report = _run(tmp_path, {"valid": []}, "print('validation complete')\n")
    assert _outcomes(report) == {"valid": UNREADABLE}
    assert "is not JSON" in report.results[0].reason  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Disagreement, which is the signal the corpus exists to give
# ---------------------------------------------------------------------------


def test_an_extra_and_a_missing_rule_are_reported_separately(tmp_path: Path) -> None:
    expectations = {"invalid/A": ["TODS-E103"], "invalid/B": ["TODS-E307"]}
    report = _run(
        tmp_path,
        expectations,
        _report_ids({"A": ["TODS-E103", "TODS-W302"], "B": []}),
    )
    by_fixture = {result.fixture: result for result in report.results}  # type: ignore[attr-defined]
    assert by_fixture["invalid/A"].outcome == DISAGREES
    assert by_fixture["invalid/A"].extra == ("TODS-W302",)
    assert by_fixture["invalid/A"].missing == ()
    assert by_fixture["invalid/B"].outcome == DISAGREES
    assert by_fixture["invalid/B"].extra == ()
    assert by_fixture["invalid/B"].missing == ("TODS-E307",)


def test_a_repeated_identifier_is_one_disagreement_not_several(tmp_path: Path) -> None:
    """Rule sets, not finding counts: the oracle records which rules fire."""

    report = _run(
        tmp_path,
        {"invalid/A": ["TODS-E103"]},
        _report_ids({"A": ["TODS-E103", "TODS-E103", "TODS-E103"]}),
    )
    assert _outcomes(report) == {"invalid/A": AGREES}
    assert report.results[0].reported == ("TODS-E103",)  # type: ignore[attr-defined]


def test_an_identifier_map_translates_before_the_comparison(tmp_path: Path) -> None:
    report = _run(
        tmp_path,
        {"invalid/A": ["TODS-E103"]},
        _report_ids({"A": ["THEIRS-1"]}),
        adapter=_adapter(tmp_path, map={"THEIRS-1": "TODS-E103"}),
    )
    assert _outcomes(report) == {"invalid/A": AGREES}


# ---------------------------------------------------------------------------
# A command that will not finish, or will not run
# ---------------------------------------------------------------------------


def test_a_hanging_command_times_out_for_that_fixture_only(tmp_path: Path) -> None:
    """One hang is one unmeasured fixture, not an abandoned corpus."""

    expectations = {"invalid/A": ["TODS-E103"], "invalid/HANG": ["TODS-E307"]}
    body = "if name == 'HANG':\n    time.sleep(30)\n" + _report_ids({"A": ["TODS-E103"]})
    report = _run(tmp_path, expectations, body, timeout=2.0)
    assert _outcomes(report) == {"invalid/A": AGREES, "invalid/HANG": TIMED_OUT}
    assert report.compared == 1  # type: ignore[attr-defined]
    assert report.unmeasured == 1  # type: ignore[attr-defined]
    assert "did not finish within 2s" in _by(report, "invalid/HANG").reason


def test_a_command_that_cannot_be_executed_is_unreadable_not_a_crash(tmp_path: Path) -> None:
    root = _corpus_dir(tmp_path, {"valid": []})
    corpus = load_corpus(root, tmp_path / "extract")
    adapter = load_adapter(json.dumps(_JSON_ADAPTER))
    report = run_conformance(f"{tmp_path / 'no-such-binary'} {{path}}", adapter, corpus)
    assert _outcomes(report) == {"valid": UNREADABLE}
    assert "could not run" in report.results[0].reason


def _by(report: object, fixture: str):  # type: ignore[no-untyped-def]
    return next(r for r in report.results if r.fixture == fixture)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# The adapter format refuses what it cannot read safely
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        pytest.param("not json at all", "not valid JSON", id="not-json"),
        pytest.param("[]", "must be a JSON object", id="not-an-object"),
        pytest.param('{"strategy": "json", "pointer": "/a/-/b"}', "needs a 'name'", id="no-name"),
        pytest.param('{"name": "x", "strategy": "xml"}', "'strategy' must be", id="bad-strategy"),
        pytest.param(
            '{"name": "x", "strategy": "json", "pointer": "/a/-/b", "source": "syslog"}',
            "'source' must be",
            id="bad-source",
        ),
        pytest.param(
            '{"name": "x", "strategy": "json", "pointer": "findings"}',
            "needs a 'pointer'",
            id="pointer-not-rooted",
        ),
        pytest.param(
            '{"name": "x", "strategy": "json", "pointer": "/findings/rule_id"}',
            "must contain a '-' step",
            id="pointer-reads-one-value",
        ),
        pytest.param(
            '{"name": "x", "strategy": "json", "pointer": "/findings/-"}',
            "must end at the identifier",
            id="pointer-ends-at-the-array",
        ),
        pytest.param(
            '{"name": "x", "strategy": "regex", "pattern": "TODS-[EWI][0-9]{3}",'
            ' "no_findings_pattern": "clean"}',
            "exactly one capture group",
            id="regex-without-a-group",
        ),
        pytest.param(
            '{"name": "x", "strategy": "regex", "pattern": "(TODS-[EWI][0-9]{3})"}',
            "needs a 'no_findings_pattern'",
            id="regex-without-a-clean-pattern",
        ),
        pytest.param(
            '{"name": "x", "strategy": "regex", "no_findings_pattern": "clean"}',
            "needs a 'pattern'",
            id="regex-without-an-identifier-pattern",
        ),
        pytest.param(
            '{"name": "x", "strategy": "regex", "pattern": 7, "no_findings_pattern": "clean"}',
            "'pattern' must be a string",
            id="pattern-is-not-a-string",
        ),
        pytest.param(
            '{"name": "x", "strategy": "regex", "pattern": "([unclosed",'
            ' "no_findings_pattern": "clean"}',
            "not a valid regular expression",
            id="regex-that-does-not-compile",
        ),
        pytest.param(
            '{"name": "x", "strategy": "json", "pointer": "/a/-/b", "map": {"a": 1}}',
            "'map' must be an object of string to string",
            id="map-is-not-strings",
        ),
    ],
)
def test_an_adapter_it_could_misread_with_is_refused(description: str, expected: str) -> None:
    with pytest.raises(AdapterError, match=expected):
        load_adapter(description)


def test_a_regex_adapter_needs_the_clean_pattern_to_call_an_output_clean(
    tmp_path: Path,
) -> None:
    """Why `no_findings_pattern` is required rather than optional.

    Both runs below produce no identifier match. The first prints the sentence
    the tool prints when it is happy, so it is a reading of zero rules; the
    second prints a stack trace, and no expression in the adapter understood
    it. Without the second pattern those two are the same observation.
    """

    regex = {
        "name": "regex",
        "strategy": "regex",
        "pattern": "(TODS-[EWI][0-9]{3})",
        "no_findings_pattern": "^feed is valid$",
        "source": "stdout",
    }
    path = tmp_path / "regex-adapter.json"
    path.write_text(json.dumps(regex), encoding="utf-8")

    clean = _run(tmp_path, {"valid": []}, "print('feed is valid')\n", adapter=path)
    assert _outcomes(clean) == {"valid": AGREES}

    broken = _run(
        tmp_path,
        {"valid": []},
        "sys.stdout.write('Traceback (most recent call last)\\n')\n",
        adapter=path,
    )
    assert _outcomes(broken) == {"valid": UNREADABLE}
    assert "no_findings_pattern did not match" in broken.results[0].reason  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# The corpus, and the command template
# ---------------------------------------------------------------------------


def test_a_corpus_without_expectations_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    (root / "valid").mkdir(parents=True)
    with pytest.raises(CorpusError, match="nothing to compare to"):
        load_corpus(root, tmp_path / "extract")


def test_expectations_naming_a_fixture_the_corpus_lacks_is_refused(tmp_path: Path) -> None:
    """Otherwise a corpus missing half its fixtures reports them as agreeing."""

    root = _corpus_dir(tmp_path, {"invalid/A": ["TODS-E103"]})
    (root / "expectations.json").write_text(
        json.dumps({"invalid/A": ["TODS-E103"], "invalid/GONE": ["TODS-E307"]}), encoding="utf-8"
    )
    with pytest.raises(CorpusError, match="invalid/GONE"):
        load_corpus(root, tmp_path / "extract")


def test_a_command_template_that_never_names_the_fixture_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"must contain \{path\} once"):
        build_argv("validator --json", tmp_path / "fixture")


def test_the_template_is_split_before_the_path_is_substituted(tmp_path: Path) -> None:
    """A fixture directory with a space in it stays one argument."""

    spaced = tmp_path / "a corpus" / "invalid" / "A"
    argv = build_argv("validator --json {path}", spaced)
    assert argv == ["validator", "--json", str(spaced)]


def test_the_report_names_the_corpus_it_ran_against(tmp_path: Path) -> None:
    """A comparison is about a specific set of fixtures, and says which."""

    root = _corpus_dir(tmp_path, {"valid": []})
    first = load_corpus(root, tmp_path / "extract-1")
    (root / "valid" / "run_events.txt").write_text("run_id\nR2\n", encoding="utf-8")
    second = load_corpus(root, tmp_path / "extract-2")

    assert first.digest_kind == "sha256-tree"
    assert len(first.digest) == 64
    assert first.digest != second.digest, "a changed fixture must change the digest"

    adapter = load_adapter(json.dumps(_JSON_ADAPTER))
    script = _fake_validator(tmp_path, "print(json.dumps({'findings': []}))\n")
    report = run_conformance(f"{sys.executable} {script} {{path}}", adapter, second)
    for rendered in (render_conformance_text(report), render_conformance_markdown(report)):
        assert second.digest in rendered
        assert "sha256-tree" in rendered
    assert conformance_to_dict(report)["corpus"]["digest"] == second.digest


def test_a_zip_corpus_is_read_and_digested_as_an_archive(tmp_path: Path) -> None:
    """The published corpus is a zip, and its digest is of the published bytes."""

    import zipfile

    root = _corpus_dir(tmp_path, {"valid": []})
    archive = tmp_path / "corpus.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for file in sorted(p for p in root.rglob("*") if p.is_file()):
            zf.write(file, file.relative_to(root).as_posix())

    corpus = load_corpus(archive, tmp_path / "extract")
    assert corpus.digest_kind == "sha256-archive"
    assert corpus.expectations == {"valid": ()}
    assert (corpus.root / "valid" / "run_events.txt").is_file()


# ---------------------------------------------------------------------------
# The summary line, which is the part a reader quotes
# ---------------------------------------------------------------------------


def test_the_summary_states_how_many_fixtures_were_compared_not_only_how_many_agreed(
    tmp_path: Path,
) -> None:
    """`2 agree` cannot be told from `2 agree, 1 never ran`, and only one of
    those is a corpus that was passed."""

    expectations = {"invalid/A": ["TODS-E103"], "invalid/HANG": ["TODS-E307"], "valid": []}
    body = "if name == 'HANG':\n    time.sleep(30)\n" + _report_ids({"A": ["TODS-E103"]})
    report = _run(tmp_path, expectations, body, timeout=2.0)

    text = render_conformance_text(report)
    assert "2 of 3 fixtures compared" in text
    assert "1 timed out" in text
    assert "Every fixture agreed." not in text
    assert "2 of 3 fixtures compared" in render_conformance_markdown(report)

    summary = conformance_to_dict(report)["summary"]
    assert summary == {
        "fixtures": 3,
        "compared": 2,
        AGREES: 2,
        DISAGREES: 0,
        UNREADABLE: 0,
        TIMED_OUT: 1,
    }


# ---------------------------------------------------------------------------
# Against the real validator, because the shipped pointer is a claim about
# this project's own report format.
# ---------------------------------------------------------------------------


def _real_corpus(tmp_path: Path) -> Path:
    """Real fixtures, laid out the way the published archive lays them out."""

    oracle = json.loads((_FIXTURES / "expectations.json").read_text(encoding="utf-8"))
    root = tmp_path / "real-corpus"
    root.mkdir()
    expectations = {}
    for fixture in _REAL_FIXTURES:
        shutil.copytree(_FIXTURES / fixture, root / fixture)
        expectations[fixture] = oracle[fixture]
    (root / "valid").mkdir()
    for sub in ("tods", "gtfs"):
        for file in sorted((_FIXTURES / "valid" / sub).iterdir()):
            if file.is_file():
                shutil.copy(file, root / "valid" / file.name)
    expectations["valid"] = oracle["valid"]
    (root / "expectations.json").write_text(json.dumps(expectations), encoding="utf-8")
    return root


_REAL_COMMAND = (
    f"{sys.executable} -m tods_validate.cli validate {{path}} --format json "
    "--enable coverage --enable advisory --enable experimental --enable feasibility"
)


def test_the_shipped_adapter_reads_this_validator_and_agrees_with_the_oracle(
    tmp_path: Path,
) -> None:
    """tods-validate against its own corpus, through the documented adapter.

    Three fixtures rather than all forty-seven, because each is a subprocess
    and the suite is a merge gate; `docs/conformance.md` records the command
    for the whole corpus. The three include `valid`, which is the fixture the
    fail-closed rule is about.
    """

    corpus = load_corpus(_real_corpus(tmp_path), tmp_path / "extract")
    adapter = load_adapter(json.dumps(_JSON_ADAPTER))
    report = run_conformance(_REAL_COMMAND, adapter, corpus, timeout=120.0)

    assert _outcomes(report) == dict.fromkeys(corpus.expectations, AGREES), render_conformance_text(
        report
    )
    assert report.compared == 3


def test_a_wrong_expectation_makes_the_real_validator_disagree(tmp_path: Path) -> None:
    """The negative half of the test above.

    Without it, a harness that reported `agrees` unconditionally would pass —
    which is exactly the failure mode of a comparison tool.
    """

    root = _real_corpus(tmp_path)
    oracle = json.loads((root / "expectations.json").read_text(encoding="utf-8"))
    oracle["valid"] = ["TODS-E103"]
    (root / "expectations.json").write_text(json.dumps(oracle), encoding="utf-8")

    corpus = load_corpus(root, tmp_path / "extract")
    adapter = load_adapter(json.dumps(_JSON_ADAPTER))
    report = run_conformance(_REAL_COMMAND, adapter, corpus, timeout=120.0)

    assert _by(report, "valid").outcome == DISAGREES
    assert _by(report, "valid").missing == ("TODS-E103",)
    assert _by(report, "invalid/TODS-E103").outcome == AGREES


def test_the_cli_exits_two_when_a_fixture_could_not_be_compared(tmp_path: Path) -> None:
    """Three exit codes, not two: agreement, disagreement, and no comparison.

    Driven through the installed console entry point rather than the library,
    because the exit code is the whole interface for anyone scripting this.
    """

    root = _corpus_dir(tmp_path, {"valid": []})
    adapter = _adapter(tmp_path, pointer="/violations/-/code")
    script = _fake_validator(tmp_path, "print(json.dumps({'findings': []}))\n")
    completed = subprocess.run(  # noqa: S603 - fixed argv, resolved interpreter, no shell
        [
            sys.executable,
            "-m",
            "tods_validate.cli",
            "conformance",
            "run",
            "--command",
            f"{sys.executable} {script} {{path}}",
            "--corpus",
            str(root),
            "--adapter",
            str(adapter),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert "0 of 1 fixtures compared" in completed.stdout


def test_a_regex_adapter_reads_the_identifiers_it_matches(tmp_path: Path) -> None:
    """The regex strategy's accepting half, which its refusal test cannot show."""

    regex = {
        "name": "regex",
        "strategy": "regex",
        "pattern": "(TODS-[EWI][0-9]{3})",
        "no_findings_pattern": "^feed is valid$",
        "source": "stdout",
    }
    path = tmp_path / "regex-adapter.json"
    path.write_text(json.dumps(regex), encoding="utf-8")
    body = (
        "lines = {'A': 'error TODS-E103 at row 2\\nerror TODS-W302 at row 3'}\n"
        "print(lines.get(name, 'feed is valid'))\n"
    )
    report = _run(
        tmp_path,
        {"invalid/A": ["TODS-E103", "TODS-W302"], "valid": []},
        body,
        adapter=path,
    )
    assert _outcomes(report) == {"invalid/A": AGREES, "valid": AGREES}
    assert _by(report, "invalid/A").reported == ("TODS-E103", "TODS-W302")


def test_an_adapter_can_read_stderr_or_both_streams(tmp_path: Path) -> None:
    """A validator that writes its report to stderr is common enough to support."""

    body = (
        "sys.stderr.write(json.dumps({'findings': [{'rule_id': 'TODS-E103'}]}))\n"
        "print('progress noise')\n"
    )
    expectations = {"invalid/A": ["TODS-E103"]}
    on_stdout = _run(tmp_path, expectations, body)
    assert _outcomes(on_stdout) == {"invalid/A": UNREADABLE}

    on_stderr = _run(tmp_path, expectations, body, adapter=_adapter(tmp_path, source="stderr"))
    assert _outcomes(on_stderr) == {"invalid/A": AGREES}

    combined = _run(tmp_path, expectations, body, adapter=_adapter(tmp_path, source="combined"))
    assert _outcomes(combined) == {"invalid/A": UNREADABLE}, (
        "concatenating two streams is not JSON; 'combined' is for tools that write "
        "one document across both, not a way to search everywhere"
    )


def test_a_pointer_that_lands_on_the_wrong_shape_says_so(tmp_path: Path) -> None:
    not_an_array = _run(tmp_path, {"valid": []}, "print(json.dumps({'findings': 3}))\n")
    assert _outcomes(not_an_array) == {"valid": UNREADABLE}
    assert "expects an array" in not_an_array.results[0].reason  # type: ignore[attr-defined]

    not_a_string = _run(
        tmp_path, {"valid": []}, "print(json.dumps({'findings': [{'rule_id': 7}]}))\n"
    )
    assert _outcomes(not_a_string) == {"valid": UNREADABLE}
    assert "does not name a string" in not_a_string.results[0].reason  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        pytest.param("not json", "could not be read", id="unparseable"),
        pytest.param("{}", "names no fixtures", id="empty"),
        pytest.param('{"valid": "TODS-E103"}', "not a list of rule ids", id="not-a-list"),
    ],
)
def test_an_oracle_the_harness_cannot_read_is_refused(
    contents: str, expected: str, tmp_path: Path
) -> None:
    """A corpus whose oracle is unreadable compares nothing, so it must not run."""

    root = _corpus_dir(tmp_path, {"valid": []})
    (root / "expectations.json").write_text(contents, encoding="utf-8")
    with pytest.raises(CorpusError, match=expected):
        load_corpus(root, tmp_path / "extract")


def test_a_corpus_that_is_neither_a_directory_nor_an_archive_is_refused(tmp_path: Path) -> None:
    stray = tmp_path / "corpus.txt"
    stray.write_text("fixtures", encoding="utf-8")
    with pytest.raises(CorpusError, match="neither a directory nor a zip"):
        load_corpus(stray, tmp_path / "extract")


def test_the_text_report_names_both_sides_of_a_disagreement(tmp_path: Path) -> None:
    """A disagreement a reader cannot act on is a number, not a finding."""

    report = _run(
        tmp_path,
        {"invalid/A": ["TODS-E103"]},
        _report_ids({"A": ["TODS-W302"]}),
    )
    text = render_conformance_text(report)
    assert "invalid/A: disagrees" in text
    assert "reported and not expected: TODS-W302" in text
    assert "expected and not reported: TODS-E103" in text
    assert "Every fixture agreed." not in text

    markdown = render_conformance_markdown(report)
    assert "`TODS-W302`" in markdown
    assert "`TODS-E103`" in markdown


def test_a_hand_built_regex_adapter_missing_a_pattern_reads_nothing() -> None:
    """`load_adapter` refuses this shape, so only a caller building an Adapter
    directly can reach it. It reports unreadable rather than quietly treating
    half an adapter as a validator that found nothing."""

    from tods_validate.conformance import Adapter, read_identifiers

    half = Adapter(name="half", strategy="regex", source="stdout")
    found, reason = read_identifiers(half, "TODS-E103", "")
    assert found is None
    assert "no pattern or no no_findings_pattern" in reason


def test_every_shipped_example_adapter_loads() -> None:
    """The examples are documentation, and documentation that does not parse
    is worse than none: a reader copies it and gets an error about their own
    validator."""

    examples = sorted(_ADAPTER_EXAMPLES.glob("*.json"))
    assert len(examples) >= 2, "the adapter examples directory is empty or unreadable"
    for example in examples:
        adapter = load_adapter(example.read_text(encoding="utf-8"))
        assert adapter.name

    text_adapter = load_adapter(
        (_ADAPTER_EXAMPLES / "text-output.json").read_text(encoding="utf-8")
    )
    found, reason = read_identifiers(text_adapter, "error: TODS-E103 in run_events.txt", "")
    assert (found, reason) == (["TODS-E103"], "")
    assert read_identifiers(text_adapter, "no issues found", "") == ([], "")
    unreadable, why = read_identifiers(text_adapter, "Segmentation fault", "")
    assert unreadable is None
    assert "no_findings_pattern did not match" in why
