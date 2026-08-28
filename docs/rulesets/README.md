# Branch rulesets

## What this directory is, and what it is not

`main.json` is the **intended** ruleset for the default branch, in the exact
shape `POST /repos/{owner}/{repo}/rulesets` accepts. It is not an export of a
live ruleset, and committing it does not apply it. No ruleset is enabled on
this repository as of 2026-08-27; `docs/CONFORMANCE-GAPS.md` records that gap
under **CQ-37 to 43** and **CICD-03/11-18**, and it stays open until somebody
applies this file and replaces it with the export.

Writing it down is worth doing anyway. The gap entry previously carried the
intended ruleset as a paragraph of prose, which is the definition of tribal
knowledge: unreviewable, undiffable, and impossible to check against the CI
jobs it names. As a file it is all three, and
`tests/test_branch_ruleset.py` checks the one part of it that drifts on its
own: every status check it requires has to be a check this repository's
workflows actually produce, and every merge-blocking check the workflows
produce has to be required. A ruleset naming a job that was renamed is a
ruleset that blocks nothing.

## Why `zizmor` is not a required check

`docs/CONFORMANCE-GAPS.md` described the intended ruleset in prose and listed
`zizmor` among the checks to require. Applying that literally would have
blocked every pull request. `zizmor.yml`'s `pull_request` trigger is filtered
to `.github/workflows/**` and `action.yml`, so on a pull request that touches
neither, the workflow does not run, the check never reports, and a merge that
requires it can never happen. The same reasoning excludes any future
path-filtered workflow. `tests/test_branch_ruleset.py` enforces the rule in
both directions, so this cannot be re-introduced by editing the file, and
zizmor becomes requirable the moment its trigger stops being filtered.

## Applying it

This needs a live GitHub settings change, which no automated pass makes.

```sh
gh api --method POST repos/ChelseaKR/tods-validate/rulesets \
  --input docs/rulesets/main.json
```

Then replace this file with the export, so the committed artifact becomes a
record of what is enforced rather than of what was intended:

```sh
gh api repos/ChelseaKR/tods-validate/rulesets            # find the id
gh api repos/ChelseaKR/tods-validate/rulesets/<id> > docs/rulesets/main.json
```

The export carries server-assigned fields (`id`, `node_id`, `created_at`,
`_links`, `source`) that the create payload does not. `tests/test_branch_ruleset.py`
reads only `rules`, so it keeps working across that swap.

## The limit no ruleset fixes

`bypass_actors` is empty and `require_code_owner_review` is on, which on a
solo-maintained repository means the maintainer cannot approve their own pull
request and cannot bypass the requirement either. That is deliberate: the
honest state is "self-review is a structural limitation", not "self-review
counts as review". `.github/CODEOWNERS` is ready for a second person; until
there is one, expect to need an explicit, recorded bypass to merge, and
record it. See phase 4 of [`../MULTIYEAR-PLAN.md`](../MULTIYEAR-PLAN.md).
