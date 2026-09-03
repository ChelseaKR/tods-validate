# make verify runs every merge-blocking gate that can run on a laptop, with the
# same command CI runs (CICD-27). Run it before opening a PR; the release
# workflows re-run it at the tagged commit before anything publishes
# (REL-14/15).
#
# CI additionally runs five things this file does not, so a green `make verify`
# is a necessary condition for merge and not a sufficient one:
#
#   - the composite action's self-test, CodeQL, Semgrep and zizmor, which need
#     GitHub itself;
#   - the `perf` job, which runs `make perf-check` and `make memory-check`
#     against baselines recorded on the runner's machine class (see those
#     targets below);
#   - the VS Code extension package job, which type-checks, audits and builds
#     a VSIX out of editor/vscode. It is path-filtered to that directory, so it
#     is absent from most pull requests, which is how it stayed off this list
#     for as long as it did.
#
# This paragraph is checked against the workflows by
# tests/test_ci_gate_parity.py, so a job added later cannot reject a tree that
# `make verify` has just called green without saying so here.
.PHONY: verify lockfile lint format typecheck test docs-check contract-check i18n-check incident-check data-cards-check audit npm-audit secrets a11y citation-cff perf-check memory-check

# Run the tools this repository pins, not whichever ones the shell happens to
# find first.
#
# Every gate below named its tool bare -- `mypy`, `ruff`, `pytest`, `python` --
# so the gate ran whatever was on PATH. CONTRIBUTING.md says to
# `. .venv/bin/activate` before `make verify`, and nothing enforced it; when
# that step is missed the gates do not report a wrong environment, they report
# wrong results about the code.
#
# Measured here, with the venv present but not activated: a pipx-installed
# mypy -- the *same* 2.1.0 uv.lock pins, so neither a version drift nor a stub
# problem -- cannot see click, pygls or lsprotocol. It emits 4
# `import-not-found` errors, and then, because an unresolved `click.option` is
# Any, `strict = true`'s disallow_untyped_decorators fires on every decorated
# command: "Found 96 errors in 2 files", all in src/tods_validate/cli.py and
# src/tods_validate/lsp.py, on a commit whose CI run was green. Handing that
# same binary the project interpreter (`--python-executable .venv/bin/python`)
# prints "Success: no issues found in 51 source files". The 89
# untyped-decorator lines are a rendering of the 4 unresolved imports, and
# reading them as a fault in the code has already cost one debugging session
# that concluded "click stub drift" and went looking for something to silence.
#
# CI never saw it because every job running a Python gate prepends
# `$PWD/.venv/bin` to $GITHUB_PATH by hand first -- the local/CI divergence the
# header above promises does not exist. Resolving the tools here closes it at
# the source rather than in each caller's shell.
#
# Explicit paths rather than an exported PATH, because `export PATH` does not
# reach a recipe like `typecheck`'s. A recipe line with no shell metacharacters
# is exec'd directly instead of through /bin/sh, and that path search does not
# honour make's exported value (GNU Make 3.81, which is what macOS ships): with
# `export PATH := $(CURDIR)/.venv/bin:$(PATH)` in force, `mypy` still found the
# pipx build and still printed 96 errors, while `mypy; :` -- the same command
# with a metacharacter, so run through the shell -- printed Success. A fix that
# depends on whether a recipe happens to contain a semicolon is not a fix.
#
# TOOL is empty when there is no .venv, so the CI jobs that install with
# `pip install .` into a setup-python interpreter keep resolving exactly as
# before; it is gitignored, so those checkouts never have one.
#
# Not a silencing fix: no mypy setting is relaxed, no module is exempted from
# disallow_untyped_decorators, and no `# type: ignore` is added. The gate stays
# able to fail. It is only made to check the code against the dependency set
# uv.lock actually describes.
VENV_BIN := $(CURDIR)/.venv/bin
TOOL := $(if $(wildcard $(VENV_BIN)/python),$(VENV_BIN)/,)

PYTHON := $(TOOL)python
MYPY := $(TOOL)mypy
RUFF := $(TOOL)ruff
PYTEST := $(TOOL)pytest
PIP_AUDIT := $(TOOL)pip-audit
TODS_VALIDATE := $(TOOL)tods-validate

# Every gate `make verify` runs, in reporting order. Each one is independent:
# see the recipe below for why that matters.
VERIFY_GATES := lockfile action-lock lint format typecheck test docs-check contract-check \
	i18n-check incident-check data-cards-check audit npm-audit secrets a11y citation-cff

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

