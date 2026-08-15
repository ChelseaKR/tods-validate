"""The browser playground stays wired to the public API it calls.

The playground runs hardcoded Python in Pyodide, so the only thing that can
silently break it from this side is renaming the API it imports. These guards
fail loudly if that happens. (The page itself needs a browser to test end to
end; see web/README.md.)
"""

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_HTML = _ROOT / "web" / "index.html"
_PYPROJECT = _ROOT / "pyproject.toml"


def _pinned_version() -> str:
    match = re.search(r'const TODS_VALIDATE_VERSION = "([^"]+)";', _HTML.read_text())
    assert match is not None, "the playground must pin the wheel version it installs"
    return match.group(1)


def test_playground_installs_this_projects_version() -> None:
    # The page micropip-installs `tods-validate==<this>` from PyPI, so a pin left
    # behind at the previous release means the "try it without installing
    # anything" path validates with the previous release's rule set while the
    # rule pages served from the same site describe the current one.
    project = tomllib.loads(_PYPROJECT.read_text())["project"]["version"]
    assert _pinned_version() == project


def test_playground_keeps_the_parameter_the_accessibility_gate_targets() -> None:
    # scripts/run-a11y.sh audits index.html?a11y-static=1. If that branch is
    # renamed or dropped, the gate would still pass -- against a page that never
    # rendered the state it was meant to audit.
    assert "a11y-static" in _HTML.read_text()


def test_playground_references_the_public_api() -> None:
    html = _HTML.read_text()
    assert "from tods_validate.api import validate_feed" in html
    assert "from tods_validate.report import render_html" in html
    assert "micropip.install" in html  # installs the published wheel in-browser


def test_playground_version_target_exists_before_initialization() -> None:
    html = _HTML.read_text()
    target = 'id="footer-version"'
    assignment = "footerVersion.textContent ="
    assert target in html
    assert html.index(target) < html.index(assignment)


def test_playground_api_symbols_exist() -> None:
    from tods_validate.api import validate_feed
    from tods_validate.report import render_html

    # The playground calls these exact signatures.
    assert callable(validate_feed)
    assert callable(render_html)
