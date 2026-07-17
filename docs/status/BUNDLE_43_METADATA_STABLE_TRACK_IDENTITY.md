# Bundle 43 — Metadata and Stable Track Identity

## Status

Implemented on an isolated feature branch. Not yet merged.

## Selected Enterprise Scope

This bundle deliberately keeps only the highest-value elements from the historical plans and donor repositories:

- immutable contracts,
- stable content identity,
- deterministic processing,
- controlled failure taxonomy,
- explicit provider/version evidence,
- bounded-memory file processing,
- tests before rollout,
- no optional heavy dependency on the boot path.

Deferred or rejected here:

- Spotify, Last.fm and market popularity signals,
- embeddings and generative AI,
- BPM, key, energy or cue extraction,
- database writes,
- API and desktop integration,
- direct reuse of historic bundle code,
- path-derived track identity,
- guessed artist parsing from filenames.

## Schema Tree

```text
APPLAYLIST
└── Library ingestion
    ├── Bundle 42: LibraryScanner
    │   └── LibraryScanResult
    │       ├── accepted_paths[]
    │       ├── skipped[]
    │       ├── errors[]
    │       └── completion evidence
    │
    └── Bundle 43: Identity and metadata
        ├── ContentTrackIdentityService
        │   ├── opened-file-descriptor SHA-256
        │   ├── inode/device verification
        │   ├── size + mtime evidence
        │   └── TrackIdentity
        │       └── aptrack:v1:sha256:<digest>
        │
        ├── TrackMetadataReader boundary
        │   ├── provider name/version
        │   ├── explicit metadata origin
        │   ├── normalized values
        │   └── warnings
        │
        └── LibraryCandidateImporter
            ├── deterministic ordering
            ├── duplicate-content rejection
            ├── controlled issue taxonomy
            └── TrackImportBatchResult
```

## Runtime Flow

```text
selected directory
  → bounded scan
  → accepted audio path
  → stable content fingerprint
  → read-only metadata provider
  → validated import candidate
  → later repository persistence
  → later BPM/key/energy analysis
```

## Security Boundaries

- Input paths must be absolute and resolve to regular files.
- Hashing is streaming and bounded in memory.
- Identity is bound to the opened file descriptor.
- Device/inode, size and mtime must remain stable during hashing.
- Metadata provider output is validated before acceptance.
- Duplicate bytes are represented once, with explicit duplicate evidence.
- No tag mutation, network access or database side effect occurs.

## Recognition Roadmap

Bundle 43 does not claim music recognition. It creates the stable evidence layer required for it.

The next product slices are:

```text
Bundle 44: tagged metadata provider + repository persistence
Bundle 45: real baseline MIR provider
           ├── tempo + beat confidence
           ├── key + scale + Camelot
           ├── tonal strength/confidence
           ├── energy features
           └── duration and warnings
Bundle 46: benchmark harness and acceptance report
Bundle 47+: desktop library and analysis inspector
```

## Definition of Done

- same bytes at different paths produce the same track ID,
- changed bytes produce a different track ID,
- identity processing remains bounded in memory,
- a file changed or replaced during hashing is rejected,
- malformed metadata output becomes a controlled issue,
- filename fallback does not invent artist certainty,
- duplicate content is deterministic and visible,
- Python 3.11 and 3.12 CI pass.
