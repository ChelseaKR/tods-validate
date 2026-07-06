<!--
Thanks for a PR. See CONTRIBUTING.md for the local gate (`make verify`) and
DEFINITION_OF_DONE.md for what "done" means here. Delete sections that don't
apply (e.g. most PRs are not a new rule).
-->

## What and why

<!-- What changed, and why. Link an issue if one exists. -->

## Definition of Done

- [ ] `make verify` passes locally (lint, format, mypy, tests + coverage
      floor, docs-drift check, i18n check, pip-audit, gitleaks)
- [ ] `CHANGELOG.md` updated if behavior changed
- [ ] Commits signed off (`git commit -s`)

### If this adds or changes a rule

- [ ] New passing fixture + failing fixture under `tests/fixtures/`
- [ ] `docs/rules.md` regenerated (`python scripts/generate_rules_doc.py`)
- [ ] Spec citation is real; ambiguity (if any) recorded in
      `docs/spec-questions.md` rather than guessed

### If this touches a workflow, `action.yml`, or `Dockerfile`

- [ ] New/changed `uses:` is pinned to a full 40-char commit SHA
- [ ] No `${{ }}` expression is interpolated directly into a `run:` shell
      block (route it through `env:` instead — see `docs/CONFORMANCE-GAPS.md#ci-cd`)
- [ ] Permissions are least-privilege and escalated at job level, not workflow level
- [ ] `zizmor` is clean (`zizmor --min-severity high .github/workflows/ action.yml`)

### If this adds a new external attack surface or touches personal data handling

- [ ] Read through `SECURITY.md`'s threat model; update it if the surface changed
- [ ] `docs/RESPONSIBLE-TECH-AUDITS.md` §C/F reflects the change
