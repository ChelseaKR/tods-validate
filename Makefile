# make verify runs every merge-blocking gate that can run on a laptop, with the
# same command CI runs (CICD-27). Run it before opening a PR; the release
# workflows re-run it at the tagged commit before anything publishes
# (REL-14/15). CI additionally runs what needs GitHub itself -- the composite
# action's self-test, CodeQL, Semgrep and zizmor -- so a green `make verify` is
# a necessary condition for merge, not a sufficient one.
.PHONY: verify lint format typecheck test docs-check contract-check i18n-check audit secrets a11y citation

verify: lint format typecheck test docs-check contract-check i18n-check audit secrets a11y citation
	@echo "make verify: all gates passed."

lint:
	ruff check src tests scripts

format:
	ruff format --check src tests scripts

typecheck:
	mypy

test:
	pytest --cov --cov-report=term-missing --cov-fail-under=90

docs-check:
	python scripts/generate_rules_doc.py --check

contract-check:
	python scripts/check_public_contract.py

i18n-check:
	python scripts/check_i18n.py

# Dependency vulnerability audit (CQ-11 / SEC-11). --strict also fails on any
# dependency pip-audit could not evaluate, rather than silently skipping it.
# Audits the exact pins in uv.lock (what `uv sync --frozen` installs) minus
# the project itself: during a release PR the bumped version does not exist
# on PyPI yet, so auditing the local package can only ever fail; every real
# dependency is still audited.
audit:
	req="$$(mktemp)" && \
	uv export --frozen --extra dev --no-emit-project --no-hashes --quiet \
		--format requirements-txt -o "$$req" && \
	pip-audit --strict --no-deps -r "$$req"; \
	rc=$$?; rm -f "$$req"; exit $$rc

# Secret scan over the working tree + history (SEC-17/18). Requires the
# gitleaks binary (see https://github.com/gitleaks/gitleaks#installing); the
# CI job installs it explicitly rather than via the license-gated Action.
secrets:
	gitleaks detect --source . --redact --exit-code 1

# Blocking WCAG 2.1 AA automation for the browser playground and a generated
# HTML report. npm ci must have been run first; CI and the reusable release
# verification workflow both install from package-lock.json.
a11y:
	npm audit --audit-level=high
	npm run a11y

# Validates CITATION.cff against the Citation File Format 1.2.0 schema
# (DOC-08). Catches malformed citation metadata before a release ships it.
# Run via uvx so the check needs no addition to the dev dependency set;
# cffconvert is fetched ephemerally into uv's tool cache.
citation:
	uvx cffconvert --validate -i CITATION.cff