# CQ-09's drift half. The standard asks for a "lockfile-drift check + frozen
# install"; this repo only had the second half. `uv sync --frozen` installs
# exactly what uv.lock says and exits 0 whether or not the lock still agrees
# with pyproject.toml, so a bumped version (or an added dependency) shipped a
# stale environment and every CI job stayed green -- measured, not assumed:
# with pyproject at 0.9.0 and uv.lock still at 0.8.0, `uv sync --frozen
# --group dev` exits 0 and installs 0.8.0, while `uv lock --check` exits 1.
# ADR 0005 claimed --frozen "fails on any lockfile drift"; it does not, and the
# ADR now records the correction. Runs first in VERIFY_GATES and as its own
# step before every `uv sync` in CI, because a check after the install is a
# check of the wrong thing.
lockfile:
	uv lock --check

# requirements-action.lock is the hash-pinned runtime set action.yml installs
# with `pip install --require-hashes --only-binary=:all:`. It used to be
# maintained by hand, with a comment telling the next person to run
# `pip download` and `pip hash`, and nothing compared it to anything. On
# 2026-08-29 it pinned click==8.1.8 while uv.lock, requirements-dev.lock and
# every CI job resolved click==8.4.2: the published composite action had been
# installing a different click from the one this project tests against, and no
# gate could say so.
#
# It is generated now, by the command its own header records, and this gate
# regenerates it into a temporary file and diffs. The command reads uv.lock and
# needs no index, so the gate is offline. The `; sys_platform == 'win32'` line
# for colorama is uv's, not an error: pip evaluates the marker and skips the
# line on the Linux runner the action uses, verified against pip's real
# --require-hashes path rather than assumed.
#
# Regenerate with the command in the file's header, redirecting to the file:
#   uv export --frozen --no-dev --no-emit-project --format requirements-txt \
#     > requirements-action.lock
ACTION_LOCK_EXPORT := uv export --frozen --no-dev --no-emit-project --format requirements-txt

action-lock:
	@out="$$(mktemp)" && \
	$(ACTION_LOCK_EXPORT) > "$$out" && \
	if diff -u requirements-action.lock "$$out"; then \
		rm -f "$$out"; \
		echo "requirements-action.lock is what uv.lock exports"; \
	else \
		rm -f "$$out"; \
		echo "requirements-action.lock has drifted from uv.lock. Regenerate it:" >&2; \
		echo "  $(ACTION_LOCK_EXPORT) > requirements-action.lock" >&2; \
		exit 1; \
	fi

lint:
	$(RUFF) check src tests scripts

format:
	$(RUFF) format --check src tests scripts

typecheck:
	$(MYPY)

test:
	$(PYTEST) --cov --cov-report=term-missing --cov-fail-under=90

# Two independent drift checks, and both of them run.
#
# These were two recipe lines. make aborts a recipe at its first failing line,
# so a stale docs/rules.md meant check_doc_currency.py did not run at all: the
# gate reported a generated-doc problem and never performed a currency check.
# That is the same failure the `a11y` and `npm-audit` comments below describe,
# one level down. `verify` isolates gates from each other; nothing was
# isolating the checks inside one gate. Each reports its own result now, and
# docs-check exits non-zero if either failed.
docs-check:
	@status=0; \
	printf '%s\n' '' 'docs check 1 of 2: generated docs match the rule registry'; \
	if $(PYTHON) scripts/generate_rules_doc.py --check; then \
		printf '%s\n' 'generated docs: PASS'; \
	else \
		status=1; printf '%s\n' 'generated docs: FAIL'; \
	fi; \
	printf '%s\n' '' 'docs check 2 of 2: stamped pages are current'; \
	if $(PYTHON) scripts/check_doc_currency.py; then \
		printf '%s\n' 'doc currency: PASS'; \
	else \
		status=1; printf '%s\n' 'doc currency: FAIL'; \
	fi; \
	exit $$status

contract-check:
	$(PYTHON) scripts/check_public_contract.py

# The one gate that keeps a bare `python`. ci.yml's `i18n` job runs this
# recipe's command directly instead of calling the target, and
# tests/test_ci_gate_parity.py compares the two as text so they cannot
# silently drift apart; `$(PYTHON)` here would fail that comparison against
# the job's literal `python scripts/check_i18n.py`. That job installs with
# `pip install .` into a setup-python interpreter and has no .venv, where
# `$(PYTHON)` expands to bare `python` anyway, so this costs nothing there.
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
	uv export --frozen --group dev --no-emit-project --no-hashes --quiet \
		--format requirements-txt -o "$$req" && \
	$(PIP_AUDIT) --strict --no-deps -r "$$req"; \
	rc=$$?; rm -f "$$req"; exit $$rc

