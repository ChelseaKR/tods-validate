# make verify runs every merge-blocking gate that can run on a laptop, with the
# same command CI runs (CICD-27). Run it before opening a PR; the release
# workflows re-run it at the tagged commit before anything publishes
# (REL-14/15). CI additionally runs what needs GitHub itself -- the composite
# action's self-test, CodeQL, Semgrep and zizmor -- so a green `make verify` is
# a necessary condition for merge, not a sufficient one.
.PHONY: verify lint format typecheck test docs-check contract-check i18n-check audit npm-audit secrets a11y citation perf-check

# Every gate `make verify` runs, in reporting order. Each one is independent:
# see the recipe below for why that matters.
VERIFY_GATES := lint format typecheck test docs-check contract-check i18n-check \
	audit npm-audit secrets a11y citation

# The gates run one after another and every one of them runs, whatever the ones
# before it did. This is deliberate. When `verify` was a prerequisite list, make
# stopped at the first failure, so a red gate silently cancelled every gate
# after it -- an unfixable dependency advisory in the npm toolchain meant the
# accessibility check had not run on any commit for weeks, and nothing said so.
# Running them all is not the same as tolerating failures: each gate prints its
# own PASS/FAIL, and `verify` exits non-zero if any of them failed, so nothing
# is muted and nothing is hidden behind something else's result.
verify:
	@status=0; failed=""; \
	for gate in $(VERIFY_GATES); do \
		printf '\n== make %s ==\n' "$$gate"; \
		if $(MAKE) --no-print-directory "$$gate"; then \
			printf '== %s: PASS ==\n' "$$gate"; \
		else \
			status=1; failed="$$failed $$gate"; \
			printf '== %s: FAIL ==\n' "$$gate"; \
		fi; \
	done; \
	if [ "$$status" -eq 0 ]; then \
		printf '\nmake verify: all gates passed.\n'; \
	else \
		printf '\nmake verify: FAILED:%s\n' "$$failed" >&2; \
	fi; \
	exit $$status

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
	python scripts/check_doc_currency.py

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

# Node dependency vulnerability audit (SEC-11). This used to be the first line
# of the `a11y` recipe, which meant a HIGH advisory anywhere in the npm
# toolchain aborted the recipe before `npm run a11y` ever started: the
# accessibility gate reported a dependency problem and never performed an
# accessibility check. It is its own gate now, and it reports its own result.
# The gate blocks on HIGH/CRITICAL exactly as `npm audit --audit-level=high`
# did; the script exists because npm cannot accept a single reviewed advisory,
# and the alternative -- raising the severity floor -- would hide every finding
# at that level. See waivers.yml.
npm-audit:
	python scripts/check_npm_audit.py

# Blocking WCAG 2.1 AA automation for the browser playground and a generated
# HTML report. npm ci must have been run first; CI and the reusable release
# verification workflow both install from package-lock.json.
a11y:
	npm run a11y

# Validates CITATION.cff against the Citation File Format 1.2.0 schema
# (DOC-08). Catches malformed citation metadata before a release ships it.
# Run via uvx so the check needs no addition to the dev dependency set;
# cffconvert is fetched ephemerally into uv's tool cache.
citation:
	uvx cffconvert --validate -i CITATION.cff

# Perf budget (QM-02): validation throughput against perf/baseline.json.
# Deliberately NOT a `verify` prerequisite: the baseline is recorded on the CI
# runner's machine class, so a laptop's number is not comparable to it. Run it
# to see the measurement locally; the merge-blocking comparison is the `perf`
# job in .github/workflows/ci.yml.
perf-check:
	python scripts/check_perf_budget.py
