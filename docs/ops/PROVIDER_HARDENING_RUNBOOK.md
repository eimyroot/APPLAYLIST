# APPLAYLIST — Provider Hardening Runbook

## Working Directory


## Verify Provider Layer

scripts/verify_provider_hardening.sh

## Manual Test Command

.venv/bin/python -m pytest -q

## Provider Safety Rule

Do not import optional heavy providers during API startup.

Risky imports:
- librosa
- numba
- llvmlite
- essentia

These must stay inside provider implementation paths or guarded availability checks.

## Safe Provider Flow

- select provider
- check availability
- analyze
- normalize
- validate
- persist

## Failure Rule

Never fake a successful analysis.

If provider output is incomplete, return controlled failure or normalized partial output with explicit confidence/defaults.
