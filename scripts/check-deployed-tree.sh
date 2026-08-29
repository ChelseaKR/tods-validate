#!/usr/bin/env bash
# Fail when any published file is not the file this repository publishes.
#
# check-deployed-playground.sh compares one file: web/index.html. pages.yml
# uploads the whole `web` directory, which today is 46 files: the playground,
# its README, the rule index, and 44 per-rule reference pages. So 45 of the 46
# published files had nothing looking at them at all, and the one that did was
# looked at once a week.
#
# That is not a theoretical hole. On 2026-08-29 every one of the 46 differed
# from the deployment: #157 gave all 45 pages a canonical URL, a description and
# a title, and the last successful deploy was 2026-08-22, so the live rule pages
# were a week behind the repository while the version pin the boot check reads
# was identical on both sides.
#
# This walks the tracked tree instead of naming one file. Same oracle as its
# sibling, for the same reason recorded there: the default branch is the honest
# answer to "the page this repository publishes", and it is self-healing, going
# red exactly while the deployment is behind and green again on the deploy that
# fixes it.
#
# Usage:
#   scripts/check-deployed-tree.sh
#
# Environment:
#   PLAYGROUND_ORIGIN  the deployed site root (default: the project's Pages URL)
#   ATTEMPTS           retries while Pages serves a fresh deployment (default 3)
#   MINIMUM_FILES      refuse to pass on fewer published files than this
#                      (default 40; a check that compares nothing must fail)
#
# A check that fetches nothing and passes is worse than no check. Three things
# are failures here rather than a quiet OK: a comparison set below the floor, a
# fetch that does not succeed, and an origin that answers a guaranteed-missing
# path with a success, which is how a catch-all would make every matching
# comparison meaningless.
set -euo pipefail

origin="${PLAYGROUND_ORIGIN:-https://chelseakr.github.io/tods-validate}"
origin="${origin%/}"
attempts="${ATTEMPTS:-3}"
minimum="${MINIMUM_FILES:-40}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

digest() {
  shasum -a 256 "$1" | cut -c1-16
}

# Prove the origin can say no. If it answers everything with a success, then
# every file "matching" would prove nothing at all.
token="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
missing_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  "${origin}/.live-integrity-guaranteed-missing-${token}" 2>/dev/null || true)"
missing_status="${missing_status:-000}"
if [[ "$missing_status" != "404" ]]; then
  echo "::error::The origin answered a guaranteed-missing path with HTTP ${missing_status}," \
       "not 404, so a matching fetch would prove nothing." >&2
  exit 1
fi

mapfile -t published < <(git ls-files web)
count="${#published[@]}"
if (( count < minimum )); then
  echo "::error::Found ${count} published file(s) under web/, below the floor of ${minimum}." \
       "A check that compares nothing must fail, not pass." >&2
  exit 1
fi

compare_once() {
  : > "$work/mismatches.txt"
  local tracked relative status
  for tracked in "${published[@]}"; do
    relative="${tracked#web/}"
    status="$(curl -sS -L --retry 2 -o "$work/live.bin" -w '%{http_code}' \
      "${origin}/${relative}?deployed-tree-check=${token}" 2>/dev/null || true)"
    status="${status:-000}"
    if [[ "$status" != "200" ]]; then
      printf '%s: the live origin returned HTTP %s; this repository publishes %s bytes\n' \
        "$relative" "$status" "$(wc -c < "$tracked" | tr -d ' ')" >> "$work/mismatches.txt"
      continue
    fi
    if ! cmp -s "$tracked" "$work/live.bin"; then
      printf '%s: live sha256 %s (%s bytes) is not the published %s (%s bytes)\n' \
        "$relative" "$(digest "$work/live.bin")" "$(wc -c < "$work/live.bin" | tr -d ' ')" \
        "$(digest "$tracked")" "$(wc -c < "$tracked" | tr -d ' ')" >> "$work/mismatches.txt"
    fi
  done
  [[ ! -s "$work/mismatches.txt" ]]
}

for attempt in $(seq 1 "$attempts"); do
  if compare_once; then
    echo "${origin} serves exactly what this repository publishes: ${count} files."
    exit 0
  fi
  if (( attempt < attempts )); then
    echo "attempt ${attempt}/${attempts}: $(wc -l < "$work/mismatches.txt" | tr -d ' ')" \
         "file(s) differ; waiting for Pages"
    sleep 15
  fi
done

echo "::error::The deployment is not what this repository publishes." >&2
echo "$(wc -l < "$work/mismatches.txt" | tr -d ' ') of ${count} published file(s) differ:" >&2
cat "$work/mismatches.txt" >&2
echo "Publish it with the 'Deploy playground' workflow (.github/workflows/pages.yml)." >&2
exit 1
