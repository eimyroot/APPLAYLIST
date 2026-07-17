# Bundle 36 — Canonical Composition Export Service

## Status

Implementation candidate. The production pipeline remains legacy-authoritative.

## Goal

Provide an explicit service that can execute the canonical composition runner and materialize its result through the existing exporter without changing API or pipeline behavior.

## Flow

```text
CanonicalCompositionExecutionRequest
                │
                ▼
CanonicalCompositionRunner
                │
                ▼
CanonicalCompositionExecutionResult
                │
      failed or empty? ── yes ──► no export
                │ no
                ▼
validated canonical run ID
                │
                ▼
Exporter.export_m3u
                │
                ▼
validated immutable export artifact
```

## Postconditions

A successful canonical export requires:

- a run ID matching `canonical-[A-Za-z0-9_-]+`,
- exporter `playlist_id` equal to the generated run ID,
- `resolved_count` equal to the canonical track count,
- `skipped_count` equal to zero,
- non-empty M3U, manifest, warnings and audit paths.

Any violated postcondition raises a controlled runtime error instead of returning a misleading success contract.

## Empty and failed results

Failed canonical composition or an empty track set returns an immutable result with:

- `run_id=None`,
- `artifact=None`,
- `exported=False`.

The exporter is not invoked.

## Isolation

Bundle 36 does not:

- switch `OrchestratorPipeline`,
- add or modify API routes,
- change comparison receipts,
- activate a feature flag,
- change the database schema,
- call external services.

The service must be invoked explicitly by future controlled rollout code.

## Filesystem behavior

The existing `Exporter` owns filesystem writes. Integration tests use isolated temporary export and artifact directories and verify M3U, manifest, warnings and audit outputs.

## Rollback

Revert the Bundle 36 squash commit. No data rollback is required because the service is not automatically invoked.
