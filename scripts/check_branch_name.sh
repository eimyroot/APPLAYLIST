#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-}"

if [[ ! "$BRANCH" =~ ^feature/bundle-[0-9]+- ]]; then
  echo "❌ Invalid branch naming"
  exit 1
fi

echo "✅ Branch name OK"
