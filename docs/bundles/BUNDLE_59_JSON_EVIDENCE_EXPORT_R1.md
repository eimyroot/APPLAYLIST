# Bundle 59 — PlaylistRevision JSON Evidence Export + Path Verification R1

## Status

Implementation slice. Merge, release, deploy, production optimizer activation, Personal DJ Model training, vendor database mutation, cloud upload, selected-transition editor UI, and regeneration around locks remain unauthorized.

## Canonical dependency

- base branch: `feature/bundle-0-bootstrap`
- exact base SHA: `35be83c47d2d367a60f6ac7140f0f9cd1b5fb52a`
- source playlist authority: immutable Bundle 57 `PlaylistRevision`
- path-validity authority: canonical Bundle 58 M3U8 material projection over `TrackRepository`
- analysis authority: persisted `AnalysisEvidenceRepository`
- transition authority: persisted `TransitionAssessment` snapshots exposed read-only through `TransitionEvidenceIndex`

## User outcome

A DJ can select one exact immutable playlist revision, inspect a renderer-safe evidence preview, and explicitly save a deterministic JSON evidence companion through the native desktop save dialog.

The JSON export is designed as the machine-readable companion to the canonical M3U8 export. It records revision lineage, ordered track evidence, adjacent persisted transition evidence metadata, and proof that the same revision is currently path-valid for M3U8 export.

## Authority model

```text
PlaylistRevisionRepository
  -> exact revision_id
  -> Bundle 58 M3U8 material projection
      -> TrackRepository path-validity verification
      -> M3U8 SHA-256 + byte count only
  -> AnalysisEvidenceRepository
      -> latest successful persisted evidence per revision track
      -> active correction only when bound to that evidence
  -> TransitionEvidenceIndex
      -> read-only metadata from persisted TransitionAssessment snapshots
  -> deterministic canonical JSON
  -> authenticated private sidecar material
  -> trusted Rust validation
  -> native save dialog
  -> bounded atomic local write
  -> renderer-safe receipt
```

No component in Bundle 59 may append, update, delete, regenerate, or reinterpret playlist, analysis, correction, or transition evidence.

## JSON evidence document

Schema:

`applaylist-playlist-revision-evidence-r1`

Top-level fields:

- exact revision identity and immutable fingerprint
- bounded parent lineage ending at the explicitly selected revision
- exact ordered track IDs, display labels and lock state
- latest successful persisted analysis evidence for each track, or explicit `missing`
- active correction only when it references that exact successful evidence
- adjacent transition-pair evidence metadata from canonical persisted TransitionAssessment snapshots, or explicit `missing`
- M3U8 verification summary: `path_valid`, track count, M3U8 content SHA-256 and byte count
- Personal DJ Model training authorization fixed to false
- production activation authorization fixed to false

The evidence document deliberately contains no source filesystem paths, output paths, sidecar credentials, raw exceptions, audio bytes, or raw M3U8 material.

## Transition evidence rule

Bundle 59 does not create or recompute TransitionAssessment.

For each adjacent track pair in the selected immutable revision:

- persisted matching snapshots are exposed only as bounded identity/provenance metadata;
- stored snapshot payload SHA-256 is reverified before metadata is returned;
- if no persisted snapshot exists, status is `missing`;
- missing transition evidence is never silently synthesized.

## Path verification rule

Bundle 59 reuses `DesktopPlaylistExportTransport.material()` from Bundle 58 as the path verification oracle.

That means the JSON evidence export succeeds only if the same exact revision currently satisfies Bundle 58 path rules:

- every track resolves through `TrackRepository`;
- every path is absolute and canonicalizable;
- every referenced file exists and is a file;
- newline/null/control-character path injection is rejected;
- audio bytes are not read or hashed.

Only the M3U8 SHA-256, byte count, track count, format, and `path_valid=true` are copied into the JSON evidence document. Raw paths and M3U8 text are discarded from the evidence projection.

## Determinism

For identical persisted playlist revision, TrackRepository path state, AnalysisEvidence/correction state, and TransitionAssessment snapshot state, JSON bytes are deterministic:

- UTF-8
- sorted JSON object keys
- compact separators
- one final newline
- SHA-256 over exact emitted bytes

Material is bounded to 256 KiB.

## Sidecar routes

Authenticated POST only:

- `/v1/playlist/evidence/preview`
- `/v1/playlist/evidence/material`

Exact request body:

```json
{"revision_id":"prv_..."}
```

Unknown fields fail closed.

## Desktop commands

- `playlist_evidence_preview`
- `playlist_evidence_export_json`

They are isolated in `main-playlist-evidence-export` capability.

The private material route is never exposed directly to renderer JavaScript.

## Native write boundary

`playlist_evidence_export_json`:

1. fetches authenticated private material for one explicit revision ID;
2. validates strict material DTO shape;
3. recomputes JSON SHA-256 and byte count;
4. parses and validates the evidence document identity and path-verification proof;
5. rejects forbidden path-key shapes in the evidence document;
6. opens native save dialog;
7. returns `None` on cancel with no write;
8. enforces `.json`;
9. rejects an existing target instead of silently overwriting it;
10. writes a bounded temporary file in the selected directory;
11. syncs and renames it to the target;
12. returns only a renderer-safe receipt.

## Renderer-safe preview

Preview contains only:

- revision ID / playlist ID / revision index
- JSON format + safe suggested filename
- track count
- count of tracks with persisted analysis evidence
- adjacent transition pair count
- count of adjacent pairs with persisted transition evidence
- `m3u8_path_valid=true`
- M3U8 content SHA-256
- false authority flags

No source path, output directory or JSON material is returned.

## Renderer-safe receipt

Successful receipt contains only:

- revision ID
- `json` format
- safe output basename
- track count
- JSON SHA-256
- bytes written
- M3U8 path-valid flag
- M3U8 SHA-256
- false authority flags

## Explicit non-effects

Bundle 59 does not:

- read/hash/copy/transcode audio bytes
- call MIR providers
- append or modify AnalysisEvidence/corrections
- create or recompute TransitionAssessment
- rerun optimizer
- mutate PlaylistRevision history
- train Personal DJ Model
- activate production optimization
- mutate rekordbox/Traktor/Serato databases
- upload/sync to cloud
- release/deploy/sign/notarize the application

## Required merge gates

- exact base / merge-base identity
- full Python CI 3.11 and 3.12
- deterministic JSON evidence transport tests
- authenticated sidecar strict-body/auth/path privacy tests
- path-invalid fail-closed regression
- renderer no-path/no-network authority tests
- Desktop Rust rustfmt/check/test
- Desktop Sidecar Proof Ubuntu + macOS
- PR Guard
- zero unresolved review threads
- exact-head evidence recorded in PR before merge authorization

## Next dependency

After Bundle 59, the R4 interoperability track can add the first documented vendor adapter guidance over the canonical pair:

```text
immutable PlaylistRevision
  -> M3U8
  -> JSON evidence companion
  -> vendor-specific read/write-neutral interoperability adapter
```

Vendor database mutation remains a separate authorization boundary.
