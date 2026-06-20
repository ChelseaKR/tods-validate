# Getting started (for non-developers)

You do not need to be a programmer to check a TODS feed. This page covers the
zero-setup path and explains exactly what "pass" means.

## The quickest check: Docker

If you have [Docker](https://www.docker.com/) installed, you do not need Python.
From the folder that contains your feed:

```sh
docker run --rm -v "$PWD:/work:ro" ghcr.io/chelseakr/tods-validate \
  /work/tods --gtfs /work/gtfs
```

- `-v "$PWD:/work:ro"` makes your current folder available inside the container
  at `/work`, read-only.
- `/work/tods` is the folder with your TODS `.txt` files; `/work/gtfs` is your
  GTFS feed. If the GTFS files sit in the same folder as the TODS files, drop
  the `--gtfs` part.

For a quick shareable summary, add `--format html > report.html` and open the
file in a browser, or `--format markdown` to paste into an email or issue.

## What the result means

The tool prints findings and exits with a status code your CI or script can read:

| Exit code | Meaning |
|-----------|---------|
| `0` | No **errors**. The feed conforms (warnings may still be present). |
| `1` | At least one error (or, with `--fail-on warning`, at least one warning). |
| `2` | The package itself could not be read at all (wrong path, not a folder/zip). |

Severities:

- **ERROR** — the feed violates the spec; fix these. They set exit code 1.
- **WARNING** — probably a mistake, but the spec allows it. Warnings do **not**
  fail the run unless you pass `--fail-on warning`.
- **INFO** — worth knowing; no action required.

So "passing" means **zero errors** by default. If your agency has reviewed a
particular warning and decided to accept it, suppress it with
`--ignore TODS-W206` (repeatable) or record the policy in a `tods-validate.toml`
file (see the [README](../README.md)).

## Fixing findings

Every finding says what is wrong, where (file and row), and what good looks
like, and cites the spec section. When the same rule fires many times, the
report groups them and adds a hint about the likely common cause (for example, a
stale GTFS export). Start with the distinct rules listed under "By rule"; fixing
each rule's root cause usually clears its whole cluster.

## Sharing a feed safely

If you want help with a feed but it contains employee IDs or license plates,
pseudonymize it first:

```sh
tods-validate anonymize tods/ -o tods-anon/
```

This is pseudonymization, not guaranteed anonymity — see [SECURITY.md](../SECURITY.md).
