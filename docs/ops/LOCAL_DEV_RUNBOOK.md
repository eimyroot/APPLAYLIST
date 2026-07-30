---
id: OPS-LOCAL-DEV-RUNBOOK
title: APPLAYLIST Local Development Runbook
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - ../../STATUS.md
  - ../../docs/decisions/ADR-0001-LOCAL-FIRST-GIT.md
---

# APPLAYLIST — Local Development Runbook

## Working directory

```bash
cd "/Users/eimyna/00_DEV/APPLAYLIST"
```

Always confirm:

```bash
pwd
git rev-parse --show-toplevel
git status --short --branch
git rev-parse HEAD
git remote -v
git log -5 --oneline
```

## Python and deterministic environment

Supported project policy: Python `>=3.11,<3.13`.

Create the canonical local environment from the committed hash-locked dependency graph:

```bash
make bootstrap PYTHON_BOOTSTRAP=python3.12
```

Then use the project-owned commands:

```bash
make doctor
make lint
make type
make test
make security
make verify
make bundle
```

The exact test count belongs in the evidence receipt for the verified commit, not in this runbook.

## Local API

Bind development traffic to loopback unless a specific work block requires another interface:

```bash
.venv/bin/python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

## Never commit

- `.env` or secret-bearing environment files;
- `.venv/`;
- local databases;
- local audio libraries;
- private benchmark data;
- cache/build output;
- synchronization-provider duplicate artifacts.

## Pre-commit minimum

```bash
git diff --check
.venv/bin/python -m pytest -q
git status --short --branch
```

See `LOCAL_GATE_RUNBOOK.md` for gate semantics and debt-baseline rules.