# Secret scan over the working tree + history (SEC-17/18). Requires the
# gitleaks binary (see https://github.com/gitleaks/gitleaks#installing); the
# CI job installs it explicitly rather than via the license-gated Action.
#
# Two scans, because one of them cannot see what the other is for. `gitleaks
# detect --source .` walks commits: it answers "was a secret ever committed",
# and it is blind to a file that exists on disk and has not been committed
# yet. That is the state every working tree is in while a gate runs against
# it. Measured on this repository at v0.10.0: a file at the repository root
# holding an AWS key pair, a GitHub PAT and a Slack bot token, saved and never
# added to the index, gave "283 commits scanned / no leaks found" and exit 0
# from the history scan, and "leaks found: 1" and exit 1 from --no-git. The
# comment above this recipe had said "working tree + history" since the gate
# was written; only the history half existed.
#
# Both run, whatever the other one did, and each reports its own result -- the
# same reason `verify` does not stop at its first failure. `.gitleaks.toml`
# scopes the working-tree scan away from installed dependencies; see that file.
secrets:
	@status=0; \
	printf '%s\n' '' 'gitleaks scan 1 of 2: committed history'; \
	if gitleaks detect --source . --redact --exit-code 1; then \
		printf '%s\n' 'gitleaks history: PASS'; \
	else \
		status=1; printf '%s\n' 'gitleaks history: FAIL'; \
	fi; \
	printf '%s\n' '' 'gitleaks scan 2 of 2: working tree, uncommitted files included'; \
	if gitleaks detect --no-git --source . --redact --exit-code 1; then \
		printf '%s\n' 'gitleaks working tree: PASS'; \
	else \
		status=1; printf '%s\n' 'gitleaks working tree: FAIL'; \
	fi; \
	exit $$status

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
	$(PYTHON) scripts/check_npm_audit.py

# Blocking WCAG 2.1 AA automation for the browser playground and a generated
# HTML report. npm ci must have been run first; CI and the reusable release
# verification workflow both install from package-lock.json.
# scripts/run-a11y.sh generates the report it audits by running the built
# CLI, which is the console script this project installs into .venv/bin --
# so the gate needed the venv on PATH for the same reason `typecheck` did,
# and failed with `tods-validate: command not found` without it. The script
# already takes TODS_VALIDATE_BIN; this hands it the same resolved path the
# other gates use, and passes the script's own default through unchanged
# when there is no .venv.
a11y:
	TODS_VALIDATE_BIN=$(TODS_VALIDATE) npm run a11y

# Validates CITATION.cff against the Citation File Format 1.2.0 schema
# (DOC-08). Catches malformed citation metadata before a release ships it.
# Run via uvx so the check needs no addition to the dev dependency set;
# cffconvert is fetched ephemerally into uv's tool cache.
#
# Named for the file, not for the word. It was called `citation` until 2026-08-29,
# which in a repository whose premise is cited findings read as a claim that the
# spec citations findings carry had been checked. They had not, by this target or
# any other under this name. Those citations are checked elsewhere:
# tests/test_registry.py asserts every rule's spec_section is a URL under the TODS
# specification, and `make docs-check` regenerates docs/rules.md from the registry
# and fails on any drift.
citation-cff:
	uvx cffconvert --validate -i CITATION.cff

# Perf budget (QM-02): validation throughput against perf/baseline.json.
# Deliberately NOT a `verify` prerequisite: the baseline is recorded on the CI
# runner's machine class, so a laptop's number is not comparable to it. Run it
# to see the measurement locally; the merge-blocking comparison is the `perf`
# job in .github/workflows/ci.yml.
# The incident-response contract as a gate rather than a document (IR-05/07/
# 15/16/17), and the data-card presence check DG-01 marks AUTO-GATE. Both are
# in VERIFY_GATES rather than in a workflow of their own because the
# portfolio's definition of AUTO-GATE is merge-blocking, with no `|| true`.
incident-check:
	$(PYTHON) scripts/check_incident_contract.py

data-cards-check:
	$(PYTHON) scripts/check_data_cards.py

perf-check:
	$(PYTHON) scripts/check_perf_budget.py

# The other half of the scale budget (FIX-04). Kept out of VERIFY_GATES for the
# same reason perf-check is: it measures rather than inspects, so it belongs in
# the `perf` CI job next to the throughput gate, not in the pre-commit loop.
# tests/test_memory_budget.py runs the comparison logic and one real
# measurement inside `make test`, so the budget is not only checked in CI.
memory-check:
	$(PYTHON) scripts/check_memory_budget.py
