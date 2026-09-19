"""The browser playground stays wired to the public API it calls.

The playground runs hardcoded Python in Pyodide, so the only thing that can
silently break it from this side is renaming the API it imports. These guards
fail loudly if that happens. (The page itself needs a browser, so it is tested
end to end by scripts/check-playground-boots.cjs against the deployed URL,
not from here; see web/README.md.)
"""

import importlib.util
import json
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


# ---------------------------------------------------------------------------
# The head, and the shared origin it has to survive
#
# The playground is served at a path under chelseakr.github.io, which five
# sibling projects also publish under, and https://chelseakr.github.io/ is
# itself a 404. Two mistakes follow, and neither shows up in a browser, because
# the browser has already been handed the page: a canonical or og:url naming
# the bare origin, which tells a crawler that six unrelated projects are one
# page, and a root-relative href, which resolves against the origin rather than
# /tods-validate/ and so lands on another project or on nothing.
#
# web/index.html is hand-written, with no generator behind it, so nothing here
# is checked by the docs-drift gate. This module is where the page's other
# hand-editable invariants already live, so the checks go here rather than in a
# second file that would have to remember to exist.
# ---------------------------------------------------------------------------

# Written out rather than read from tods_validate.report.RULE_PAGE_BASE. An
# expectation derived from the constant under test moves with the mistake and
# stays green.
_PUBLISHED_AT = "https://chelseakr.github.io/tods-validate/"

# The share card, written out for the same reason as the URL above. 1200x630 is
# the size LinkedIn, Slack and X all render whole; anything else they crop.
_SOCIAL_CARD_FILE = "og-card.png"
_SOCIAL_CARD_SIZE = (1200, 630)


def _png_size(path: Path) -> tuple[int, int]:
    """Width and height from a PNG IHDR, so no decoder is needed to check one."""
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


# Words that would make the description claim something this project does not.
# TODS is somebody else's specification: NOTICE says in full that this is not
# affiliated with, endorsed by, or sponsored by Cal-ITP, MobilityData, the TODS
# working group, or any agency or vendor. A description is read in places
# NOTICE is not, so it may not contradict it. Nor may it state coverage: the
# rule set moves with the spec, and tests/test_readme_claims.py is what holds
# the README's figures to the registry.
_FORBIDDEN_IN_DESCRIPTION = (
    "official",
    "endorsed",
    "approved",
    "certified",
    "conformant",
    "conformance",
    "compliant",
    "authoritative",
    "complete coverage",
    "full coverage",
)


def _head() -> str:
    return _HTML.read_text(encoding="utf-8").split("</head>", 1)[0]


def _meta(attribute: str, name: str) -> str | None:
    found = re.search(
        rf'<meta\s+{attribute}="{re.escape(name)}"\s+content="([^"]*)"\s*/?>',
        _head(),
        re.S,
    )
    if found is None:
        found = re.search(
            rf'<meta\s*\n\s*{attribute}="{re.escape(name)}"\s*\n\s*content="([^"]*)"\s*\n\s*/>',
            _head(),
            re.S,
        )
    return found.group(1) if found else None


def test_the_playground_canonical_is_itself_and_keeps_the_project_path() -> None:
    assert f'<link rel="canonical" href="{_PUBLISHED_AT}" />' in _head()
    assert _meta("property", "og:url") == _PUBLISHED_AT


def test_the_playground_carries_a_share_card_that_agrees_with_the_page() -> None:
    description = _meta("name", "description")
    assert description is not None
    assert description.strip()
    assert _meta("property", "og:description") == description
    title = re.search(r"<title>([^<]+)</title>", _head())
    assert title is not None
    assert _meta("property", "og:title") == title.group(1)
    assert _meta("property", "og:type") == "website"
    assert _meta("property", "og:site_name") == "tods-validate"
    assert _meta("name", "twitter:card") == "summary_large_image"


def test_the_playground_share_card_is_a_landscape_image_that_is_published() -> None:
    """The page said what it was and showed nothing.

    The head carried og:title, og:description and og:url and no image at all,
    so every share of the playground arrived as gray text on LinkedIn, Slack
    and X. Two ways an image tag goes wrong just as quietly, and both are
    checked here rather than discovered in someone else's feed: a URL naming a
    file that is not in web/, which pages.yml uploads whole, so the card 404s;
    and a file that is there at the wrong shape, which the networks then crop
    to their landscape box with the project name outside the frame.
    """
    card = _meta("property", "og:image")
    assert card == f"{_PUBLISHED_AT}{_SOCIAL_CARD_FILE}", (
        f"og:image must be the published card's absolute URL, not {card!r}"
    )
    assert _meta("name", "twitter:image") == card
    assert (_meta("property", "og:image:alt") or "").strip()
    assert (_meta("name", "twitter:image:alt") or "").strip()

    published = _HTML.parent / _SOCIAL_CARD_FILE
    assert published.is_file(), f"{_SOCIAL_CARD_FILE} is advertised but not in web/"
    assert _png_size(published) == _SOCIAL_CARD_SIZE
    assert _meta("property", "og:image:width") == str(_SOCIAL_CARD_SIZE[0])
    assert _meta("property", "og:image:height") == str(_SOCIAL_CARD_SIZE[1])


