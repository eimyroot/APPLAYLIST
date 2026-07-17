# Bundle 32 — Composition Shadow Comparison Service

## Goal

Measure the behavioral difference between the legacy composer and the canonical deterministic engine without changing production composition or export.

## Confirmed baseline mismatch

The pipeline request accepts BPM range and mode controls. The current orchestrator calls the legacy composer with only `limit`; BPM and mode values are retained only in the returned input section.

## Shadow boundary

`CompositionShadowService` is a read-only internal service:

1. receives the already-produced legacy track identifiers,
2. reads playlist candidates through an injected repository,
3. adapts them through the fail-closed Bundle 31 adapter,
4. runs the canonical engine with explicit target count, BPM range, genre, mode and start key,
5. returns an immutable comparison report.

It does not invoke the legacy composer, modify its output, export a playlist, write a database row or expose an API route.

## Report evidence

The report contains:

- legacy and canonical ordered track identifiers,
- canonical status and controlled failure reason,
- candidate, adapted, rejected and fallback counts,
- set overlap count,
- positional agreement count,
- legacy and canonical coverage ratios,
- adapter issues,
- canonical engine warnings.

## Failure model

- invalid request values fail during request construction,
- unsupported modes fail before repository access,
- invalid candidate features are represented by Bundle 31 issue codes,
- an empty canonical candidate set remains a controlled engine result,
- no shadow failure can alter an existing legacy playlist because this bundle does not integrate with the pipeline.

## Verification

- deterministic overlap and position metrics,
- unchanged legacy tuple evidence,
- adapter rejection and fallback propagation,
- BPM-range behavior,
- invalid mode before repository access,
- empty legacy-output ratio behavior,
- full Python 3.11 and 3.12 CI.

## Rollback

Revert the future Bundle 32 squash commit. No database, export or data rollback is required.
