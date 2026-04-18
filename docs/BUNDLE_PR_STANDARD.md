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
