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

## Python

Supported project policy: Python `>=3.11,<3.13`.

Until EPIC-002 provides a fully deterministic environment command, use an explicitly selected
virtual environment and verify its interpreter:

```bash
.venv/bin/python --version
```

Example recreation for the existing audio constraint baseline:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e ".[dev]" -c constraints/audio-stack-py311.txt
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

Do not hard-code a passing test count into this runbook. The exact count belongs in the evidence
receipt for the verified commit.

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

EPIC-002 is responsible for replacing this transitional runbook flow with the canonical
`make doctor / lint / test / verify / bundle` gate.
