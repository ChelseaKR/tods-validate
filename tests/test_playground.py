"""The browser playground stays wired to the public API it calls.

The playground runs hardcoded Python in Pyodide, so the only thing that can
silently break it from this side is renaming the API it imports. These guards
fail loudly if that happens. (The page itself needs a browser to test end to
end; see web/README.md.)
"""

import importlib.util
import re
import sys
import tomllib
from datetime import date
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parent.parent
_HTML = _ROOT / "web" / "index.html"
_PYPROJECT = _ROOT / "pyproject.toml"
_WAIVERS = _ROOT / "waivers.yml"

_WAIVER_REQUIRED_FIELDS = (
    "id",
    "control",
    "repo",
    "kind",
    "reason",
    "owner",
    "granted",
    "expires",
    "check",
    "pinned_version",
    "project_version",
)


def _pinned_version() -> str:
    match = re.search(r'const TODS_VALIDATE_VERSION = "([^"]+)";', _HTML.read_text())
    assert match is not None, "the playground must pin the wheel version it installs"
    return match.group(1)


def _waiver_parser() -> ModuleType:
    # Reuse the generic waiver-registry reader scripts/check_npm_audit.py already
    # has (waivers.yml's shape, dated/owned/expiring, is a portfolio-wide
    # convention, not an npm-specific one -- only the `kind`-filtering downstream
    # of parse_waivers is npm-audit-specific). Loaded by path the same way
    # tests/test_npm_audit_gate.py does, since scripts/ is not an importable package.
    spec = importlib.util.spec_from_file_location(
        "check_npm_audit", _ROOT / "scripts" / "check_npm_audit.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _playground_version_pin_waiver() -> tuple[dict[str, str] | None, list[str]]:
    """Return the active playground-version-pin waiver, plus any problems found.

    Mirrors check_npm_audit.py's fail-closed shape: a missing, malformed, or
    expired waiver returns (None, problems) and accepts nothing.
    """
    if not _WAIVERS.exists():
        return None, [f"waiver registry not found: {_WAIVERS}"]
    parse_waivers = _waiver_parser().parse_waivers
    problems: list[str] = []
    for waiver in parse_waivers(_WAIVERS.read_text(encoding="utf-8")):
        if waiver.get("kind") != "playground-version-pin":
            continue
        waiver_id = waiver.get("id") or "<missing id>"
        if waiver.get("repo") != "tods-validate":
            continue
        wanted_check = "tests/test_playground.py::test_playground_installs_this_projects_version"
        if waiver.get("check") != wanted_check:
            continue
        missing = [f for f in _WAIVER_REQUIRED_FIELDS if not waiver.get(f)]
        if missing:
            problems.append(f"{waiver_id}: missing required field(s): {', '.join(missing)}")
            continue
        try:
            granted = date.fromisoformat(waiver["granted"])
            expires = date.fromisoformat(waiver["expires"])
        except ValueError:
            problems.append(f"{waiver_id}: granted and expires must be ISO dates")
            continue
        if expires < granted:
            problems.append(f"{waiver_id}: expiry precedes granted date")
            continue
        if expires < date.today():
            problems.append(f"{waiver_id}: expired on {waiver['expires']}")
            continue
        return waiver, problems
    return None, problems


def test_playground_installs_this_projects_version() -> None:
    # The page micropip-installs `tods-validate==<this>` from PyPI, so a pin left
    # behind at the previous release means the "try it without installing
    # anything" path validates with the previous release's rule set while the
    # rule pages served from the same site describe the current one. That is a
    # real bug class (#136's root cause): keep this assertion strict.
    #
    # The one case it must not block is the reverse gap: pyproject.toml's
    # version was bumped for a release whose GitHub Release/publish never
    # happened (again #136), so re-pinning the page to the last version that
    # is actually on PyPI is correct, not a bug -- and correct only for that
    # exact, already-diagnosed pair of versions. A dated, owned,
    # non-expired waiver in waivers.yml naming exactly this pin and exactly
    # this project version is the only thing that excuses the mismatch; a
    # missing, expired, or mismatched waiver still fails the gate.
    project = tomllib.loads(_PYPROJECT.read_text())["project"]["version"]
    pin = _pinned_version()
    if pin == project:
        return

    waiver, problems = _playground_version_pin_waiver()
    assert not problems, (
        f"playground pins {pin!r} but pyproject.toml is {project!r}, and "
        f"waivers.yml has a problem: {'; '.join(problems)}"
    )
    assert waiver is not None, (
        f"playground pins {pin!r} but pyproject.toml is {project!r}, and no "
        f"active playground-version-pin waiver in waivers.yml covers the gap "
        f"(see #136)"
    )
    assert waiver["pinned_version"] == pin, (
        f"waiver {waiver['id']} covers pin {waiver['pinned_version']!r}, "
        f"but the page now pins {pin!r}"
    )
    assert waiver["project_version"] == project, (
        f"waiver {waiver['id']} covers project version "
        f"{waiver['project_version']!r}, but pyproject.toml is now {project!r}"
    )


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
