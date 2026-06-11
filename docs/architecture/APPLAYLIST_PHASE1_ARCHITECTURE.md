# APPLAYLIST — Phase 1 Architecture Baseline

## Status

Accepted.

## Purpose

APPLAYLIST is a DJ/audio intelligence backend for track analysis, provider-based audio extraction, playlist preparation and future product/API expansion.

## Runtime Baseline

- Python: >=3.11,<3.13
- Test command: .venv/bin/python -m pytest -q
- Audio constraints: constraints/audio-stack-py311.txt

## Architecture

- api/ = HTTP API, routes, middleware
- core/ = domain logic, provider registry, normalization
- services/ = application services and orchestration
- data/ = models, repositories, persistence
- tests/ = regression, provider and unit tests
- docs/ = architecture and ops documentation
- scripts/ = verification and maintenance scripts

## Provider Rule

Heavy audio backends must stay isolated behind providers.

Stable/default stack:

- soundfile
- numpy
- scipy

Advanced optional stack:

- librosa
- essentia
- future ML/audio backend

The API must not break just because an optional audio provider fails.

## Non-Negotiable Rules

1. Do not run tests with global Python.
2. Use .venv/bin/python.
3. Do not use Python 3.14 for this project yet.
4. Do not commit .env, .venv, .db, cache files or macOS duplicate files.
5. Do not allow * 2.py iCloud duplicates back into the codebase.
6. Every provider must be testable in isolation.
7. Provider output must be normalized before storage.
8. API routes must not contain heavy audio logic.
9. Repositories own persistence.
10. Tests must pass before every checkpoint commit.

## Current Stable Checkpoint

- 54 passed
- Python 3.11
- llvmlite 0.42.0
- numba 0.59.1
- librosa 0.10.2.post1
