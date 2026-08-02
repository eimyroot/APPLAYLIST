---
id: OPS-BACKUP-RESTORE-RUNBOOK
title: APPLAYLIST Backup and Restore Runbook
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - LOCAL_GATE_RUNBOOK.md
  - ../../STATUS.md
---

# APPLAYLIST — Backup and Restore Runbook

## Create a verified local bundle

```bash
make bundle
```

The target requires a clean worktree, runs `git fsck --full --strict`, creates a Git bundle under
the ignored `artifacts/` directory and verifies the bundle before reporting success.

## Restore smoke

`make verify` includes `scripts/restore_smoke.sh`.

The smoke test:

1. requires a clean source worktree,
2. creates a temporary bundle of the current commit,
3. clones it into a temporary directory,
4. runs `git fsck --full --strict`,
5. resolves the restored commit by a verified ref,
6. checks out the exact commit detached,
7. requires a clean restored worktree,
8. removes only its own temporary directory.

## Disaster recovery

For an actual recovery, preserve the damaged repository before replacing anything. Restore into a
new directory, verify bundle SHA/evidence, run `git fsck`, compare the expected commit, and only
then decide whether to promote the restored repository.

Do not overwrite the canonical repository in place as a first recovery action.
