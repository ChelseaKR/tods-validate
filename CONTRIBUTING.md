# Contributing

Thanks for considering a contribution. `tods-validate` aims to be a validator
the TODS working group and everyday transit schedulers can rely on, so
correctness, clear findings, and honest spec citations matter more than feature
count.

## Setup

Requires Python 3.11 or newer.

```sh
git clone https://github.com/ChelseaKR/tods-validate
cd tods-validate
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## The local gate

Before opening a PR, run the same checks CI enforces. If they pass locally they
should pass in CI:

```sh
ruff check src tests scripts            # lint
ruff format --check src tests scripts   # formatting
mypy                                    # strict type-check on src/
pytest --cov --cov-report=term-missing --cov-fail-under=90   # tests, 90% floor
python scripts/generate_rules_doc.py --check                 # docs/rules.md is in sync
```

`pre-commit` runs ruff, ruff-format, and mypy on staged files, so most of this
is caught before you commit. Coverage is a merge-blocking floor at 90%, and the
docs-drift check fails CI if `docs/rules.md` no longer matches the rule
registry.

## Rules and fixtures

This is a TODS validator, so most changes are rules. A rule has a stable ID
(`TODS-E203`, `TODS-W206`, `TODS-I108`; `E`/`W`/`I` for error, warning, info), a
severity, a spec citation, and a check function that yields `Finding` objects
carrying the file, row, field, message, and where relevant a suggested fix.

- **Every rule ships a passing and a failing fixture.** Add a minimal feed under
  `tests/fixtures/` that triggers the rule and one that does not, and a test in
  the matching `tests/test_*.py` module. See
  [docs/authoring-rules.md](docs/authoring-rules.md) for severity choice, ID
  allocation, message style, and the fixture and conformance contract.
- **Findings are the product.** A message says what is wrong, where, and what
  good looks like, in language a scheduler can act on, and cites the spec
  section it comes from. Prefer "run_events.txt row 4: end_time is '9:45', which
  is not a valid time. Use HH:MM:SS." over "invalid value in run_events".
- **Rule IDs are stable.** Downstream pipelines filter and suppress by ID, so do
  not renumber an existing rule. Allocate the next free ID in its band.
- **Regenerate the catalog.** After adding or changing a rule, run
  `python scripts/generate_rules_doc.py` and commit the updated
  `docs/rules.md`; CI fails if it drifts.
- **Do not invent spec details.** File names, field names, required or optional
  status, and enum values come from the current TODS spec, not from memory or
  analogy to GTFS. If the spec is ambiguous, implement the permissive reading
  and add a `docs/spec-questions.md` entry rather than guessing.

## House rules

- **No network at runtime.** Validation, merge, stats, and anonymize never make
  network requests; references resolve only against the local companion GTFS
  feed. Keep it that way (see [SECURITY.md](SECURITY.md)).
- **Runtime dependencies stay minimal.** The core depends only on `click`.
  Heavier libraries belong behind an optional extra (the LSP server lives under
  the `lsp` extra), not in the default install path.
- **No real agency data.** Fixtures are hand-built and synthetic. Do not add a
  real feed, a real employee roster, or real vehicle identifiers to the repo or
  to an issue.
- **Honesty in claims.** The `anonymize` command pseudonymizes; it does not
  guarantee anonymity, and the docs say so. Keep claims to what the code does.

## Pull requests

- Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `ci:`,
  `chore:`). PR titles follow the same convention.
- Keep PRs small and reviewable, even when working solo.
- Update `CHANGELOG.md` when behavior changes, and regenerate `docs/rules.md`
  when a rule changes.
- Sign off your commits with the Developer Certificate of Origin
  ([developercertificate.org](https://developercertificate.org/)):

  ```sh
  git commit -s -m "feat: add TODS-W411 for ..."
  ```

  `-s` appends the `Signed-off-by:` trailer. By signing off you certify you
  wrote the contribution or have the right to submit it under the project's
  Apache-2.0 license.

## Reporting a security issue

See [SECURITY.md](SECURITY.md). Please report vulnerabilities through a private
GitHub security advisory rather than a public issue.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating you agree to uphold it.
