# Bundle 39 — Canonical Source-Path Scope

## Status

Implemented on `feature/bundle-39-canonical-source-path-scope`. Production rollout requires a green pull-request gate and squash merge.

## Problem

The pipeline request already contains a `path`, but canonical composition previously ignored it and loaded every joined playlist candidate from the indexed library. In canonical authority mode, a request for one folder could therefore export tracks from unrelated folders.

## Contract

`CanonicalCompositionExecutionRequest` now accepts an optional `source_path`.

When `source_path` is set:

- it must be a non-empty absolute path;
- normalization occurs before repository access;
- only a candidate whose path exactly equals the scope or is a lexical descendant is retained;
- filtering occurs before candidate adaptation;
- out-of-scope malformed candidates do not contribute rejection or fallback evidence;
- an empty scoped candidate set produces a failed composition and no export.

When `source_path` is omitted, existing whole-library runner behavior remains unchanged for comparison and internal callers.

## Pipeline behavior

`CanonicalCompositionAuthority` passes `PipelineCompositionCommand.path` to the canonical execution request.

Legacy authority behavior is unchanged. There is no filesystem scan, ingestion, database migration, API field, response field, or fallback to whole-library canonical selection.

## Security and correctness properties

- Relative and empty source paths are rejected before repository access.
- Candidate matching is path-component aware, so `/music/set-two` is not considered a descendant of `/music/set`.
- No filesystem resolution or unbounded traversal is performed.
- Canonical export remains fail-closed when the selected scope has no exportable tracks.
- Export postconditions from Bundle 36 remain mandatory.

## Verification

Required gates:

- Python 3.11 install, compile, critical Ruff, and full pytest;
- Python 3.12 install, compile, critical Ruff, and full pytest;
- real SQLite repository JOIN integration;
- real exporter integration proving out-of-scope paths are absent from M3U output;
- PR Guard success;
- no unresolved review threads;
- mergeability against `feature/bundle-0-bootstrap`.

## Rollback

Set `COMPOSITION_AUTHORITY=legacy` for immediate operational rollback. Code rollback is a revert of the future Bundle 39 squash commit. No data rollback is required.
