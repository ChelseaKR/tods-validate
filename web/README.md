# tods-validate playground

A zero-install, zero-upload TODS validator that runs entirely in the browser via
[Pyodide](https://pyodide.org). `index.html` loads Pyodide, installs the
published `tods-validate` wheel with micropip, writes the chosen files into
Pyodide's virtual filesystem, and calls `validate_feed` + `render_html`. Because
nothing leaves the browser, it is safe for non-public operational data.

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
version in the script tag whose `src` contains `pyodide/vX.Y.Z` to the current
[Pyodide release](https://github.com/pyodide/pyodide/releases).

## Deploy

In **Settings → Pages**, set the source to **GitHub Actions**, then run the
**Deploy playground** workflow (`.github/workflows/pages.yml`). It publishes this
folder. Once it is live and verified, add the URL to the project README.
