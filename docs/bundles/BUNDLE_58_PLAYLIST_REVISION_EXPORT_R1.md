# Bundle 58 — Governed PlaylistRevision Export R1

## Status

Implementation slice. Merge, release, deploy, production optimizer activation, Personal DJ Model training, vendor database mutation, and cloud upload remain unauthorized.

## Canonical dependency

- base branch: `feature/bundle-0-bootstrap`
- exact base SHA: `abaf82716f112f2b40193a6b2a181536cd941641`
- source authority: immutable Bundle 57 `PlaylistRevision`

## User outcome

A DJ can select one exact immutable playlist revision in the desktop shell, inspect a renderer-safe export preview, explicitly choose a destination through the native save dialog, and export a UTF-8 M3U8 file.

No terminal or CSV handoff is required.

## Authority model

```text
PlaylistRevisionRepository
  -> exact revision_id
  -> DesktopPlaylistExportTransport
      -> preview (renderer-safe)
      -> material (authenticated/private)
  -> PlaylistExportBridge
  -> native save dialog
  -> bounded atomic local write
  -> renderer-safe receipt
```

The revision ledger remains the only playlist revision authority. Export is a read-only projection and never updates or deletes revision rows.

## R1 interoperability format

Generic UTF-8 M3U8 only.

The material contains:

- `#EXTM3U`
- one `#EXTINF` row per revision item
- the revision display label
- the canonical local TrackRecord path
- exact immutable revision order

The export does not copy, transcode, hash, or read audio bytes.

Vendor-specific rekordbox, Traktor, and Serato database mutation is outside R1.

## Privacy and path boundary

Private filesystem paths are resolved from `TrackRepository` only inside the authenticated sidecar.

The renderer-safe preview contains only:

- revision ID
- playlist ID
- revision index
- `m3u8` format
- safe suggested filename
- bounded ordered track IDs/display labels/lock state
- training/activation flags fixed to false

The private material additionally contains M3U8 text, SHA-256, and byte count. It is consumed by Rust and is never returned by a Tauri renderer command.

The successful renderer receipt contains only:

- revision ID
- format
- safe output filename (basename only)
- track count
- M3U8 content SHA-256
- bytes written
- training/activation flags fixed to false

No output directory or source audio path is returned to JavaScript.

## Native write boundary

`playlist_export_m3u8`:

1. fetches authenticated private material for one explicit revision ID;
2. validates exact private response shape;
3. recomputes SHA-256 and byte count;
4. verifies M3U8 structure and local path existence without reading audio bytes;
5. opens the native save dialog;
6. returns `None` on user cancel with no write;
7. enforces `.m3u8`;
8. rejects an already-existing target instead of silently overwriting it;
9. writes a bounded temporary file in the selected directory;
10. syncs and renames it to the selected target;
11. returns only a renderer-safe receipt.

## Sidecar routes

Authenticated POST only:

- `/v1/playlist/export/preview`
- `/v1/playlist/export/material`

Exact request body:

```json
{"revision_id":"prv_..."}
```

Unknown fields fail closed.

## Tauri commands

- `playlist_export_preview`
- `playlist_export_m3u8`

They are isolated in `main-playlist-export` capability.

## Failure model

Fail closed on:

- unknown/missing revision
- malformed revision sequence
- missing local TrackRecord
- relative, unavailable, newline/null/control-character path
- invalid display content
- oversized M3U8 material
- material digest/byte-count mismatch
- malformed private material
- invalid target extension/directory
- existing target
- write/rename failure

## Explicit non-effects

Every preview/material/receipt keeps:

```text
personal_dj_model_training_authorized = false
production_activation_authorized      = false
```

Bundle 58 does not:

- run MIR providers
- read/hash audio bytes
- rerun optimizer or TransitionAssessment
- mutate PlaylistRevision history
- train preference models
- activate production optimization
- write rekordbox/Traktor/Serato databases
- upload/sync to cloud
- release/deploy/sign/notarize the application

## Required merge gates

- exact base/merge-base identity
- full Python CI 3.11 and 3.12
- export transport + authenticated sidecar regression tests
- renderer path/privacy contract tests
- Desktop Rust rustfmt/check/test
- Desktop Sidecar Proof on Ubuntu and macOS
- PR Guard
- zero unresolved review threads
- exact-head evidence recorded in PR before merge authorization
