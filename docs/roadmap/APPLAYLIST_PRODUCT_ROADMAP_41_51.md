# APPLAYLIST Product Roadmap — Bundles 41–51

## Status

Accepted product-first implementation order following Bundle 40 composition startup readiness.

## Governing rule

Every bundle after Bundle 41 must deliver a named product capability, a measurable acceptance result, or a release-critical dependency for the next vertical slice.

Additional authority, receipt, governance or generalized orchestration work is frozen unless a roadmap bundle demonstrates that it is necessary.

## Bundle 41 — Product Baseline Realignment

### Goal

Replace infrastructure-first sequencing with a product-first baseline.

### Deliverables

- Product Definition v1
- Target Architecture v1
- MIR Benchmark Specification v1
- License Decision Register v1
- this roadmap
- updated README and implementation order

### Scope

Documentation only.

## Bundle 42 — Library Import Boundary

### User value

A DJ can select one local folder and see which audio files APPLAYLIST accepts, skips or cannot read.

### Deliverables

- immutable library and import-session contracts,
- bounded directory scanner,
- explicit supported-extension policy,
- recursion, symlink and maximum-file limits,
- cancellation boundary,
- accepted/skipped/error evidence,
- no analysis or metadata dependency yet.

### Acceptance

- scanner never escapes the selected root,
- deterministic ordering,
- duplicate paths are not returned twice,
- controlled results for unreadable files and loops,
- unit and temporary-filesystem integration tests.

## Bundle 43 — Metadata and Stable Track Identity

### User value

Imported files become useful library rows and remain identifiable after safe rescans.

### Deliverables

- read-only metadata provider contract,
- selected provider after license review,
- normalized title/artist/album/genre/duration/sample-rate/bitrate,
- stable identity strategy,
- batch track upsert/query operations,
- changed/moved/missing file evidence,
- import-session persistence.

### Acceptance

- supported formats produce normalized records,
- malformed tags cannot break an import batch,
- a rescan is idempotent,
- identity collisions and moves are tested.

## Bundle 44 — Analysis Job Contract

### User value

A DJ can start, observe and cancel analysis for imported tracks.

### Deliverables

- typed job payload,
- track/library/provider/options fields,
- idempotency key,
- pending/running/done/failed/cancelled states,
- count-based progress,
- controlled error taxonomy,
- repository-backed job state.

### Acceptance

- retry does not create duplicate analysis for the same version,
- cancellation is visible and controlled,
- job payload contains no arbitrary unvalidated path authority.

## Bundle 45 — Real Baseline Audio Provider

### User value

APPLAYLIST produces real BPM, key/Camelot, energy and duration evidence for local tracks.

### Deliverables

- lazy Librosa/NumPy/SciPy provider boundary,
- no repository writes inside provider code,
- normalized raw result,
- algorithm/provider version evidence,
- confidence and warnings where possible,
- controlled decode/dependency/runtime/output failures,
- analysis application service persistence transaction.

### Acceptance

- no optional import on API mandatory boot,
- no `stub` result,
- no NaN/inf persistence,
- real audio fixtures produce validated records,
- failure of one file does not corrupt the batch.

## Bundle 46 — MIR Benchmark Harness

### User value

Provider choice is justified by measured quality rather than implementation convenience.

### Deliverables

- dataset manifest schema,
- benchmark runner,
- BPM/key/energy/runtime metrics,
- machine-readable report,
- baseline Librosa report,
- optional Essentia experiment when licensing permits,
- human DJ transition-evaluation protocol.

### Decision Gate A

The production provider default cannot change until the benchmark and license review pass.

## Bundle 47 — Desktop Library Shell

### User value

The DJ can perform import and inspect library state without terminal or direct API use.

### Preconditions

- desktop framework and packaging license approved,
- Bundles 42–46 complete.

### Deliverables

- desktop application entry point,
- folder picker,
- library table,
- import and analysis progress,
- error/warning presentation,
- service-layer integration without duplicated domain logic.

### Acceptance

A clean local user can import and analyze a folder through the UI.

## Bundle 48 — Analysis Inspector

### User value

The DJ can review uncertain or invalid analysis before using tracks in a set.

### Deliverables

- BPM/key/Camelot/energy/confidence display,
- provider/version evidence,
- warning filters,
- manual correction command and audit trail,
- re-analysis command.

### Acceptance

Manual corrections survive refresh and are distinguishable from provider output.

## Bundle 49 — Set Builder

### User value

The DJ can generate an explainable set under explicit musical constraints.

### Deliverables

- target count and target-duration request,
- BPM range,
- energy curve/mode,
- genre and optional start-key controls,
- canonical composition execution,
- transition score/reason panel,
- summary warnings and constraint failures.

### Acceptance

The UI result reflects the exact source scope and constraints and is deterministic for a fixed snapshot.

## Bundle 50 — Manual Playlist Editor

### User value

The DJ can turn an automatic proposal into an approved performance plan.

### Deliverables

- persisted playlist/revision model,
- reorder/remove/lock/replace,
- regenerate selected section,
- undo/redo or revision checkpoints,
- transition-warning recalculation,
- explicit approved state.

### Acceptance

Manual edits do not disappear after restart and export uses the approved revision.

## Bundle 51 — M3U8 End-to-End Release Slice

### User value

A DJ can complete the full workflow and open the exported playlist in supported DJ software.

### Deliverables

- approved-revision export,
- UTF-8 M3U8 adapter,
- atomic write and manifest,
- path-integrity validation,
- desktop export action,
- clean-install instructions,
- end-to-end smoke script,
- supported-DJ-software compatibility record.

### Definition of Done

- select folder,
- import tracks,
- analyze real audio,
- inspect evidence,
- generate set,
- edit order,
- export M3U8,
- open the playlist successfully in at least one declared supported application.

## Post-MVP candidates

Only after Bundle 51:

- rekordbox XML adapter,
- Traktor NML adapter,
- advanced provider rollout,
- packaging for additional platforms,
- library change monitoring,
- cue/phrase research,
- OneLibrary-compatible integration when technically and legally available.

## Stop list until Bundle 51

- cloud accounts and synchronization,
- streaming services,
- mobile clients,
- live performance engine,
- stems,
- waveform/beatgrid editor,
- AI chat as the main product surface,
- automatic live transitions,
- proprietary database reverse engineering,
- further composition authority abstractions without an accepted product need.

## Release governance

Each bundle requires:

1. issue with user value and scope,
2. branch from exact canonical head,
3. smallest isolated diff,
4. Python 3.11 and 3.12 CI,
5. product acceptance tests appropriate to the slice,
6. rollback statement,
7. documentation update when contracts change.

A green test count alone is not sufficient. Product-facing bundles must demonstrate their user-visible acceptance outcome.