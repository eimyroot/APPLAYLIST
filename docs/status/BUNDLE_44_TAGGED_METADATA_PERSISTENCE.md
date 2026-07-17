# Bundle 44 — Tagged Metadata and Track Persistence

## Status

Implemented on an isolated feature branch. Not yet merged.

## Product Goal

Persist a scanned local audio track as stable content identity, read-only tagged metadata, current file location and audit-preserving metadata snapshots before any BPM/key/energy analysis runs.

## Schema Tree

```text
APPLAYLIST
└── Library ingestion
    ├── Bundle 42: LibraryScanner
    │   └── LibraryScanResult
    │
    ├── Bundle 43: identity + metadata boundary
    │   ├── ContentTrackIdentityService
    │   ├── TrackIdentity
    │   └── TrackMetadataReader protocol
    │
    └── Bundle 44: tagged metadata + persistence
        ├── TinyTagMetadataReader
        │   ├── read-only tag parsing
        │   ├── provider/version evidence
        │   ├── normalized text and numeric fields
        │   ├── explicit filename-title fallback
        │   └── controlled parser/output errors
        │
        ├── LibraryCandidateImporter
        │   └── TrackImportBatchResult
        │
        ├── TrackImportPersistenceService
        │   └── per-candidate transaction boundary
        │
        └── LibraryTrackRepository
            ├── tracks
            │   └── compatibility projection for existing composer/runtime
            ├── track_files
            │   ├── current path
            │   ├── historical paths
            │   └── size + mtime evidence
            └── track_metadata_snapshots
                ├── provider + provider version
                ├── metadata origin
                ├── normalized values
                ├── warnings JSON
                ├── deterministic snapshot digest
                └── current/historical evidence
```

## Runtime Flow

```text
selected directory
  → bounded LibraryScanner
  → stable SHA-256 TrackIdentity
  → TinyTagMetadataReader
  → validated TrackImportCandidate
  → transactional persistence
       ├── legacy-compatible tracks projection
       ├── active + historical file paths
       └── versioned metadata snapshots
  → ready for later MIR analysis
```

## Key Decisions

- TinyTag 2.2.1 is pinned for development and CI as a small read-only metadata dependency.
- Tag parser failures are controlled errors, not silent filename fallback.
- Filename fallback is used only when a parsed file lacks a title tag.
- Artist, album and genre are never invented from filename structure.
- Track identity remains derived from bytes, never from path or metadata.
- Same content moved to a new path preserves old path evidence and marks exactly one current path.
- Identical metadata state is idempotent; changed metadata creates a new snapshot.
- Existing `tracks` consumers remain compatible while normalized evidence is added beside them.

## Transaction Boundary

For one candidate, these writes succeed or roll back together:

```text
tracks upsert
  + track_files current-path update
  + metadata snapshot current-state update
```

A database failure must not leave a track without matching file or metadata evidence.

## Explicitly Out of Scope

- BPM, beat, key, Camelot, energy, loudness or cue analysis,
- API routes and desktop UI,
- tag mutation,
- network metadata lookup,
- Spotify/Last.fm/Soundcharts signals,
- cleanup of historical duplicate `* 2.py` files,
- permanent deletion of local files.

## Verification Requirements

- TinyTag normalization and fallback tests,
- controlled corrupt/unsupported file error,
- idempotent repeated import,
- move/relink history,
- changed metadata snapshot evidence,
- rollback proof on forced SQLite failure,
- existing repository/composition tests unchanged,
- Python 3.11 and 3.12 full CI.

## Next Slices

```text
Repository Hygiene Bundle
  → audit / dry-run / quarantine / verify
  → no automatic purge

Bundle 45 — Baseline MIR Provider
  → BPM + beat confidence
  → key + scale + Camelot
  → tonal strength
  → energy features
  → versioned warnings and evidence
```
