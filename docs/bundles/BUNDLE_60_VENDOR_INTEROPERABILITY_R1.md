# Bundle 60 — Vendor Interoperability Handoff R1

## Status

Implementation slice. Merge, release, deploy, production optimizer activation, Personal DJ Model training, proprietary vendor database mutation, vendor process automation, and cloud upload remain unauthorized.

## Canonical dependency

- base branch: `feature/bundle-0-bootstrap`
- exact base SHA: `5462d85d7caefe920c04d6f4204679943beaa85e`
- playlist authority: immutable Bundle 57 `PlaylistRevision`
- path-validity / M3U8 authority: Bundle 58 `DesktopPlaylistExportTransport`
- evidence companion: Bundle 59 deterministic JSON evidence export

## User outcome

A DJ can select one exact immutable playlist revision, verify the currently documented interoperability capability for rekordbox, Traktor, and Serato, and explicitly export a deterministic rekordbox XML Bridge artifact through the native desktop save dialog.

Traktor and Serato remain guidance-only in R1. The UI and command surface do not pretend that unsupported artifacts are available.

## Authority model

```text
immutable PlaylistRevision
  -> Bundle 58 canonical path-valid M3U8 projection
      -> path validity + M3U8 SHA-256
  -> Bundle 59 JSON evidence companion remains available separately
  -> Bundle 60 vendor capability catalog
      -> rekordbox: deterministic XML Bridge artifact
      -> Traktor: guidance_only_nml_required
      -> Serato: guidance_only_files_crate
  -> renderer-safe preview
  -> trusted Rust validation
  -> native save dialog (rekordbox XML only)
  -> bounded atomic write
  -> sanitized receipt
```

No Bundle 60 component may update/delete playlist revisions or write into a vendor-managed database/library structure.

## Verified vendor references

Verification date: `2026-08-19`.

### rekordbox

- https://rekordbox.com/en/support/developer/
- https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf

R1 capability: `documented_format_export` using a rekordbox XML Bridge artifact.

### Traktor

- https://www.native-instruments.com/ni-tech-manuals/traktor-play-user-guide/en/working-with-playlists

R1 capability: `guidance_only_nml_required`. Official documentation establishes `.nml` playlist import; Bundle 60 does not generate NML.

### Serato

- https://support.serato.com/hc/en-us/articles/223446528-Adding-files-to-the-Serato-DJ-Pro-Library
- https://support.serato.com/hc/en-us/articles/227561407-Crates-in-Serato-DJ-Pro-Serato-DJ-Lite

R1 capability: `guidance_only_files_crate`. Bundle 60 does not mutate crates or `_Serato_` data.

These references are recorded documentation evidence only. Bundle 60 performs no runtime network fetch.

## Capability catalog

Schema: `applaylist-desktop-vendor-interop-preview-r1`

Catalog version: `vendor-interop-catalog-r1`

Exactly three capabilities are emitted:

1. `rekordbox` / `documented_format_export` / `rekordbox_xml` / artifact export available
2. `traktor` / `guidance_only_nml_required` / no artifact / artifact export unavailable
3. `serato` / `guidance_only_files_crate` / no artifact / artifact export unavailable

Every capability fixes `vendor_database_mutation_authorized=false`.

## rekordbox XML artifact

Private material schema: `applaylist-desktop-vendor-interop-material-r1`.

For one explicit revision ID, the transport reuses Bundle 58 material as the canonical path oracle and emits deterministic UTF-8 XML with:

- `DJ_PLAYLISTS Version="1.0.0"`
- `PRODUCT`
- `COLLECTION Entries=N`
- stable artifact-local numeric `TrackID` values `1..N`
- exact immutable revision order
- XML-escaped display names
- URI-formatted `Location` values derived from the already-canonicalized local paths
- `PLAYLISTS/NODE` playlist entries referencing the same numeric track IDs

The XML is bounded to 128 KiB and carries exact SHA-256 + byte count.

## Privacy boundary

Renderer-safe preview contains revision identity, track count, M3U8 path-valid status/digest, bounded capability codes, and false authority flags.

It contains no:

- source filesystem paths
- raw M3U8 material
- raw XML material
- output directory
- sidecar secret/nonce/port
- arbitrary vendor process state

Private rekordbox XML material is consumed only by the trusted Rust command.

## Sidecar routes

Authenticated POST only:

- `/v1/playlist/vendor/preview`
- `/v1/playlist/vendor/rekordbox/material`

Exact request body:

```json
{"revision_id":"prv_..."}
```

Unknown fields fail closed.

There are no Traktor or Serato artifact material routes in R1.

## Desktop commands

- `playlist_vendor_interop_preview`
- `playlist_vendor_interop_export_rekordbox`

They are isolated in `main-playlist-vendor-interop` capability.

There are no Traktor or Serato export commands in R1.

## Native write boundary

`playlist_vendor_interop_export_rekordbox`:

1. requires one explicit immutable revision ID;
2. fetches authenticated private material;
3. validates strict DTO shape and false authority flags;
4. recomputes XML SHA-256 and byte count;
5. verifies bounded rekordbox XML structure;
6. opens native save dialog;
7. cancel returns no receipt and performs no write;
8. enforces `.xml`;
9. rejects an existing target rather than silently overwriting;
10. writes a bounded temporary file, syncs, then renames atomically;
11. returns only basename, vendor/format, revision ID, track count, byte count, XML digest, M3U8 digest, and false authority flags.

## Failure model

Fail closed on:

- missing/invalid revision identity
- Bundle 58 path verification failure
- unavailable/missing TrackRecord path
- malformed/oversized XML material
- digest or byte-count mismatch
- capability/status escalation
- vendor database mutation authorization escalation
- malformed target or wrong extension
- existing target
- write/sync/rename failure
- unknown sidecar request fields
- failed sidecar authentication

## Explicit non-effects

Bundle 60 does not:

- generate Traktor NML
- mutate Traktor collection data
- mutate Serato crates or `_Serato_` data
- mutate rekordbox databases/device libraries
- automate vendor applications
- read/hash/copy/transcode audio bytes
- call MIR providers
- create/recompute TransitionAssessment
- rerun optimizer
- mutate PlaylistRevision history
- train Personal DJ Model
- activate production optimization
- upload/sync to cloud
- release/deploy/sign/notarize the application

## Required merge gates

- exact base and merge-base identity
- full Python CI 3.11 + 3.12
- deterministic rekordbox XML regression tests
- XML escaping / URI encoding / path privacy tests
- strict authenticated sidecar tests
- renderer no-network/no-filesystem/no-private-material tests
- proof that Traktor/Serato have no artifact export command in R1
- Desktop Rust rustfmt/check/test
- Desktop Sidecar Proof Ubuntu + macOS
- PR Guard
- zero unresolved review threads
- exact-head evidence recorded in PR before merge authorization

`MERGE_AUTHORIZATION=NO`
`RELEASE_AUTHORIZATION=NO`
`DEPLOY_AUTHORIZATION=NO`
`PRODUCTION_EFFECTS=NO`
