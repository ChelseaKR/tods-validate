# Runbook: a credential has been exposed

Last verified: 2026-08-27
Recheck cadence: after any use, and quarterly with the incident-response
standard's own cadence.

Open an `incident` issue labelled `sev1` (public surface) or `sev2` (staged but
caught before push) **now**, before working the steps. The issue's open and
close timestamps are the recovery-time signal; a rotation nobody timestamped
cannot be measured.

Work the steps in order. Step 1 comes before the issue is even fully written.

## 1. Rotate (IR-10)

Generate the replacement credential **first**. Assume the leaked value is
compromised the instant it became public, whatever the exposure lasted. Do not
begin by assessing whether anyone saw it; that is step 3, and it does not
change what step 1 requires.

Never automate this step. A production credential rotated unattended is a
credential nobody watched rotate.

## 2. Revoke (IR-11)

Invalidate the leaked credential at its issuer, and **confirm** the revocation
rather than assuming step 1 disabled it. Target: within one hour of confirming
the exposure.

For the credentials this repository could plausibly leak:

| Credential | Revoke at | Confirm by |
| --- | --- | --- |
| A GitHub PAT or App token | `gh auth token` / Settings → Developer settings, or `gh api -X DELETE /applications/.../token` | The token no longer authenticates: `GH_TOKEN=<old> gh api /user` returns 401 |
| A PyPI API token | PyPI project settings → API tokens → revoke | The token cannot publish; a `twine upload --repository testpypi` with it is rejected |
| A VS Code Marketplace PAT | Azure DevOps → Personal access tokens → revoke | `vsce login` with it fails |
| An Open VSX token | Eclipse Foundation account → Access Tokens → revoke | `ovsx` rejects it |

Note that this repository publishes to PyPI through a **trusted publisher**, not
a stored token, so the PyPI row is about a token created by hand outside that
flow. That is the one worth checking exists before assuming it does not.

## 3. Scope the blast radius (IR-12)

Read the provider's audit log for any use of the credential between exposure
and revocation. GitHub's audit log, the PyPI project's security history, the
Marketplace publisher's activity. Record what you found **and what you could
not see**; a provider with no audit log is a finding, not a blank.

## 4. Decide on history (IR-13)

**Default: do not rewrite history.** Rewriting a published branch breaks every
clone and every fork, and does not un-publish anything already fetched.

Scrub only when either holds:

- the repository is private and confirmed to have no external clones, or
- a compliance or contractual obligation requires it.

`tods-validate` is public, so the first never holds here. Record the decision
either way in the postmortem: "did not scrub, because the repository is public
and the credential is revoked" is a complete close.

## 5. Close the entry point (IR-14)

Fix the mechanism, not the instance. Typically a missing `.gitignore` pattern,
a wildcard `git add`, or a missing pre-commit hook.

Then **verify with a red-team test**: stage the same file pattern again and
confirm gitleaks blocks it.

```sh
printf 'aws_secret_access_key = AKIAIOSFODNN7EXAMPLE\n' > /tmp/leak-test.env
cp /tmp/leak-test.env ./leak-test.env
git add leak-test.env
pre-commit run gitleaks --files leak-test.env   # must fail
git restore --staged leak-test.env && rm leak-test.env /tmp/leak-test.env
```

Commit the regression test that would have caught it. That test is the
AUTO-GATE half of this step; the runbook prose is not.

Two standing gates already close the two most common entry points, and
`scripts/check_incident_contract.py` keeps them closed:

- **IR-15**: no wildcard `git add -A`, `git add .`, or `git add --all` in any
  tracked script or workflow that runs unattended.
- **IR-16**: any scripted `git commit` in unattended automation is preceded by
  a secret scan.

## 6. Postmortem (IR-05)

File `docs/incidents/YYYY-MM-DD-<slug>.md` from
[`../incidents/TEMPLATE.md`](../incidents/TEMPLATE.md), within 7 days for SEV1
or SEV2. The incident issue is not closed until that file is committed.

Include the rotation record: which credential, revoked when, confirmed how,
and what the audit log showed.

<!-- doc-currency: sha256=3ef1654132f1 -->
