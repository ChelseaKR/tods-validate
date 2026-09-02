# Runbook: publish the VS Code extension

Last verified: 2026-08-27
Recheck cadence: whenever `editor/vscode/package.json` or
`.github/workflows/vscode-extension.yml` changes, and before any attempt to
publish.

## Status

**Not published.** `editor/vscode/README.md` has said so since the extension
landed, and it is still true. This runbook exists because EXP-10 and phase 4
of [`../MULTIYEAR-PLAN.md`](../MULTIYEAR-PLAN.md) ask for the extension to be
installable from a marketplace *or* for the phase to record why it is not.
This is that record, written as the steps rather than as an excuse, so the
remaining work is one session rather than a research project.

## Why it is not published

Publishing needs two publisher accounts and a terms acceptance, none of which
a repository can hold or an automated pass can create:

- **Visual Studio Marketplace** needs an Azure DevOps organisation, a
  publisher created under it, and a personal access token scoped to
  Marketplace (Manage). The publisher id `tods-validate`, already declared in
  `editor/vscode/package.json`, has to be registered by a person and may be
  taken.
- **Open VSX** needs an Eclipse Foundation account with the **Eclipse
  Contributor Agreement signed**, which is a legal acceptance by a named human.

Everything else is done. CI builds the VSIX on every change to
`editor/vscode/**`, type-checks it, audits its dependencies at `--audit-level=high`,
and verifies the packaged archive actually contains `extension/LICENSE.txt`
and `extension/out/extension.js` before uploading it as an artifact. The
manifest already carries `publisher`, `license`, `repository`, `homepage`,
`bugs`, `keywords`, `categories`, and an `engines.vscode` floor.

## When you are ready

Decide the version first. The extension is at `0.1.0` while the Python package
is at `0.10.0`; they version independently and always have, but a Marketplace
listing showing `0.1.0` for a tool at `0.10.0` reads as abandoned. Either bump
the extension or say in its README that the numbers are unrelated.

```sh
cd editor/vscode
npm ci --ignore-scripts
npm run check          # the same type-check CI runs
npm run package        # produces tods-validate-<version>.vsix

# Install the built VSIX in a real editor and use it against a real feed
# before publishing. No gate in this repository has ever done that, and a
# packaged extension that activates and does nothing is a packaged extension.
code --install-extension tods-validate-*.vsix
```

Then, once the accounts exist:

```sh
npx @vscode/vsce login tods-validate     # prompts for the Marketplace PAT
npx @vscode/vsce publish --packagePath tods-validate-*.vsix

npx ovsx publish tods-validate-*.vsix --pat "$OPEN_VSX_TOKEN"
```

## After publishing

- Update `editor/vscode/README.md`: it currently states the extension is not
  published, and that sentence becomes false the moment it is.
- Update the `## Editor integration` section of the root `README.md` the same
  way.
- Close EXP-10 in `docs/ideation/03-expansions.md` and update phase 4 of
  `docs/MULTIYEAR-PLAN.md`.
- Do **not** wire publishing into CI on the first pass. A publish token is a
  write credential to a public registry; add it only after a manual publish has
  worked once, scoped to an environment, and with the same trusted-publisher
  reasoning `pypi-publish.yml` documents.

<!-- doc-currency: sha256=42f6be8d1d50 -->
