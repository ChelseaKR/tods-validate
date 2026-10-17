# Changelog

The extension is versioned separately from the `tods-validate` Python package.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- The packaged VSIX now includes its runtime dependency,
  `vscode-languageclient`. It was excluded by `.vscodeignore`, so an installed
  copy could not activate.

## [0.1.0]

Not published to the Marketplace or Open VSX.

- A thin client for the `tods-validate-lsp` language server: diagnostics at the
  row and field, rule descriptions on hover, and quick fixes for the safely
  fixable findings.
- The `tods-validate.serverPath` setting for a server that is not on `PATH`.
