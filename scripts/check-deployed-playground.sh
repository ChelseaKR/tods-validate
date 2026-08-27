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
# The expected page defaults to web/index.html in the checkout. Callers that
# have just deployed a specific tree (pages.yml) pass that tree's file
# explicitly; the weekly check in playground-deployment.yml checks out the
# default branch and takes the default.
#
# This used to default to web/index.html at the most recent release tag, on the
# reasoning that "a main branch that has moved on since the release is not
# drift". That oracle was wrong twice over, and it turned the weekly check red
# on 2026-08-24 against a deployment that was correct:
#
#   * It is not what gets deployed. pages.yml publishes the tag's tree on the
#     release path, but workflow_dispatch -- the documented route for
#     out-of-band playground fixes -- publishes the default branch. A
#     single-ref oracle cannot describe both.
#   * A tag is immutable, so once one ships a stale page the check can never go
#     green again. v0.10.0 tagged a web/index.html still pinned to 0.9.0; the
#     repin landed on the default branch afterwards (#142) and was dispatched
#     live. The deployment was right and the expectation was stale, so the
#     check failed the artifact it was supposed to defend.
#
# The default branch is the honest answer to "the page this repository
# publishes", and it is self-healing: it goes red exactly while the deployed
# page is behind what the repository publishes, and green again on the deploy
# that fixes it -- which is the condition this check was written for in the
# first place ("sat at v0.7.0 for three weeks after web/index.html moved to
# v0.8.0"). This is not a pull-request gate, so an unmerged PR editing the page
# never trips it.
#
# Environment:
#   PLAYGROUND_URL   the deployed page (default: the project's Pages URL)
#   ATTEMPTS         retries while Pages serves a fresh deployment (default 8)
set -euo pipefail

url="${PLAYGROUND_URL:-https://chelseakr.github.io/tods-validate/index.html}"
attempts="${ATTEMPTS:-8}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

expected="${1:-web/index.html}"
if [[ ! -f "$expected" ]]; then
  echo "::error::expected page not found: $expected" >&2
  exit 1
fi
echo "expected: $expected"

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
