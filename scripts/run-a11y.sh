#!/usr/bin/env bash
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
