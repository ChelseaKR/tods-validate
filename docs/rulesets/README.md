# Branch rulesets

## What this directory is, and what it is not

`main.json` is the **export** of the ruleset enforced on the default branch:
`protect-main`, id 18752857, applied 2026-09-01. Server-assigned fields (`id`,
`node_id`, `created_at`, `updated_at`, `source`, `_links`,
`current_user_can_bypass`) are stripped, so what is left is both a readable
record and a payload the API will accept back.

It was an intended ruleset until 2026-09-01, and the gap between the two
shapes cost something. The file said `name: main` while the live ruleset was
`protect-main`, so the documented apply command would have created a second
ruleset rather than updating the one already there, and three other documents
described a repository with no protection at all while `protect-main` had been
active since July. Committing an intent next to an unexamined live setting is
how that happens.

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

## Changing it

Editing this file changes nothing by itself. Apply it, then re-export.

**Update** the existing ruleset with `PUT` and its id. `PATCH` matches no
route on this endpoint and returns 404, which reads like a permissions problem
and is not one:

```sh
gh api -X PUT repos/ChelseaKR/tods-validate/rulesets/18752857 \
  --input docs/rulesets/main.json
```

`POST /repos/{owner}/{repo}/rulesets` creates a ruleset. Use it only for a
genuinely new one; against a name that already exists it produces a second
ruleset, and two rulesets both apply.

Then re-export, dropping the server-assigned fields:

```sh
gh api repos/ChelseaKR/tods-validate/rulesets/18752857 | python3 -c '
import json, sys
live = json.load(sys.stdin)
keep = ("name", "target", "enforcement", "conditions", "bypass_actors", "rules")
print(json.dumps({k: live[k] for k in keep}, indent=2))
' > docs/rulesets/main.json
```

Read the result before committing it. GitHub fills in parameters the payload
omits, so an export can contain settings nobody chose: applying the 2026-09-01
payload came back with `require_extra_approval_for_unattributed_changes: true`
on the `pull_request` rule, which was never sent.

## The limit no ruleset fixes

`bypass_actors` is empty, so the ruleset binds the maintainer: a red required
check cannot be overridden without editing the ruleset, which is the point.

Required approvals are zero and `require_code_owner_review` is off. Those were
both set the other way while the file was an intention, and applying it that
way would have blocked every merge: `.github/CODEOWNERS` names one person, and
GitHub does not count a self-approval, so a repository with one maintainer can
never satisfy a one-approval rule. Zero approvals still requires a pull
request, still forbids a direct push to `main`, and still requires review
threads to be resolved. What it cannot do is manufacture a second reviewer.
Self-review remains a structural limitation rather than something the ruleset
fixes, and `CODEOWNERS` is ready for a second person. See phase 4 of
[`../MULTIYEAR-PLAN.md`](../MULTIYEAR-PLAN.md).
