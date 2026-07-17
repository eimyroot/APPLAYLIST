# APPLAYLIST — Production Readiness Audit

Date: 2026-07-17

## Executive Result

Bundle 24 establishes a reproducible and verified development baseline for APPLAYLIST. The repository now installs, compiles, passes its critical lint gate and passes all 52 tests on Python 3.11 and 3.12.

This does **not** mean the complete product is production-ready. Provider execution is still a stub, optional audio backend isolation is incomplete, deployment readiness has not been proven and the user-facing product surface is unfinished.

## Canonical Source of Truth

The canonical source is the GitHub repository `nulleimy/APPLAYLIST`.

Google Drive copies are historical snapshots or donor material. At least one Drive snapshot contains `.git`, `.venv`, `.env`, SQLite data, caches, backups and duplicate `* 2.py` files. It must not be merged back as a complete working tree.

## Verified Baseline

- Branch: `feature/bundle-24-production-baseline`
- Verification lineage: commits through the Bundle 24 final CI gate
- Supported Python: `>=3.11,<3.13`
- Python 3.11: 52 passed, 0 failed, 0 errors
- Python 3.12: 52 passed, 0 failed, 0 errors
- Compile gate: passed on Python 3.11 and 3.12
- Critical Ruff gate `E9,F63,F7,F82`: passed on Python 3.11 and 3.12
- PR Guard: passed
- CI evidence: JUnit XML and full pytest logs retained for 14 days

## Implemented in Bundle 24

### Runtime and repository contract

- Align Python support to `>=3.11,<3.13`.
- Add Ruff to development dependencies.
- Replace stale Bundle 0 documentation with the current architecture and release gates.
- Normalize `.gitignore` without weakening exclusions.

### CI and supply-chain safety

- Add Python 3.11 and 3.12 CI matrix.
- Add deterministic install, compile, critical lint and pytest gates.
- Persist JUnit and pytest logs as workflow artifacts.
- Remove direct interpolation of untrusted PR metadata into shell commands.
- Restrict PR Guard token permissions to read-only repository contents.

### Application initialization

- Introduce `create_app()` while preserving `app = create_app()` for Uvicorn compatibility.
- Inject immutable security settings explicitly into middleware and bootstrap code.
- Replace reload-based security tests with isolated application instances.
- Create fresh health, jobs and pipeline routers per application instance.
- Validate route wiring through the public OpenAPI contract rather than FastAPI internal route storage.

## Root Cause Closed During Verification

The previous route-wiring test inspected `app.routes` directly. The installed FastAPI version represents included routers lazily as internal `_IncludedRouter` objects whose `path` is `None`. Runtime endpoint tests remained functional, but the test incorrectly treated this internal representation as missing routes.

The guard now verifies `app.openapi()["paths"]`, which is the stable public API contract relevant to clients and backward compatibility.

## Explicitly Not Changed

- No public endpoint path or response contract was intentionally changed.
- No database migration was run.
- No provider was enabled by default.
- No legacy analyzer path was removed.
- No Drive file was deleted or modified.
- No production deployment was attempted.
- No pull request was merged as part of this verification record.

## Remaining Risks

### Critical before provider rollout

- Bundle 23 providers still return `status="stub"` rather than canonical analysis output.
- Provider output normalization and deny-by-default persistence validation are not implemented.

### High

- The legacy analyzer imports `librosa` on its execution path and persists results directly.
- Optional backend isolation and controlled dependency errors are incomplete.
- The default branch name still describes Bundle 0 rather than current product maturity.
- Deployment, backup, restore and production smoke tests are not verified.

### Warnings observed in CI

- Starlette reports that `httpx` with `starlette.testclient` is deprecated in favor of `httpx2`.
- `aifc`, `audioop` and `sunau` warnings affect future Python 3.13 compatibility through the audio dependency chain.
- The short generated audio fixture triggers a non-fatal `librosa` `n_fft` warning.

These warnings are non-blocking for the accepted Python 3.11–3.12 baseline but must be tracked before expanding runtime support.

## Rollback

Bundle 24 changes application initialization, tests, CI, documentation and configuration, but does not migrate persisted data.

Before merge, rollback is closing the pull request or deleting the feature branch. After merge, rollback is a revert of the squash merge commit followed by the same Python 3.11/3.12 CI matrix. No database rollback is required.

## Next Highest-Value Slice

Bundle 25 should implement a fail-closed provider result contract and routed analysis service while keeping the legacy path as the default.

Required order:

1. canonical provider result model,
2. explicit provider error taxonomy,
3. lazy backend loading,
4. normalization and validation before persistence,
5. feature-flagged routed analysis service,
6. parity and failure-mode tests,
7. boot-import and rollback verification.
