---
id: OPS-PROVIDER-ANALYSIS-ROLLOUT
title: APPLAYLIST Provider Analysis Rollout Runbook
status: ACCEPTED
owner: APPLAYLIST Engineering
created: 2026-07-30
updated: 2026-07-30
supersedes: null
related:
  - ../architecture/APPLAYLIST_PROVIDER_ANALYSIS_ROLLOUT.md
  - ../../STATUS.md
---

# APPLAYLIST — Provider Analysis Rollout Runbook

## Working directory

```bash
cd "/Users/eimyna/00_DEV/APPLAYLIST"
```

## Verify provider layer

```bash
scripts/verify_provider_hardening.sh
scripts/verify_provider_rollout_readiness.sh
```

## Run full tests

Use the explicitly verified local interpreter:

```bash
.venv/bin/python -m pytest -q
```

## Provider mode

The provider path must remain explicit. To enable it for an authorized local verification:

```bash
export APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=1
```

To return to the default legacy path:

```bash
unset APPLAYLIST_PROVIDER_ANALYSIS_ENABLED
```

or:

```bash
export APPLAYLIST_PROVIDER_ANALYSIS_ENABLED=0
```

## Safety rules

- do not silently change the existing API response shape;
- do not make an optional provider a mandatory startup import;
- do not treat provider failure as fake success;
- do not promote provider mode to the default without a separately verified rollout work block.
