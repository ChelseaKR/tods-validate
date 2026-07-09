# 0003 — VS Code extension lives as a nested project under editor/vscode

- Status: accepted (backfilled 2026-07-09; layout in force since the extension landed)
- Date: 2026-07-09

## Context

The VS Code extension is a TypeScript/npm project wrapping the Python LSP
server (`tods-validate lsp`). It has its own toolchain, lockfile, and build
(`vsce`), none of which the Python packaging can express. The options were a
separate repository, a monorepo tool, or a nested directory.

## Decision

Keep the extension in-tree at `editor/vscode/` as a self-contained nested
npm project. The Python package neither includes nor depends on it; the
extension depends on the CLI being installed. A separate repo would split
one product's history and force cross-repo versioning for a component that
releases rarely; a monorepo tool is machinery this repo does not otherwise
need.

## Consequences

- One clone gives the whole product: CLI, library, LSP, Action, playground,
  extension.
- The nested `package.json`/`package-lock.json` is a second dependency
  surface to keep patched (Dependabot covers it).
- The nesting deviates from the one-project-per-repo default the code
  standard assumes (CQ-26); this record is the declaration.
- Marketplace publishing remains a separate, human-gated step; the extension
  being unpublished does not block the rest of the product.
