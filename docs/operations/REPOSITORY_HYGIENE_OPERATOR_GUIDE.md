# APPLAYLIST Repository Hygiene Operator Guide

## Purpose

The repository hygiene tool keeps a local APPLAYLIST checkout understandable and reproducible without deleting unknown data, source code, databases, secrets or music files.

It is an operator tool, not an automatic garbage collector.

## Safety model

```text
selected Git checkout
  → resolve canonical Git root
  → inventory tracked and worktree state
  → classify only known candidate types
  → protect tracked/modified/secret/database/audio/symlink content
  → write JSON + Markdown evidence
  → dry-run by default
  → explicit quarantine --apply
  → timestamped manifest
  → optional verified restore
```

Permanent purge is deliberately not implemented.

## Schema tree

```text
RepositoryHygiene
├── audit
│   ├── Git tracked-file inventory
│   ├── dirty-worktree evidence
│   ├── bounded size calculation
│   ├── candidate classification
│   ├── report-only protections
│   └── JSON + Markdown reports
│
├── quarantine
│   ├── dry-run by default
│   ├── explicit --apply
│   ├── repository-root containment
│   ├── preserved relative paths
│   ├── timestamped payload tree
│   └── rollback manifest
│
├── restore
│   ├── dry-run by default
│   ├── repository identity validation
│   ├── destination collision prevention
│   ├── file digest validation
│   └── explicit --apply
│
└── verify
    ├── git diff --check
    ├── tracked Python syntax compilation in memory
    ├── import smoke test with bytecode disabled
    ├── tracked-quarantine invariant
    └── audit summary
```

## Protected by default

The tool never automatically quarantines:

- `.git`,
- tracked files or directories containing tracked files,
- modified tracked content,
- `.env` or `.env.*`,
- SQLite databases,
- supported audio files,
- unknown files,
- symlinks,
- anything outside the selected Git repository root,
- `.repo-hygiene` state and evidence.

## Candidate categories

Automatically eligible when untracked and unmodified:

- Python bytecode and `__pycache__`,
- pytest, Ruff, Mypy, Tox and Nox caches,
- coverage and editor temporary files,
- `.DS_Store`,
- standard build outputs,
- byte-identical untracked duplicate files such as `module 2.py` when the canonical file is tracked and the duplicate is not referenced.

Report-only unless explicitly enabled:

- `artifacts/`, `exports/`, `logs/`, `tmp/`, `data/cache/`, `data/tmp/`,
- `.venv`, `venv`, `node_modules`, `frontend/node_modules`, `frontend/dist`.

## Commands

Run from any path inside the APPLAYLIST Git checkout.

### Audit only

```bash
bash scripts/repo_hygiene.sh audit --stdout
```

Or:

```bash
make hygiene-audit
```

The command writes reports under:

```text
.repo-hygiene/reports/
```

### Quarantine plan without changes

```bash
bash scripts/repo_hygiene.sh quarantine
```

Or:

```bash
make hygiene-plan
```

### Apply safe default quarantine

Review the generated plan first, then run:

```bash
bash scripts/repo_hygiene.sh quarantine --apply
```

### Include generated runtime outputs

```bash
bash scripts/repo_hygiene.sh quarantine --include-generated
```

Apply only after reviewing the report:

```bash
bash scripts/repo_hygiene.sh quarantine --include-generated --apply
```

### Include heavy generated directories

This is intentionally a separate opt-in:

```bash
bash scripts/repo_hygiene.sh quarantine --include-generated --include-heavy
```

Use `--apply` only after verifying that the environment or frontend dependencies can be reproduced.

### Verify repository safety

```bash
make hygiene-verify
```

Verification performs syntax checks in memory and disables Python bytecode writes. It must not create source-tree `__pycache__` directories.

### Restore one quarantine

Dry-run:

```bash
bash scripts/repo_hygiene.sh restore \
  .repo-hygiene/quarantine/<timestamp>/manifest.json
```

Apply:

```bash
bash scripts/repo_hygiene.sh restore \
  .repo-hygiene/quarantine/<timestamp>/manifest.json \
  --apply
```

Restore refuses to overwrite an existing destination or restore a modified quarantined file whose recorded digest no longer matches.

## Terminal copy rule

Copy only the command text shown inside code blocks.

Never copy these terminal-output elements back as commands:

```text
user@machine project %
create mode 100644 ...
Enumerating objects: ...
remote: ...
```

They are shell prompts or command output, not executable instructions.

## Operational sequence

```text
1. make hygiene-audit
2. read Markdown report
3. make hygiene-plan
4. confirm every quarantine candidate
5. run quarantine --apply only when justified
6. make hygiene-verify
7. retain the manifest until the checkout is proven healthy
8. restore through the manifest if anything unexpected is found
```

## Out of scope

- automatic permanent deletion,
- cleaning user music libraries,
- deleting databases or secrets,
- modifying tracked historical duplicates,
- rewriting Git history,
- deleting branches,
- dependency upgrades,
- product runtime behavior.
