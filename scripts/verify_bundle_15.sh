#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== VERIFY BUNDLE 15 ==="
echo "[1/5] branch"
git branch --show-current

echo "[2/5] status"
git status --short

echo "[3/5] required files"
test -f .github/pull_request_template.md
test -f docs/BUNDLE_PR_STANDARD.md
test -f scripts/create_bundle_pr.sh

echo "[4/5] shell syntax"
bash -n scripts/create_bundle_pr.sh
bash -n scripts/verify_bundle_15.sh

echo "[5/5] helper smoke"
scripts/create_bundle_pr.sh nulleimy/APPLAYLIST feature/bundle-14-observability-polish 4 "bundle,automation,docs" >/tmp/bundle15_pr_helper.txt
grep -q "Bundle 15:" /tmp/bundle15_pr_helper.txt
grep -q "Base branch: feature/bundle-14-observability-polish" /tmp/bundle15_pr_helper.txt

echo "=== VERIFY DONE ==="
