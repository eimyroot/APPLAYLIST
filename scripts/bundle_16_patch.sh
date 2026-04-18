#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p .github/workflows scripts

# ----------------------------
# PR CHECK SCRIPT
# ----------------------------
cat > scripts/check_pr_standard.sh << 'CHECK'
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
CHECK

chmod +x scripts/check_pr_standard.sh

# ----------------------------
# BRANCH NAME CHECK
# ----------------------------
cat > scripts/check_branch_name.sh << 'CHECK'
#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-}"

if [[ ! "$BRANCH" =~ ^feature/bundle-[0-9]+- ]]; then
  echo "❌ Invalid branch naming"
  exit 1
fi

echo "✅ Branch name OK"
CHECK

chmod +x scripts/check_branch_name.sh

# ----------------------------
# GITHUB ACTION
# ----------------------------
cat > .github/workflows/pr-guard.yml << 'YAML'
name: PR Guard

on:
  pull_request:
    types: [opened, edited, synchronize]

jobs:
  validate-pr:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Validate branch name
        run: |
          bash scripts/check_branch_name.sh "${{ github.head_ref }}"

      - name: Validate PR structure
        run: |
          PR_TITLE="${{ github.event.pull_request.title }}"
          PR_BODY="${{ github.event.pull_request.body }}"
          export PR_TITLE PR_BODY
          bash scripts/check_pr_standard.sh
YAML

echo "=== BUNDLE 16 PATCH DONE ==="
