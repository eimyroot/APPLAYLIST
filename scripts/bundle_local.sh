#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT_DIR="${1:-artifacts}"
[ -z "$(git status --porcelain)" ] || {
  printf 'BLOCKED=BUNDLE_REQUIRES_CLEAN_WORKTREE\n' >&2
  exit 20
}

git fsck --full --strict >/dev/null

HEAD_SHA="$(git rev-parse HEAD)"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/applaylist-${HEAD_SHA}.bundle"
TMP="${OUT}.tmp"

test ! -e "$OUT" || {
  printf 'BLOCKED=BUNDLE_ALREADY_EXISTS path=%s\n' "$OUT" >&2
  exit 21
}

git bundle create "$TMP" HEAD
git bundle verify "$TMP" >/dev/null 2>&1
mv "$TMP" "$OUT"

printf 'BUNDLE=PASS\n'
printf 'BUNDLE_PATH=%s\n' "$OUT"
printf 'BUNDLE_SHA256=%s\n' "$(shasum -a 256 "$OUT" | awk '{print $1}')"
