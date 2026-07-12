# TODS Validate for VS Code

A thin VS Code client for the `tods-validate` language server. It validates
[TODS](https://tods-transit.org) feeds inline: open or save any TODS file and
the whole feed is re-validated, with findings shown at their row and field,
rule descriptions on hover, and quick fixes for the safely fixable ones.

The extension does no validation itself. All of that lives in the Python
language server, which this client launches over stdio.

## Prerequisites

Install the language server (it ships with the Python package's `lsp` extra) and
make sure `tods-validate-lsp` is on your `PATH`. `pipx` keeps the server in an
isolated environment and is the recommended editor install:

```sh
pipx install 'tods-validate[lsp]'
command -v tods-validate-lsp  # macOS/Linux: prints the executable path
# where tods-validate-lsp     # Windows
```

Installing into an existing environment with
`pip install 'tods-validate[lsp]'` also works.

If it lives somewhere not on `PATH`, set **`tods-validate.serverPath`** in your
VS Code settings to its full path. Find that path with
the commands above. A startup error includes an **Open setup guide** action
that returns to these instructions.

## Build and try it locally

This folder is a standard TypeScript VS Code extension. From `editor/vscode/`:

```sh
npm install
npm run compile
```

Then press **F5** in VS Code with this folder open to launch an Extension
Development Host. Open a folder containing a TODS feed (for example the repo's
`examples/sample-feed/`), open `run_events.txt`, and you should see diagnostics,
hovers, and quick fixes. Introduce a problem (a stray space in an ID, a duplicate
row) and save to watch it update.

## Package a VSIX

```sh
npm run package   # produces tods-validate-<version>.vsix via @vscode/vsce
code --install-extension tods-validate-*.vsix
```

The repository's **VS Code extension** workflow performs the same locked install,
type-check, package, and vulnerability-audit steps and uploads the VSIX as a
workflow artifact. The extension has not been published to the Marketplace or
Open VSX; publisher-account setup and terms acceptance remain maintainer-only
steps. Verify the VSIX in a real editor before relying on it.
