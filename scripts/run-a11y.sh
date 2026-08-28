#!/usr/bin/env bash
# The blocking WCAG 2.1 AA gate (`make a11y`), over two pages served from a temp
# directory: this repository's web/index.html and a freshly generated HTML
# report.
#
# What this does NOT audit: the deployed playground at the project's Pages URL.
# It copies web/index.html below, which is the *source* of that deployment, not
# the deployment -- and the two can differ, which is exactly how the live page
# stayed at the previous release for three weeks with this gate green. The
# deployed artifact is audited against the same runners and standard by
# scripts/pa11y-ci-live.cjs, run from .github/workflows/pages.yml right after
# each deploy and weekly from playground-deployment.yml, with
# scripts/check-deployed-playground.sh checking the two are the same page.
set -euo pipefail

a11y_tmp="$(mktemp -d "${TMPDIR:-/tmp}/tods-a11y.XXXXXX")"
a11y_port="${A11Y_PORT:-8765}"
a11y_python="${A11Y_PYTHON_BIN:-python3}"
a11y_validator="${TODS_VALIDATE_BIN:-tods-validate}"
a11y_server_pid=""

cleanup() {
  if [[ -n "$a11y_server_pid" ]]; then
    kill "$a11y_server_pid" 2>/dev/null || true
    wait "$a11y_server_pid" 2>/dev/null || true
  fi
  rm -rf "$a11y_tmp"
}
trap cleanup EXIT

cp web/index.html "$a11y_tmp/index.html"
# The rule catalog is published by pages.yml (`path: web`) and was never
# audited: 44 pages deployed to the same site as index.html, behind the same
# accessibility claim, with no runner ever pointed at them.
mkdir -p "$a11y_tmp/rules"
cp web/rules/*.html "$a11y_tmp/rules/"
"$a11y_validator" tests/fixtures/invalid/TODS-E201 --format html \
  > "$a11y_tmp/report.html" || [[ "$?" -eq 1 ]]

"$a11y_python" -m http.server "$a11y_port" --bind 127.0.0.1 \
  --directory "$a11y_tmp" > "$a11y_tmp/server.log" 2>&1 &
a11y_server_pid="$!"

for _ in {1..30}; do
  if curl --fail --silent "http://127.0.0.1:$a11y_port/report.html" > /dev/null; then
    break
  fi
  sleep 0.2
done
curl --fail --silent "http://127.0.0.1:$a11y_port/report.html" > /dev/null

A11Y_BASE_URL="http://127.0.0.1:$a11y_port" \
  ./node_modules/.bin/pa11y-ci --config scripts/pa11y-ci.cjs
