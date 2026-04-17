#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-nulleimy/APPLAYLIST}"
BASE_BRANCH="${2:-}"
ISSUE_NUMBER="${3:-}"
LABELS="${4:-bundle,automation}"

CURRENT_BRANCH="$(git branch --show-current)"

if [[ -z "$CURRENT_BRANCH" ]]; then
  echo "ERROR: could not detect current branch"
  exit 1
fi

if [[ -z "$BASE_BRANCH" ]]; then
  echo "ERROR: base branch argument is required"
  echo "Usage: scripts/create_bundle_pr.sh <repo> <base_branch> <issue_number> [labels_csv]"
  exit 1
fi

case "$CURRENT_BRANCH" in
  feature/bundle-[0-9]*-*)
    ;;
  *)
    echo "ERROR: current branch does not follow feature/bundle-<N>-<scope>"
    exit 1
    ;;
esac

BUNDLE_NUM="$(printf '%s\n' "$CURRENT_BRANCH" | sed -E 's#^feature/bundle-([0-9]+)-.*#\1#')"
SCOPE_RAW="$(printf '%s\n' "$CURRENT_BRANCH" | sed -E 's#^feature/bundle-[0-9]+-(.*)$#\1#')"
SCOPE_TITLE="$(printf '%s\n' "$SCOPE_RAW" | tr '-' ' ')"

if [[ -z "$BUNDLE_NUM" || -z "$SCOPE_RAW" ]]; then
  echo "ERROR: failed to parse bundle number or scope from current branch"
  exit 1
fi

TITLE="Bundle ${BUNDLE_NUM}: ${SCOPE_TITLE}"

BODY_FILE="$(mktemp)"
cat > "$BODY_FILE" <<EOF_BODY
## Summary
- standardize PR workflow for bundle-based development
- add repository PR template
- document APPLAYLIST bundle PR policy
- add helper script for bundle PR creation

## Verification
- verify script passed
- files created and checked
- branch naming and base branch validated manually

## Notes
- helper script prepares consistent PR title/body flow
- labels can be applied after PR creation

## Bundle Context
- Bundle: ${BUNDLE_NUM}
- Base branch: ${BASE_BRANCH}
- Related issue: ${ISSUE_NUMBER:+#${ISSUE_NUMBER}}
EOF_BODY

echo "Current branch: $CURRENT_BRANCH"
echo "Repo: $REPO"
echo "Base: $BASE_BRANCH"
echo "Issue: ${ISSUE_NUMBER:-none}"
echo "Suggested labels: $LABELS"
echo
echo "Suggested title:"
echo "$TITLE"
echo
echo "Suggested body:"
cat "$BODY_FILE"
echo
echo "Next step: create PR through GitHub automation/tooling."
