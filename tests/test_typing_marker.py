"""The published package must advertise its own type information (PEP 561).

`mypy --strict` runs over `src/` on every pull request, and the v1 contract
reserves semantic-versioning guarantees for the public Python exports. Neither
of those reaches anyone downstream without a `py.typed` marker in the
distribution: without it, type checkers treat an installed `tods_validate` as
untyped and refuse to look inside it, so a caller running mypy over their own
code gets `import-untyped` and no checking of this library's API at all.

Measured at v0.10.0, before the marker was added, on a five-line consumer that
imports `validate_feed`:

    error: Skipping analyzing "tods_validate": module is installed, but
    missing library stubs or py.typed marker  [import-untyped]

and with the marker in place, "Success: no issues found in 1 source file".
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MARKER = _ROOT / "src" / "tods_validate" / "py.typed"


def test_the_source_package_carries_a_py_typed_marker() -> None:
    assert _MARKER.is_file(), (
        "src/tods_validate/py.typed is missing. Without it every downstream "
        "type checker treats this package as untyped, whatever mypy --strict "
        "says about it here."
    )


def test_the_marker_is_where_an_installed_consumer_looks_for_it() -> None:
    """The marker has to sit next to the installed package, not only in the repo.

    `find_spec` resolves the same way an importing consumer does, so this
    passes for an editable install and for a wheel install and fails if the
    file stops being packaged.
    """
    spec = importlib.util.find_spec("tods_validate")
    assert spec is not None
    assert spec.origin is not None
    installed = Path(spec.origin).parent
    assert (installed / "py.typed").is_file(), (
        f"tods_validate is installed at {installed} with no py.typed beside it; "
        "the marker exists in the repository but is not being packaged"
    )


def test_a_consumer_can_type_check_against_this_package(tmp_path: Path) -> None:
    """The property, rather than a restatement of the file's existence.

    Run from `tmp_path` so mypy does not pick up this repository's own
    configuration (`files = ["src"]`) and check `src/` instead of the consumer.
    """
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        textwrap.dedent(
            """\
            from pathlib import Path

            from tods_validate import validate_feed

            report = validate_feed(Path("feed"))
            print(report)
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "consumer.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "import-untyped" not in result.stdout, (
        "a consumer type-checking against tods_validate is told the package is "
        f"untyped:\n{result.stdout}"
    )
    assert result.returncode == 0, (
        f"mypy --strict failed on a minimal consumer:\n{result.stdout}\n{result.stderr}"
    )