def test_the_playground_description_claims_nothing_the_page_does_not() -> None:
    description = _meta("name", "description")
    assert description is not None
    lowered = description.lower()
    for word in _FORBIDDEN_IN_DESCRIPTION:
        assert word not in lowered, (
            f"the description says {word!r}. This project validates a specification it "
            f"does not speak for, and states no coverage it has not measured. See NOTICE."
        )
    assert re.search(r"\b[0-9]+\b", description) is None, (
        f"the description states a figure nothing derives: {description!r}"
    )


def test_the_playground_makes_no_root_relative_reference() -> None:
    # Protocol-relative //host/x is a different thing and is not this mistake.
    page = _HTML.read_text(encoding="utf-8")
    rooted = re.findall(r'(?:href|src)="(/(?!/)[^"]*)"', page)
    assert rooted == [], f"root-relative references escape /tods-validate/: {rooted}"


# The page carries exactly one scanner suppression. Semgrep's
# html.security.audit.missing-integrity rule matches every link whose href
# carries a scheme, whatever its rel, so it fires on the canonical link; that
# finding is a false positive, and the comment above the tag says why. A
# `nosemgrep` marker covers the line it sits on and the line below it, so where
# it sits is the whole of how narrow it is. It must not reach the Pyodide
# `<script src>` further down, whose integrity hash this same rule is the
# reason for: that one is the finding the rule exists for, and it has to stay
# catchable.
_SUPPRESSION_MARKER = "nosemgrep: html.security.audit.missing-integrity.missing-integrity"


def test_the_only_suppression_sits_directly_above_the_canonical() -> None:
    lines = _HTML.read_text(encoding="utf-8").splitlines()
    marked = [i for i, line in enumerate(lines) if "nosemgrep" in line]
    assert len(marked) == 1, f"the page carries {len(marked)} nosemgrep markers, expected 1"
    index = marked[0]
    assert _SUPPRESSION_MARKER in lines[index], (
        f"the page suppresses something other than the missing-integrity rule: {lines[index]!r}"
    )
    assert lines[index + 1].strip().startswith('<link rel="canonical" '), (
        f"the marker covers the wrong line: {lines[index + 1]!r}"
    )


def test_the_external_runtime_script_still_carries_an_integrity_hash() -> None:
    # The other half of the same decision: the suppression above is defensible
    # only while the real subresource on this page is still hashed. Every
    # script with a scheme is external and must carry a hash. The one relative
    # script is the site's own same-origin analytics loader (ADR 0010), which is
    # published from this repository alongside the page itself.
    page = _HTML.read_text(encoding="utf-8")
    tags = re.findall(r"<script\b[^>]*\bsrc=[^>]*>", page, re.S | re.I)
    external = [tag for tag in tags if re.search(r'\bsrc="[a-z][a-z0-9+.-]*:', tag, re.I)]
    assert external, "the Pyodide runtime script is missing"
    for tag in external:
        assert "integrity=" in tag, f"an external script ships without an SRI hash: {tag!r}"
    local = [tag for tag in tags if tag not in external]
    assert local == ['<script src="analytics.js" defer>'], local


# ---------------------------------------------------------------------------
# The route back to the repository, and the machine-readable description
#
# DISCOVERY-AND-ADOPTION-STANDARD.md DISC-02 asks that the homepage named in a
# repository's GitHub About links to `github.com/<owner>/<repo>`. Measured on
# 2026-09-13, the live page carried three URLs with `github` in them and all
# three were `chelseakr.github.io`: the canonical, the og:url and the share
# card. There was no route from the page to the source at all.
#
# That is not a formality. This page is where an agency meets the validator
# after a search; the CLI, the pre-commit hook, the GitHub Action, the Docker
# image and the editor extension are all in the repository, and a reader who
# arrived here had no way to reach any of them.
#
# The JSON-LD block is the other half: a crawler reading this page had to infer
# from prose that it is software, that it runs in the reader's own browser, and
# that it is free. Everything in that block is a value this repository already
# states somewhere, and the checks below read it from that somewhere rather
# than from a second copy kept here -- an expectation copied out of the thing
# it checks moves with the mistake and stays green.
# ---------------------------------------------------------------------------

