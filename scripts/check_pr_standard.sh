#!/usr/bin/env bash
set -euo pipefail

TITLE="${PR_TITLE:-}"
BODY="${PR_BODY:-}"

echo "Checking PR title..."
if [[ ! "$TITLE" =~ ^Bundle[[:space:]][0-9]+: ]]; then
  echo "❌ Invalid PR title format"
  exit 1
fi

echo "Checking required sections..."
echo "$BODY" | grep -q "## Summary" || { echo "❌ Missing Summary"; exit 1; }
echo "$BODY" | grep -q "## Verification" || { echo "❌ Missing Verification"; exit 1; }
echo "$BODY" | grep -q "## Bundle Context" || { echo "❌ Missing Bundle Context"; exit 1; }

echo "✅ PR format OK"
