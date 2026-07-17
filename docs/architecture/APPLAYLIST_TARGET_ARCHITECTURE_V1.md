# APPLAYLIST Target Architecture v1

## Status

Accepted target architecture for the product-first roadmap. This document does not activate new runtime behavior.

## Architectural goal

APPLAYLIST must support one complete local DJ workflow without coupling UI, audio backends, persistence and export logic.

```text
Desktop UI
  -> application services
      -> domain contracts
      -> repositories
      -> provider boundary
      -> export adapters
```

## Product topology

```text
+------------------------------------------------------+
| Desktop application                                  |
| Library | Analysis | Set Builder | Playlist | Export |
+-------------------------+----------------------------+
                          |
+-------------------------v----------------------------+
| Application services                                 |
| LibraryImportService                                 |
| AnalysisJobService                                   |
| CanonicalCompositionRunner                           |
| PlaylistEditingService                               |
| PlaylistExportService                                |
+------------+------------------+----------------------+
             |                  |
+------------v------+  +--------v----------------------+
| Provider boundary  |  | Repository boundary          |
| metadata reader    |  | libraries/import sessions    |
| baseline audio     |  | tracks/analyses/playlists    |
| advanced optional  |  | playlist revisions/jobs      |
+--------------------+  +-------------------------------+
```

## Runtime shape

### Local-first application

The first product release is a local desktop application backed by the existing Python domain and service layers.

Recommended desktop candidate: PySide6 using Qt Widgets or QML. This is a decision candidate, not a dependency approval. The license register must be resolved before packaging.

### Headless API

FastAPI remains supported for:

- automated tests,
- local automation,
- integrations,
- future remote or service mode.

The desktop UI should call application services directly where practical. Core product behavior must not exist only inside HTTP routes.

## Layer responsibilities

### UI layer

Owns:

- folder selection,
- progress presentation,
- table and editor state,
- user commands,
- validation feedback.

Must not own:

- filesystem traversal,
- audio DSP,
- SQL,
- provider selection,
- export serialization.

### Application services

Own use-case orchestration and transaction boundaries.

Required services:

- `LibraryImportService`
- `AnalysisJobService`
- `CanonicalCompositionRunner`
- `PlaylistEditingService`
- `PlaylistExportService`

### Domain layer

Owns immutable contracts and pure rules:

- track identity,
- analysis evidence,
- composition constraints,
- transition scoring,
- playlist revisions,
- export preconditions.

Domain code must not import FastAPI, SQLite, desktop UI, Librosa or Essentia.

### Provider layer

Owns optional external or heavy capabilities:

- metadata extraction,
- baseline audio analysis,
- advanced audio analysis,
- future fingerprinting.

Provider rules:

- lazy optional imports,
- raw output never persisted directly,
- explicit availability and version,
- controlled errors,
- no repository writes.

### Repository layer

Owns persistence and query/read models.

Required aggregate boundaries:

- library,
- import session,
- track,
- analysis,
- playlist,
- playlist revision,
- job.

Repositories must support batch operations required by import and analysis jobs.

### Export adapters

Each format is isolated behind a stable export contract.

Initial order:

1. M3U8
2. JSON/manifest evidence
3. rekordbox XML
4. Traktor NML

Adapters must never mutate the approved playlist.

## Library import boundary

A bounded scanner receives an explicit absolute root and policy:

- allowed extensions,
- recursion setting,
- maximum file count,
- symlink policy,
- cancellation token.

It returns evidence:

- discovered paths,
- accepted files,
- skipped files with reason,
- errors with controlled code.

The scanner must not search outside the selected root.

## Track identity

Path alone is not a durable identity because files can move.

MVP identity should combine:

- normalized source path,
- file size,
- modified timestamp,
- lightweight content fingerprint or deterministic hash strategy.

The exact fingerprint algorithm is a Bundle 43 decision. It must be benchmarked for performance on large files and must not require network access.

## Analysis flow

```text
TrackRecord
-> AnalysisJob
-> selected provider
-> raw provider result
-> normalize
-> validate
-> AnalysisRecord
-> repository transaction
```

Required evidence:

- provider name/version,
- extractor and feature schema version,
- BPM/key/energy/duration,
- confidence values when available,
- warnings,
- source file identity,
- completed timestamp.

## Composition flow

```text
source-scoped analyzed candidates
-> fail-closed candidate adapter
-> canonical deterministic engine
-> composition result and decision trace
-> editable playlist revision
```

Composition must not query external services while scoring candidates.

## Playlist editing model

Manual editing requires a persisted revision model rather than mutating a generated result in place.

Each revision should capture:

- playlist ID,
- ordered track IDs,
- locked positions,
- origin (`generated` or `manual`),
- parent revision,
- created timestamp,
- warnings and unresolved transition issues.

Undo/redo can operate over revisions or commands in the desktop state while saving explicit checkpoints.

## Export flow

```text
approved playlist revision
-> path integrity validation
-> format adapter
-> temporary output
-> atomic publish
-> export manifest
```

Export preconditions:

- non-empty approved playlist,
- all paths are absolute and exist,
- no duplicate output identity,
- no unresolved rejected track,
- output remains below the configured export destination.

## Background processing

Long-running import and analysis work must use typed job payloads.

A job payload must include:

- job ID and type,
- library/import session ID,
- track IDs or source scope,
- provider and options,
- idempotency key,
- cancellation state.

A job must expose pending/running/done/failed/cancelled state and progress counts, not only a floating percentage.

## Security boundaries

- explicit local roots only,
- no arbitrary server-side path supplied by an untrusted remote caller,
- bounded recursion and file count,
- symlink escape prevention,
- safe output roots and atomic writes,
- no secrets in repository or generated receipts,
- optional providers cannot execute during mandatory boot.

## Observability

Product-relevant structured events:

- import session summary,
- analysis job summary,
- provider selection and controlled failure,
- composition request/result summary,
- export path-integrity result.

Existing comparison receipts remain diagnostic. They are not a user-facing product dependency.

## Deployment stages

### Development

Python virtual environment, local SQLite, FastAPI and service tests.

### Desktop MVP

Signed macOS application is the first packaging target, followed by Windows. Packaging technology and Qt licensing require explicit approval before implementation.

### Future service mode

Remote API, accounts and cloud sync are deferred until local product value is proven.

## Architecture invariants

1. UI never performs DSP or SQL.
2. Providers never persist.
3. Routes never own core use-case logic.
4. Optional audio imports never occur on mandatory boot.
5. Only normalized validated analysis is stored.
6. Composition is deterministic for a fixed snapshot and version.
7. Manual edits produce explicit playlist state.
8. Export validates every path before publishing.
9. New abstraction work requires a named product use case.
10. Default runtime changes require benchmark and rollback evidence.