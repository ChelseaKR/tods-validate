"""The browser playground stays wired to the public API it calls.

The playground runs hardcoded Python in Pyodide, so the only thing that can
silently break it from this side is renaming the API it imports. These guards
fail loudly if that happens. (The page itself needs a browser to test end to
end; see web/README.md.)
"""

from pathlib import Path

_HTML = Path(__file__).resolve().parent.parent / "web" / "index.html"


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
