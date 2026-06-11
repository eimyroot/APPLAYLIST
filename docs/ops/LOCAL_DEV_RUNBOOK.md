# APPLAYLIST — Local Development Runbook

## Working Directory

cd '/Users/eimyna/Documents/0_DEV/APPLAYLIST!'

## Correct Test Command

.venv/bin/python -m pytest -q

Expected current baseline:

54 passed

## Recreate Local Environment

cd '/Users/eimyna/Documents/0_DEV/APPLAYLIST!' && \
rm -rf .venv && \
python3.11 -m venv .venv && \
.venv/bin/python -m pip install --upgrade pip setuptools wheel && \
.venv/bin/python -m pip install -e ".[dev]" -c constraints/audio-stack-py311.txt

## Never Commit

- .env
- .env.*
- .venv/
- *.db
- *.sqlite
- *.sqlite3
- .local_backups/
- __pycache__/
- .pytest_cache/
- .DS_Store
- * 2.py

## Pre-Commit Check

cd '/Users/eimyna/Documents/0_DEV/APPLAYLIST!' && \
.venv/bin/python -m pytest -q && \
git status --short
