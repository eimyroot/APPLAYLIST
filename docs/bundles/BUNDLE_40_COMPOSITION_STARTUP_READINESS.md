# Bundle 40 — Composition Startup Readiness Gate

## Status

Implemented on `feature/bundle-40-composition-startup-readiness`. Merge requires the full Python 3.11/3.12 release gate.

## Problem

Composition authority selection was validated only when a pipeline object was first constructed. An application configured with an invalid authority or incompatible canonical observability settings could start and return `status=ok` from `/health`, then fail on its first pipeline request.

## Runtime contract

`evaluate_composition_runtime()` produces an immutable readiness snapshot containing only:

- readiness status;
- selected composition authority;
- comparison enabled state;
- receipt enabled state.

It rejects:

- an unsupported composition authority;
- composition receipts without composition comparison;
- canonical authority combined with comparison observability;
- non-boolean explicit observability values.

No secrets, paths, database records, candidate counts, or filesystem information are included.

## Application startup

`create_app()` evaluates composition readiness before constructing and serving the FastAPI application. Invalid runtime configuration therefore fails application construction instead of waiting for the first `/pipeline/run` request.

The immutable snapshot is stored at:

```text
app.state.composition_runtime_readiness
```

Tests and controlled embedding environments may inject an already validated snapshot through `create_app(composition_readiness=...)`.

## Endpoints

### `/health`

Existing liveness response remains unchanged:

```json
{
  "status": "ok",
  "app": "APPLAYLIST",
  "env": "development",
  "api_version": "0.1.0"
}
```

### `/ready`

The new readiness endpoint returns the immutable configuration snapshot:

```json
{
  "status": "ready",
  "composition_authority": "legacy",
  "composition_comparison_enabled": false,
  "composition_receipts_enabled": false
}
```

`/ready` is a safe read-only endpoint. It does not scan files, query candidate data, create schemas, run composition, or write artifacts.

## Isolation

- Legacy remains the default authority.
- No pipeline response or request schema changes.
- No database migration.
- No candidate availability assertion.
- No filesystem or exporter side effect.
- No automatic canonical fallback.

## Verification

Required gates:

- startup rejection tests for every invalid combination;
- valid legacy and canonical readiness tests;
- exact `/health` backward-compatibility assertion;
- `/ready` payload assertion;
- application-state immutability assertion;
- route wiring guard;
- Python 3.11 and 3.12 install, compile, critical Ruff and full pytest;
- PR Guard, review-thread and mergeability checks.

## Rollback

Operational rollback is `COMPOSITION_AUTHORITY=legacy`, with comparison and receipts disabled if necessary. Code rollback is a revert of the future Bundle 40 squash commit. No data rollback is required.
