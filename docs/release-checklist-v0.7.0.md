# Release checklist: v0.7.0

Everything below the "Owner steps" line requires the repository owner
(tag signing key, GitHub UI). The staging work — CHANGELOG `## v0.7.0`
section, version bumps in `pyproject.toml` / `CITATION.cff` /
`README.md` (`@v0.7.0` snippets) / `web/index.html` (playground wheel
pin) — is already on the `chore/v0.7.0-release-prep` branch.

## What the tag/release will trigger (cite: repo workflows)

All three release workflows fire on **`release: types: [published]`**,
not on the tag push itself — pushing the tag alone publishes nothing;
publishing the GitHub Release is the trigger:

- `.github/workflows/pypi-publish.yml` — first runs the reusable
  `.github/workflows/verify.yml` with the release tag, which enforces:
  - `make verify` (full merge-blocking gate set) at the tagged commit;
  - **version consistency (REL-03)**: tag `v0.7.0` == `pyproject.toml`
    `version` == `CITATION.cff` `version`, and `CHANGELOG.md` has a
    `## v0.7.0` heading — all already staged;
  - **the tag is an annotated, signed tag object (REL-08)** — a
    lightweight tag fails the release. (Historical tags through v0.6.0
    predate this check; v0.7.0 is the first tag it enforces, per
    `docs/CONFORMANCE-GAPS.md`.)
  Then it builds sdist+wheel, generates a CycloneDX SBOM, attests SLSA
  build provenance, publishes to PyPI via OIDC Trusted Publishing, and a
  `verify-published` job re-downloads the artifact from PyPI and checks
  its attestation.
- `.github/workflows/docker.yml` — builds and pushes the image to GHCR.
- `.github/workflows/release-corpus.yml` — builds the conformance corpus
  and attaches it to the release.

## Owner steps

1. **Merge** the `chore/v0.7.0-release-prep` PR into `main` and confirm
   CI on `main` is green. (If merge day is not 2026-07-09, touch up the
   `CHANGELOG.md` date and `CITATION.cff` `date-released` first.)
2. **Create the signed tag** at the merge commit on `main`:

   ```sh
   git tag -s v0.7.0 -m "release: v0.7.0"
   git push origin v0.7.0
   ```

   It must be `-s` (annotated + signed): `verify.yml`'s REL-08 step runs
   `git cat-file -t` and `git verify-tag` and fails the publish otherwise.
3. **Draft the release** in the GitHub UI (Releases → "Draft a new
   release" → choose tag `v0.7.0`). Title `v0.7.0`; paste or
   auto-generate notes from the CHANGELOG `## v0.7.0` section.
4. **Marketplace listing — same draft-release screen.** Tick the
   checkbox **"Publish this Action to the GitHub Marketplace"**.
   - First time only: GitHub will ask you to accept the **GitHub
     Marketplace Developer Agreement** and requires **two-factor auth**
     on the account.
   - The listing requirements are already met in `action.yml`: it is at
     the repo root and has `name: tods-validate`, a `description`, and
     `branding` (`icon: check-circle`, `color: green`). The Action name
     must be unique across the Marketplace; if `tods-validate` is taken,
     the UI will say so and the `name:` in `action.yml` must change.
   - **Category suggestion**: primary **"Continuous integration"**,
     secondary **"Code quality"**.
5. **Publish the release.** This fires the three workflows above.
6. **Verify green**: `gh run list --workflow pypi-publish.yml` (and
   `docker.yml`, `release-corpus.yml`), or the Actions tab. The
   `verify-published` job is the last word — green means the artifact on
   PyPI is the one that was verified.
7. **Create/move the floating major tag** — only after v0.7.0 exists and
   published green. Marketplace/README consumers conventionally pin a
   major tag; keep it signed like the release tags:

   ```sh
   git tag -fs v1 v0.7.0 -m "v1 -> v0.7.0"
   git push --force origin v1
   ```

   (While the project is pre-1.0, `v0` is the semantically honest
   floating tag if you prefer; the README examples pin the exact
   `@v0.7.0` either way, so the floating tag is a convenience alias.
   Note the version-consistency guard only applies to `vX.Y.Z` release
   tags passed into `verify.yml`; a floating `v1`/`v0` tag never goes
   through it.)
8. **Redeploy GitHub Pages** (`.github/workflows/pages.yml` is
   `workflow_dispatch`-only) — but only **after** the PyPI publish
   succeeds: the browser playground (`web/index.html`) now pins
   `tods-validate==0.7.0`, which must exist on PyPI for the playground
   to load.
9. Spot-check the Marketplace listing page renders (icon, description,
   README) and that `uses: ChelseaKR/tods-validate@v0.7.0` resolves in a
   consumer workflow.

## Explicitly not in v0.7.0

- PR #51 (`--spec-version 1.0.0`, E4) and PR #50 (EXP-02 GTFS-drift
  diagnosis) were still open when this release was staged and are not
  part of v0.7.0 or its CHANGELOG section. If either merges before the
  tag is cut, add it to the `## v0.7.0` section first.