# Anchors, with their link text, so a backlink with an empty label cannot pass.
# `[^>]*` after the href is what carries this page's habit of putting the `>`
# on the following line.
_ANCHOR_RE = re.compile(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>\s*(.*?)\s*</a\s*>', re.S)
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

# Fields that would put a figure in the head. softwareVersion is a real number
# this project derives (pyproject.toml -> the pin above), and it is still
# refused here: the head is served to a crawler long after a release moves it,
# and nothing a reader can see would show it had gone stale. The rest are
# figures nothing in this repository derives at all.
_FORBIDDEN_IN_STRUCTURED_DATA = (
    "softwareVersion",
    "version",
    "aggregateRating",
    "ratingValue",
    "reviewCount",
    "ratingCount",
    "interactionCount",
    "interactionStatistic",
    "datePublished",
    "dateModified",
    "fileSize",
)


def _project_urls() -> dict[str, str]:
    urls: dict[str, str] = tomllib.loads(_PYPROJECT.read_text())["project"]["urls"]
    return urls


def _repository_url() -> str:
    """Where this project says it lives -- one declaration, in pyproject.toml."""
    return _project_urls()["Repository"]


def _license_url() -> str:
    """The SPDX page for the license pyproject.toml declares, built from it."""
    spdx = tomllib.loads(_PYPROJECT.read_text())["project"]["license"]
    return f"https://spdx.org/licenses/{spdx}.html"


def _canonical() -> str | None:
    found = re.search(r'<link rel="canonical" href="([^"]+)"', _head())
    return found.group(1) if found else None


def _structured_data() -> dict[str, object]:
    """The page's one JSON-LD node, parsed.

    A block that is not valid JSON raises here rather than being skipped, which
    is the whole point: a malformed node is invisible in a browser and silently
    ignored by every consumer that would have read it.
    """
    blocks = _LD_JSON_RE.findall(_HTML.read_text(encoding="utf-8"))
    assert len(blocks) == 1, f"expected exactly one JSON-LD block, found {len(blocks)}"
    parsed = json.loads(blocks[0])
    assert isinstance(parsed, dict), f"the JSON-LD node is a {type(parsed).__name__}, not an object"
    return parsed


def test_the_playground_links_back_to_the_repository() -> None:
    anchors = _ANCHOR_RE.findall(_HTML.read_text(encoding="utf-8"))
    # The negative control this check needs against itself: if the page's
    # anchor markup changes shape and this sweep stops matching, an empty
    # result would satisfy every assertion below by vacuum.
    assert anchors, "the anchor sweep matched nothing; it has stopped reading this page"

    repository = _repository_url()
    labels = [text for href, text in anchors if href == repository]
    assert labels, (
        f"the playground does not link to {repository} (DISC-02). The links it does carry are "
        f"{sorted({href for href, _ in anchors})}. This page is the only route a reader who "
        f"arrived from a search has to the CLI, the Action, the hook and the extension."
    )
    assert all(label.strip() for label in labels), "the repository link carries no link text"


def test_the_playground_carries_one_well_formed_structured_data_node() -> None:
    data = _structured_data()
    assert data.get("@context") == "https://schema.org"
    assert data.get("@type") in {"WebApplication", "SoftwareApplication"}, (
        f"the node describes a {data.get('@type')!r}; this page is an application"
    )


def test_the_structured_data_agrees_with_the_page_it_describes() -> None:
    data = _structured_data()
    page = _HTML.read_text(encoding="utf-8")

    heading = re.search(r"<h1>([^<]+)</h1>", page)
    assert heading is not None
    assert data.get("name") == heading.group(1).strip()
    assert data.get("description") == _meta("name", "description")
    assert data.get("url") == _canonical()
    assert data.get("image") == _meta("property", "og:image")


def test_the_structured_data_agrees_with_what_the_project_declares() -> None:
    data = _structured_data()
    assert data.get("codeRepository") == _repository_url()
    assert data.get("license") == _license_url()
    # Free to use is a property of this page, not a price this repository could
    # get wrong later: the validator runs in the reader's browser and the
    # license above is what permits it.
    assert data.get("isAccessibleForFree") is True


def test_the_structured_data_states_no_figure_nothing_re_derives() -> None:
    data = _structured_data()
    present = [field for field in _FORBIDDEN_IN_STRUCTURED_DATA if field in data]
    assert not present, (
        f"the structured data states {present}. A figure in the head is served to crawlers "
        f"long after it stops being true, and no reader of this page can see that it has."
    )
    assert not re.search(r"\b[0-9]+\b", str(data.get("description", ""))), (
        "the structured data's description states a figure nothing derives"
    )
