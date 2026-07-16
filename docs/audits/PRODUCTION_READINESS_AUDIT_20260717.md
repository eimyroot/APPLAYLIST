# APPLAYLIST — Production Readiness Audit

Date: 2026-07-17

## Executive Result

APPLAYLIST contains meaningful backend foundations through Bundle 23, but it is not yet production-ready. The immediate blocker is not missing product scope alone; it is the absence of a reliable, current release baseline.

## Verified Facts

1. The repository default branch is named `feature/bundle-0-bootstrap` while its history contains work through Bundle 23.
2. The previous README still described Bundle 0 and omitted the implemented jobs, repositories, analyzer, composer, intelligence and provider work.
3. `pyproject.toml` previously allowed Python `>=3.9`, conflicting with the accepted runtime baseline `>=3.11,<3.13` and Ruff target `py311`.
4. The repository had a PR-format guard but no general test/lint/compile CI workflow.
5. The Bundle 23 provider abstraction reports analysis results with `status="stub"`; it is not a production extractor.
6. The legacy analyzer imports `librosa` at module import time and persists results directly, so provider isolation and normalized persistence boundaries are not complete.
7. Google Drive contains multiple project snapshots. At least one snapshot includes `.git`, `.venv`, `.env`, SQLite data, caches, backups and duplicate `* 2.py` files. These snapshots must not be used as the canonical production source.

## Risk Classification

### Critical

- No trustworthy automated release gate for compile, lint and tests.
- Multiple divergent copies can cause work to be performed on an obsolete branch or contaminated snapshot.
- Provider stubs can be mistaken for completed extraction if integrated prematurely.

### High

- Optional audio dependency isolation is incomplete.
- Runtime support contract was inconsistent.
- Current API, job and persistence compatibility has not been verified across provider mode.

### Medium

- Repository metadata and documentation are stale.
- `.gitignore` accumulated duplicated rules, reducing audit clarity.
- Default branch naming obscures the actual maturity and release lineage.

## Implemented in Bundle 24

- Align Python support to `>=3.11,<3.13`.
- Add Ruff to development dependencies.
- Add CI matrix for Python 3.11 and 3.12.
- Run compile, Ruff and pytest in CI.
- Replace the stale README with current architecture and release gates.
- Normalize `.gitignore` without weakening exclusions.
- Commit accepted architecture, provider hardening and rollout documents.

## Explicitly Not Changed

- No API response contract was changed.
- No database migration was run.
- No provider was enabled by default.
- No legacy analyzer path was removed.
- No Drive file was deleted or modified.
- No production deployment was attempted.

## Target Architecture

```text
API / Job
   -> RoutedAnalysisService
      -> legacy mode (default)
      -> provider mode (feature flag)
         -> ProviderRegistry
         -> selected provider
         -> normalize
         -> validate
         -> AnalysisRecord
         -> Repository
```

Mandatory boot must only import contracts, configuration, registry metadata and baseline-safe modules. Heavy optional backends must be imported lazily inside provider execution.

## Failure Modes and Required Behavior

- Missing optional dependency -> controlled `provider_dependency_missing`.
- Requested unavailable provider -> controlled `provider_unavailable`.
- Invalid provider output -> `provider_output_invalid`, no persistence.
- Provider runtime crash -> controlled `provider_runtime_error`, structured log.
- Invalid feature flag -> legacy mode, fail closed.
- Persistence schema mismatch -> stop rollout, no silent coercion.

## Rollback

Bundle 24 is documentation, configuration and CI-only. Roll back by reverting its commits or closing the pull request before merge. No runtime data rollback is required.

## Next Highest-Value Slice

Bundle 25 should implement the fail-closed provider contract and routed analysis service without changing the default legacy path. It must include lazy optional imports, normalized output validation, explicit error codes, unit tests and boot-import tests.
