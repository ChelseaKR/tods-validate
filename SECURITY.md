# Security policy

## Supported versions

Pre-1.0, only the **latest minor release** is supported. There is no long-term
support branch; upgrade to the latest release to get a fix. This will be
revisited (a supported-versions table with more than one line) at the 1.0
stability commitment described in [docs/roadmap.md](docs/roadmap.md).

| Version | Supported |
|---|---|
| latest (0.x) | ✅ |
| older 0.x | ❌ |

## Reporting a vulnerability

Please report suspected vulnerabilities privately by opening a
[GitHub security advisory](https://github.com/ChelseaKR/tods-validate/security/advisories/new)
rather than a public issue.

**Response SLA:** acknowledgment within 3 business days of the report; a
fix or documented mitigation, then a published release, within 30 days for
high/critical severity and 90 days for medium/low, tracked from
acknowledgment. If a fix will take longer, we say so in the advisory thread
with a revised date rather than going silent.

## Threat model

`tods-validate` reads TODS and GTFS feeds, which are **untrusted input**: a CI
job may validate a feed contributed by an outside party, and the `merge` and
`anonymize` commands read archives whose contents are not controlled by the
operator. The tool is designed so that reading a malicious package cannot
exhaust resources or write outside the chosen output location.

Hardening in place:

- **No network access.** Validation, merge, stats, and anonymize never make
  network requests. References are resolved only against the local companion
  GTFS feed.
- **Zip-bomb defense.** Zip members are refused when a single member would
  decompress above `MAX_FILE_BYTES` (512 MiB), when the total decompressed size
  would exceed `MAX_TOTAL_BYTES` (2 GiB), or when the compression ratio exceeds
  `MAX_COMPRESSION_RATIO` (200:1). See `src/tods_validate/loader.py`.
- **Path-traversal defense.** Zip members with absolute paths or `..` segments
  are rejected rather than extracted; only top-level files are read.
- **No code execution.** Inputs are parsed as CSV; nothing in a feed is
  evaluated, imported, or executed.
- **Minimal dependencies.** The runtime depends only on `click`.

## Handling personal data

`employee_run_dates.txt` and `vehicles.txt` can carry person- or
vehicle-identifying values. The `anonymize` subcommand pseudonymizes
`employee_id`, `license_plate`, `vehicle_id`, and `vehicle_label` before a
feed is shared; `vehicle_label` (the painted fleet number, which otherwise
correlates 1:1 with a pseudonymized `vehicle_id` for anyone with a photo of
the bus) is covered by default. Use `--also FILE:FIELD` to pseudonymize
additional extension columns.

Pseudonymization is not a guarantee of anonymity; correlation with other
datasets may still re-identify individuals. Treat anonymized output
accordingly, and prefer a random (default) salt unless stable pseudonyms
across exports are specifically required. Every `anonymize` run also prints a
"Carried through unprotected" table naming every column, outside the
pseudonymized set, that still holds non-enum free text — treat entries there
as the residual re-identification risk in that export and review or strip
them by hand before sharing.

## Supply chain

Released artifacts (PyPI package and GHCR image) are built in CI from a tagged
commit. When pinning the GitHub Action or Docker image in your own pipeline,
pin by commit SHA or image digest rather than a moving tag.
