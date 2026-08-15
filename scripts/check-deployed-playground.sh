#!/usr/bin/env bash
# Fail when the deployed playground is not the page this repository publishes.
#
# The blocking WCAG gate in ci.yml and the Python tests both check web/index.html
# -- the source of the deployment. Nothing checked the deployment itself, which
# is how the live page came to sit three weeks behind at the previous release's
# rule set while every gate stayed green. This is the check for the artifact.
#
# Usage:
#   scripts/check-deployed-playground.sh [PATH_TO_EXPECTED_HTML]
#
# With no argument, the expected page is web/index.html at the most recent
# release tag: that is the version the deployment is supposed to be, so a main
# branch that has moved on since the release is not drift. Callers that have
# just deployed a specific tree (pages.yml) pass that tree's file instead.
#
# Environment:
#   PLAYGROUND_URL   the deployed page (default: the project's Pages URL)
#   ATTEMPTS         retries while Pages serves a fresh deployment (default 8)
set -euo pipefail

url="${PLAYGROUND_URL:-https://chelseakr.github.io/tods-validate/index.html}"
attempts="${ATTEMPTS:-8}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

expected="${1:-}"
if [[ -z "$expected" ]]; then
  tag="$(git describe --tags --abbrev=0)"
  echo "expected: web/index.html at $tag"
  git show "$tag:web/index.html" > "$work/expected.html"
  expected="$work/expected.html"
else
  echo "expected: $expected"
fi

pin() {
  sed -n 's/.*TODS_VALIDATE_VERSION = "\([^"]*\)".*/\1/p' "$1" | head -1
}

for attempt in $(seq 1 "$attempts"); do
  curl -fsSL --retry 3 "$url" -o "$work/live.html"
  if cmp -s "$expected" "$work/live.html"; then
    echo "$url matches the page this repository publishes (tods-validate $(pin "$expected"))"
    exit 0
  fi
  echo "attempt $attempt/$attempts: the deployed page differs; waiting for Pages"
  sleep 15
done

echo "::error::The deployed playground is not the page this repository publishes."
echo "expected pin: $(pin "$expected")"
echo "live pin:     $(pin "$work/live.html")"
diff -u "$expected" "$work/live.html" || true
echo "Publish it with the 'Deploy playground' workflow (.github/workflows/pages.yml)."
exit 1
