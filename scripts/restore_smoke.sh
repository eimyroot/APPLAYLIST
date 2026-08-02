#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

[ -z "$(git status --porcelain)" ] || {
  printf 'BLOCKED=RESTORE_SMOKE_REQUIRES_CLEAN_WORKTREE\n' >&2
  exit 20
}

HEAD_SHA="$(git rev-parse HEAD)"
BRANCH="$(git branch --show-current)"
TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/applaylist-restore.XXXXXX")"
cleanup() {
  case "$TMPROOT" in
    "${TMPDIR:-/tmp}"/applaylist-restore.*) rm -rf -- "$TMPROOT" ;;
    *) printf 'BLOCKED=UNSAFE_RESTORE_TMP_PATH path=%s\n' "$TMPROOT" >&2 ;;
  esac
}
trap cleanup EXIT

BUNDLE="$TMPROOT/repository.bundle"
RESTORE="$TMPROOT/restored"

git bundle create "$BUNDLE" HEAD
git bundle verify "$BUNDLE" >"$TMPROOT/bundle-verify.txt" 2>&1
git clone --no-checkout "$BUNDLE" "$RESTORE" >/dev/null 2>&1

(
  cd "$RESTORE"
  git fsck --full --strict >/dev/null 2>&1

  CANDIDATE=""
  SHA=""
  if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
    CANDIDATE="refs/remotes/origin/$BRANCH"
    SHA="$(git show-ref --verify --hash "$CANDIDATE")"
  elif git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    CANDIDATE="refs/heads/$BRANCH"
    SHA="$(git show-ref --verify --hash "$CANDIDATE")"
  else
    CANDIDATE="$(git for-each-ref --format='%(refname)' refs/remotes/origin refs/heads \
      | head -1)"
    if [ -n "$CANDIDATE" ]; then
      SHA="$(git show-ref --verify --hash "$CANDIDATE")"
    elif git rev-parse --verify 'HEAD^{commit}' >/dev/null 2>&1; then
      CANDIDATE="HEAD"
      SHA="$(git rev-parse --verify 'HEAD^{commit}')"
    fi
  fi

  [ -n "$CANDIDATE" ] || exit 21
  [ -n "$SHA" ] || exit 21
  [ "$SHA" = "$HEAD_SHA" ] || exit 22

  git -c advice.detachedHead=false checkout --detach "$SHA" >/dev/null 2>&1
  [ "$(git rev-parse --verify 'HEAD^{commit}')" = "$HEAD_SHA" ] || exit 23
  [ -z "$(git status --porcelain)" ] || exit 24
)

printf 'BACKUP_RESTORE_TEST=PASS\n'
printf 'RESTORED_HEAD=%s\n' "$HEAD_SHA"
