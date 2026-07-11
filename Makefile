# make verify reproduces the full merge-blocking gate set locally, byte-for-
# byte with CI (CICD-27). Run it before opening a PR; the release workflows
# re-run it at the tagged commit before anything publishes (REL-14/15).
.PHONY: verify lint format typecheck test docs-check i18n-check audit secrets

verify: lint format typecheck test docs-check i18n-check audit secrets
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
