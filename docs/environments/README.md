# Deployment environments

`main.json` is the export of the GitHub Environments this repository deploys
to, and of the deployment branch policies that decide which refs may reach
them. Committing it does not apply it; GitHub is the source of truth, and this
file is the record.

## Why this directory exists

An environment's branch policy is enforced before a job's first step. A job
whose ref does not match is refused, and the refusal renders as a failed job
with no steps and no retrievable log, which is close to unreadable if you do
not already know to look at the environment.

`github-pages` admitted the branch `main` and nothing else. `pypi-publish.yml`
reaches it through `deploy-playground`, which calls `pages.yml` during a
`release: published` run, where the ref is a tag. That stage failed on v0.10.0
and again on v0.11.0 and had never once completed, while the comment above it
described the deploy sequencing it provides as structural.

The site did not visibly fall behind, because someone dispatched `pages.yml`
by hand afterwards: its run history shows two `workflow_dispatch` runs on
2026-08-22, the day v0.10.0 shipped. `pages.yml` has no `push` trigger, so
there was no automatic fallback. Every release since the sequencing landed has
depended on a person noticing that the deploy had not happened.

`tests/test_deployment_environments.py` compares this file with the workflows
in the direction that drifts: a job that deploys somewhere its ref cannot
reach. It follows local `uses:` calls, because a reusable workflow runs at its
caller's ref rather than its own.

## Changing a policy

Apply it, then re-export.

```sh
gh api -X POST repos/ChelseaKR/tods-validate/environments/<env>/deployment-branch-policies \
  -f name='v*' -f type=tag
```

A policy list only takes effect when the environment's
`deployment_branch_policy` sets `custom_branch_policies: true`; with a null
policy every ref is admitted and the list is not consulted.

Re-export both environments together:

```sh
python3 - <<'PY' > docs/environments/main.json
import json, subprocess
out = {}
for env in ("pypi", "github-pages"):
    e = json.loads(subprocess.run(
        ["gh", "api", f"repos/ChelseaKR/tods-validate/environments/{env}"],
        capture_output=True, text=True).stdout)
    p = json.loads(subprocess.run(
        ["gh", "api",
         f"repos/ChelseaKR/tods-validate/environments/{env}/deployment-branch-policies"],
        capture_output=True, text=True).stdout)
    out[env] = {
        "deployment_branch_policy": e["deployment_branch_policy"],
        "branch_policies": sorted(
            ({"type": b["type"], "name": b["name"]} for b in p["branch_policies"]),
            key=lambda b: (b["type"], b["name"]),
        ),
        "protection_rule_types": sorted(r["type"] for r in e["protection_rules"]),
    }
print(json.dumps(out, indent=2))
PY
```

## What is deliberately absent

Neither environment carries a required-reviewer rule. On a repository with one
maintainer that stalls every release waiting for an approval only the person
who triggered it could give, which is the same unsatisfiable shape the branch
ruleset had to drop; see [`../rulesets/README.md`](../rulesets/README.md).

## The limit this shares with the ruleset

Nothing compares this file with GitHub. The test checks it against the
workflows, which is the drift that happens on its own, but a policy changed in
the UI would show up in no diff.
