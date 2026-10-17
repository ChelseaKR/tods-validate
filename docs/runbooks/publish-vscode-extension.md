# Runbook: publish the VS Code extension

Last verified: 2026-10-17
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

- **Visual Studio Marketplace** needs an Azure DevOps organization, a
  publisher created under it, and a personal access token scoped to
  Marketplace (Manage). The publisher id `tods-validate`, already declared in
  `editor/vscode/package.json`, has to be registered by a person and may be
  taken.
- **Open VSX** needs an Eclipse Foundation account with the **Eclipse
  Contributor Agreement signed**, which is a legal acceptance by a named human.

Everything else is done. CI builds the VSIX on every change to
`editor/vscode/**`, type-checks it, and verifies the packaged archive actually
contains `extension/LICENSE.txt`, `extension/out/extension.js` and the runtime
dependency `extension/node_modules/vscode-languageclient/package.json` before
uploading it as an artifact. The manifest already carries `publisher`,
`license`, `repository`, `homepage`, `bugs`, `keywords`, `categories`, and an
`engines.vscode` floor.

### Checked 2026-10-17

The VSIX was built and unpacked, and its entry point was loaded under Node with
a stub `vscode` module.

| Item | State |
| --- | --- |
| `publisher`, `license`, `repository` (now with `directory`), `homepage`, `bugs`, `engines.vscode`, `categories`, `keywords` | Present in `package.json`. |
| `README.md`, `LICENSE.txt` | Packaged. |
| `CHANGELOG.md` | Added, so the Marketplace's Changelog tab has content. |
| `icon` | **Absent.** The Marketplace shows a default tile. An icon is optional; add a 128x128 or larger PNG and an `"icon"` field if one is wanted. |
| Runtime dependency | **Was missing.** `.vscodeignore` excluded `node_modules/**`, so the VSIX shipped without `vscode-languageclient` and `require("vscode-languageclient/node")` failed at activation. The exclusion is removed; the VSIX now carries the five production packages. The CI content check was extended so this cannot recur unnoticed. |
| `vsce package` | Succeeds; 208 files, about 300 KB. It warns that the extension is not bundled. Bundling would shrink it and is optional. |

The extension's dependencies are audited by `make npm-audit` in the `audit` job
of `ci.yml`, not by the packaging workflow. That is deliberate: the packaging
workflow only runs when `editor/vscode/**` changes, and a new advisory arrives
against a lockfile nobody has touched. On 2026-09-10 that job had last run
green four days earlier while `GHSA-2883-xcg3-v3hh` was live in the committed
lock. `make npm-audit` walks every `package-lock.json` in the repository, runs
on every pull request, and adjudicates findings against `waivers.yml`.

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

Then, once the accounts exist, in this order. Vendor sign-up screens change, so
recheck each against the vendor's own publishing guide at the time.

**Visual Studio Marketplace**

1. Create or choose an Azure DevOps organization (dev.azure.com).
2. Create the publisher at <https://marketplace.visualstudio.com/manage> with id
   `tods-validate`. If the id is taken, change `publisher` in `package.json`
   and in the `login` command below.
3. In Azure DevOps, create a personal access token: organization set to *All
   accessible organizations*, scope *Marketplace* with *Manage*. Short expiry.
4. Publish:

```sh
npx @vscode/vsce login tods-validate     # prompts for the PAT
npx @vscode/vsce publish --packagePath tods-validate-*.vsix
```

**Open VSX**

1. Sign in at <https://open-vsx.org> with GitHub, link an Eclipse Foundation
   account from the profile page, and sign the Publisher Agreement.
2. Create an access token under *Settings*, then *Access Tokens*.
3. Claim the namespace once, then publish:

```sh
npx ovsx create-namespace tods-validate --pat "$OPEN_VSX_TOKEN"
npx ovsx publish tods-validate-*.vsix --pat "$OPEN_VSX_TOKEN"
```

Revoke both tokens afterwards if they will not be reused; see
[`secret-exposure.md`](secret-exposure.md) for where each is revoked.

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

<!-- doc-currency: sha256=d8fc98cb43a9 -->
