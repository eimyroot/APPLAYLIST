# Bundle 35 — Canonical Composition Runner

## Status

Implementation candidate. Production pipeline authority remains unchanged.

## Goal

Provide one reusable canonical execution boundary for loading analyzed tracks, adapting historical data and running deterministic composition.

## Execution flow

```text
AnalysisRepository
      │
      ▼
PlaylistCandidate[]
      │
      ▼
fail-closed candidate adapter
      │
      ▼
CompositionTrack[]
      │
      ▼
DeterministicCompositionEngine
      │
      ▼
CanonicalCompositionExecutionResult
```

## Contracts

`CanonicalCompositionExecutionRequest` contains:

- target track count,
- BPM range,
- composition mode,
- optional genre,
- optional start key,
- explicit duration fallback.

`CanonicalCompositionExecutionResult` contains:

- the immutable `CompositionResult`,
- directly exportable `CompositionTrack` values,
- source candidate count,
- adapted count,
- rejected count,
- fallback count,
- complete adapter issue evidence.

## Failure ordering

Composition mode validation occurs before repository access. Candidate validation remains fail-closed for missing or malformed track ID, path, BPM, Camelot key and energy.

A duration fallback is allowed only when explicitly represented by a `duration_fallback` issue.

## Comparison integration

`CompositionShadowService` delegates canonical execution to the runner and only calculates legacy/canonical comparison metrics. Existing repository and engine injection remain supported for compatibility.

## Isolation

Bundle 35 does not:

- switch the production pipeline,
- export a canonical playlist,
- change API responses,
- change receipt schemas,
- create a database migration,
- perform filesystem or network I/O beyond the existing repository read.

## Rollback

Revert the Bundle 35 squash commit. No data rollback is required.
