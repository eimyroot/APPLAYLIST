# APPLAYLIST — Provider Analysis Rollout Runbook

## Working Directory

cd /Users/eimyna/Documents/0_DEV/APPLAYLIST!

## Verify Provider Hardening

scripts/verify_provider_hardening.sh

## Verify Rollout Readiness

scripts/verify_provider_rollout_readiness.sh

## Run Full Tests

.venv/bin/python -m pytest -q

## Enable Provider Path Locally

APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=1

## Disable Provider Path

APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=0

or unset the variable.

## Safety Rule

Do not change API defaults until routed analysis service is verified in local tests.

## Expected Default

Without environment variable:

provider_analysis_mode({}) == legacy

## Expected Provider Mode

With:

APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=1

mode should be:

provider

## Rollback Command

unset APPLAYLIST_PROVIDER_ANALYSIS_ENABLED

or:

export APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=0
