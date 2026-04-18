#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== VERIFY BUNDLE 16 ==="

echo "[1] files"
test -f .github/workflows/pr-guard.yml
test -f scripts/check_pr_standard.sh
test -f scripts/check_branch_name.sh

echo "[2] branch check"
scripts/check_branch_name.sh feature/bundle-16-test

echo "[3] PR check"
PR_TITLE="Bundle 16: test"
PR_BODY="## Summary\nx\n## Verification\nx\n## Bundle Context\nx"
export PR_TITLE PR_BODY
scripts/check_pr_standard.sh

echo "=== VERIFY DONE ==="
