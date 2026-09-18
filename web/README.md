# tods-validate playground

A zero-install, zero-upload TODS validator that runs entirely in the browser via
[Pyodide](https://pyodide.org). `index.html` loads Pyodide, installs the
published `tods-validate` wheel with micropip, writes the chosen files into
Pyodide's virtual filesystem, and calls `validate_feed` + `render_html`. Because
the feed files and the report never leave the browser, it is safe for
non-public operational data.

Every page here (the playground, `privacy.html` and the generated rule catalog)
also loads `analytics.js`, which counts visits with Google Analytics 4 on the
live site only, never under Global Privacy Control, Do Not Track or the footer
opt-out, with ad features off and the page address sent without its query string
or fragment. It never reads the file input or the report. See
[ADR 0010](../docs/adr/0010-google-analytics-4-on-the-website.md) and
`privacy.html`. Served from `localhost` it loads nothing from Google.

## Test it locally before sharing it

This page needs a real browser, so it is not covered by the Python test suite
(only the API it depends on is, in `tests/test_playground.py`). Serve the folder
and open it:

```sh
python -m http.server -d web 8000
# then open http://localhost:8000
```

Select the files in `examples/sample-feed/` to confirm a clean pass, then a feed
with problems to confirm findings render. If Pyodide fails to load, update the
version in the `<script src=".../pyodide/vX.Y.Z/...">` tag to the current
[Pyodide release](https://github.com/pyodide/pyodide/releases).

To drive that same round trip without doing it by hand, point the deployment's
boot check at your local server (it needs `npm ci` first, for the browser the
accessibility toolchain already installs):

```sh
PLAYGROUND_URL=http://localhost:8000/index.html node scripts/check-playground-boots.cjs
```

## The backlink, and the structured data

`index.html` carries a link to <https://github.com/ChelseaKR/tods-validate> in
its footer and one `application/ld+json` node in its head. Both are gated by
`tests/test_playground.py`, alongside the page's other hand-edited invariants.

The link is DISC-02 in `DISCOVERY-AND-ADOPTION-STANDARD.md`. Until 2026-09-13
the page had no such link at all: the only three URLs on it with `github` in
them were `chelseakr.github.io` addresses -- the canonical, the `og:url` and
the share card. This page is where somebody meets the validator after a
search, and everything they would reach for next (the CLI, the GitHub Action,
the pre-commit hook, the Docker image, the editor extension) is in the
repository, so a page with no route to it ends the visit there.

The JSON-LD node states what the page already states, in a form a crawler does
not have to read prose to get: that this is a `WebApplication`, that it runs
in the reader's own browser (`browserRequirements`), that it costs nothing
(`isAccessibleForFree`), that it is Apache-2.0, and where the source is. Every
value in it is held somewhere else first -- `name` is the `<h1>`,
`description` is the meta description, `url` is the canonical, `image` is the
share card, and `license` and `codeRepository` come from `pyproject.toml` --
and the tests read it from those places rather than from a second copy kept in
the test file, because an expectation copied out of the thing it checks moves
with the mistake and stays green.

What the node deliberately leaves out, and why:

- **`softwareVersion`.** The page does pin a wheel version, in the script that
  installs it, and `test_playground_installs_this_projects_version` holds that
  pin to `pyproject.toml`. A copy of it in the head would be a different
  thing: a crawler is served the head long after a release moves, and nothing
  a reader can see would show that it had gone stale. The gate refuses the
  field outright rather than trying to keep a third copy honest.
- **`aggregateRating`, `ratingValue`, `reviewCount`, `interactionCount`.**
  There are no ratings, no reviews and no usage figure this repository
  measures. Structured data is the worst place to keep a number nothing
  re-derives, because no reader of the page can see it is wrong.
- **`datePublished` and `dateModified`.** A date nothing recomputes is the
  same claim in another shape.
- **A `Dataset` descriptor.** This page ships no dataset. Describing one would
  be soliciting a harvest of feeds that, by design, never leave the browser.

The reasoning lives here rather than in a comment in the page because
`web/index.html` is downloaded in full by every visitor and is held to a byte
ceiling in `perf/bundle-baseline.json`; this file is published but never
fetched by the playground.

## Deployment

The playground is published at
<https://chelseakr.github.io/tods-validate/>. GitHub Pages uses the GitHub
Actions build source; the **Deploy playground** workflow
(`.github/workflows/pages.yml`) publishes this folder as the last stage of a
release, called from `pypi-publish.yml` only after the released wheel has been
confirmed on PyPI, and can still be dispatched manually for an out-of-band
fix. Either way it refuses to deploy a page whose `TODS_VALIDATE_VERSION` pin
is not on PyPI, since the page installs that exact wheel in the browser.

The deployment is then checked against the live URL, not assumed from a green
deploy job:

- `scripts/check-deployed-playground.sh` fails if the served page is not
  byte-identical to the page this repository publishes — run right after each
  deploy against the tree that was just uploaded, and weekly
  (`.github/workflows/playground-deployment.yml`) against `web/index.html` on
  the default branch. It compared against the most recent release tag until
  2026-08-26, which held the weekly check red against a correct deployment:
  `v0.10.0` tags a page still pinned to `0.9.0`, the repin landed after the tag
  (#142), and a tag cannot be corrected in place.
- `scripts/check-playground-boots.cjs` drives the live page in a real browser:
  it waits for Pyodide to load and micropip to install the pinned wheel from
  PyPI, uploads a synthetic fixture, and fails unless the rendered report
  contains the finding that fixture triggers. This is the only check that shows
  the playground *works*. The two checks around it are both satisfied by a page
  that is byte-perfect, accessible, and broken for every visitor, which is what
  #136 shipped: a pin PyPI did not serve, so `micropip.install` rejected it for
  everyone while every gate stayed green.
- `scripts/pa11y-ci-live.cjs` runs axe and HTML_CodeSniffer at WCAG2AA against
  the live page. `make a11y` audits this folder's copy, which is the source of
  the deployment and not the deployment itself; this is what holds the artifact
  people actually open to the same standard. It loads the page with
  `?a11y-static=1`, which skips the Pyodide boot on purpose, so a green
  accessibility run says nothing about whether validation works.

`tests/test_playground.py` pins `TODS_VALIDATE_VERSION` to the version in
`pyproject.toml`, so the repository copy cannot be left behind either.

## rules/

`rules/` holds one permanent HTML page per rule ID plus an `index.html`
catalog, generated by `scripts/generate_rules_doc.py` from the rule registry
(the same run that regenerates `docs/rules.md`). Do not hand-edit files here;
run `python scripts/generate_rules_doc.py` to regenerate, and
`python scripts/generate_rules_doc.py --check` to verify they match the
registry (CI runs this). SARIF `helpUri` and the language server's hover text
link to `https://<pages-domain>/rules/<RULE_ID>.html`, so these URLs are a
permanence contract: filenames are the rule ID verbatim, and rule IDs are
never renumbered once released.
