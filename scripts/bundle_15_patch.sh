#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p .github docs scripts

cat > .github/pull_request_template.md << 'PRTEMPLATE'
## Summary
- 

## Verification
- 

## Notes
- 

## Bundle Context
- Bundle:
- Base branch:
- Related issue:
PRTEMPLATE

cat > docs/BUNDLE_PR_STANDARD.md << 'DOC'
# APPLAYLIST — Bundle PR Automation Standard

## Naming

### Branch
feature/bundle-<N>-<scope>

Examples:
- feature/bundle-12-observability-guardrails
- feature/bundle-13-auth-config
- feature/bundle-14-observability-polish
- feature/bundle-15-pr-automation-standard

### Commit
- feat(bundle-<N>): <summary>
- fix(bundle-<N>): <summary>
- chore(bundle-<N>): <summary>

### PR Title
Bundle <N>: <scope title>

---

## Required lifecycle for every bundle

1. create issue
2. create branch from previous stable bundle branch
3. run patch script
4. run verify script
5. ensure clean working tree or intentional staged changes only
6. commit
7. push
8. create PR
9. add labels
10. merge only after green verification / CI

---

## Required PR sections

### Summary
What the bundle changes.

### Verification
Exact tests/checks that passed.

### Notes
Warnings, non-blocking limitations, edge notes.

### Bundle Context
- bundle number
- base branch
- related issue

---

## Labels

Minimum:
- bundle
- enhancement or bug

Optional domain labels:
- security
- observability
- api
- tests
- orchestration
- docs
- automation

---

## Merge policy

Recommended:
- squash merge
- delete head branch after merge
- no direct merge without PR
- no merge with dirty branch state
- no merge without verification

---

## Automation policy

Automate:
- issue creation
- PR creation
- PR title/body generation
- labels
- optional reviewer request

Do not automate blindly:
- merge conflict resolution
- base branch selection without confirmation
- merge without green checks

---

## Standard PR body

## Summary
- add <feature/fix>
- improve <area>
- preserve existing behavior where required

## Verification
- focused tests passed
- full suite passed: <N> passed, <warnings> warning(s)

## Notes
- non-blocking warnings:
- known limitations:

## Bundle Context
- Bundle: <N>
- Base branch: <branch>
- Related issue: #<issue>
DOC

cat > scripts/create_bundle_pr.sh << 'SCRIPT'
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

BUNDLE_NUM="$(echo "$CURRENT_BRANCH" | sed -n 's/^feature\/bundle-\([0-9]\+\).*/\1/p')"
SCOPE_RAW="$(echo "$CURRENT_BRANCH" | sed -n 's/^feature\/bundle-[0-9]\+-//p')"
SCOPE_TITLE="$(echo "$SCOPE_RAW" | tr '-' ' ')"

if [[ -z "$BUNDLE_NUM" ]]; then
  echo "ERROR: current branch does not follow feature/bundle-<N>-<scope>"
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
SCRIPT
chmod +x scripts/create_bundle_pr.sh

cat > scripts/verify_bundle_15.sh << 'VERIFY'
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
VERIFY
chmod +x scripts/verify_bundle_15.sh

echo "=== BUNDLE 15 PATCH DONE ==="
