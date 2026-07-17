# Maintenance H1 — Repository Hygiene

## Status

Implemented on an isolated maintenance branch. Not merged until the complete release gate passes.

## Goal

Provide a safe local operator workflow for identifying and quarantining reproducible repository clutter without deleting source code, user data or unknown files.

## Scope

```text
APPLAYLIST local checkout
└── Maintenance H1
    ├── audit engine
    ├── JSON and Markdown evidence
    ├── dry-run quarantine planning
    ├── explicit quarantine apply
    ├── rollback manifest
    ├── verified restore
    ├── non-polluting verify checks
    ├── Bash 3.2 compatible wrapper
    ├── Makefile commands
    ├── regression tests
    └── operator guide
```

## Invariants

- Dry-run is the default.
- Permanent purge does not exist.
- Paths are contained inside the resolved Git root.
- `.git` and hygiene state are excluded from traversal.
- Tracked or modified content is never automatically moved.
- Audio, SQLite and environment files are protected.
- Symlinks are never followed or automatically moved.
- Runtime outputs and heavy generated directories require separate opt-in flags.
- Every applied move is represented in a timestamped rollback manifest.
- Verify mode does not write source-tree Python bytecode.

## Duplicate policy

A duplicate-style file such as `module 2.py` is quarantine eligible only when all conditions hold:

1. it is untracked,
2. the canonical filename exists,
3. the canonical file is tracked,
4. both files are byte-identical,
5. the duplicate name/path is not referenced by tracked text.

Otherwise it remains report-only.

## Verification targets

- candidate classification,
- tracked and dirty-worktree protection,
- protected audio/database/environment files,
- generated/heavy opt-in controls,
- duplicate validation,
- symlink behavior,
- dry-run semantics,
- quarantine manifest generation,
- restore collision and digest protection,
- root containment,
- non-polluting syntax/import verification,
- Python 3.11 and 3.12 CI,
- full existing product regression suite.

## Isolation

This maintenance slice changes no:

- audio analysis,
- metadata ingestion,
- database schema,
- API route,
- composition behavior,
- export behavior,
- runtime dependency,
- frontend.

## Rollback

Revert the isolated future squash commit. Local quarantines already created by an operator remain restorable through their manifests independently of the Git revert.
