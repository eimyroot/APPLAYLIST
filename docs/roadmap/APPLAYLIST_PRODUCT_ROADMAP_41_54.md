# APPLAYLIST Product Roadmap — Bundles 41–54

## Status

Accepted product-first roadmap v2 after Bundle 46 and the Bundle 47 desktop architecture decision.

This document supersedes `APPLAYLIST_PRODUCT_ROADMAP_41_51.md`.

## Governing rule

Every bundle must deliver one of:

- a named user capability,
- measured product-quality evidence,
- a release-critical dependency for the next vertical slice.

Additional authority, receipt, generalized orchestration, cloud or AI-chat work remains frozen unless a roadmap item proves it necessary.

Every bundle includes a schema tree showing:

- current layer,
- new/changed boundary,
- data flow,
- out-of-scope items,
- next dependency.

## Completed foundation

### Bundle 41 — Product Baseline Realignment ✅

Delivered product definition, target architecture, benchmark specification, license register and product-first sequencing.

### Bundle 42 — Bounded Library Import Boundary ✅

```text
selected root
  → bounded scanner
  → accepted / skipped / error evidence
```

Delivered root containment, deterministic ordering, limits, cancellation and symlink-loop protection.

### Bundle 43 — Stable Track Identity and Metadata Boundary ✅

```text
accepted path
  → content SHA-256 identity
  → read-only metadata boundary
  → deterministic import candidate
```

Delivered path-independent track identity, opened-file validation, metadata contracts and duplicate-content evidence.

### Bundle 44 — Tagged Metadata and Track Persistence ✅

```text
import candidate
  → TinyTag metadata
  → normalized track record
  → transactional SQLite persistence
  → relink and snapshot evidence
```

Delivered read-only tagged metadata, idempotent persistence, path history and append-only metadata snapshots.

### Bundle 45 — Baseline Librosa MIR Provider ✅

```text
audio path
  → lazy Librosa provider
  → BPM / key / Camelot / energy evidence
  → canonical normalized result
```

Delivered real local MIR analysis with provenance and controlled failures. It remains a benchmark candidate rather than production-authoritative truth.

### Bundle 46 — MIR Benchmark Harness ✅

```text
external licensed manifest
  → provider analysis
  → per-track metrics
  → aggregate report
  → manual decision gate
```

Delivered fail-closed dataset manifests, BPM/key/energy/runtime metrics and deterministic reports. Real licensed dataset runs remain an operator activity outside the repository.

## Desktop and intelligence roadmap

### Bundle 47 — Desktop Shell Architecture and Security ADR

#### Value

The product has one approved desktop/web hybrid direction and an enforceable host security model before new toolchains enter the repository.

#### Deliverables

- weighted Tauri/Electron/PySide6 decision,
- accepted Tauri 2 + React/TypeScript + packaged Python sidecar target,
- Electron fallback criteria,
- desktop security contract,
- sidecar lifecycle and authentication contract,
- filesystem capability model,
- desktop/PWA feature matrix,
- packaging/signing/updater requirements,
- realigned roadmap.

#### Scope

Documentation only. No frontend, Rust or desktop dependency activation.

#### Acceptance

- architecture and security documents are internally consistent,
- existing Python CI remains green,
- rollback requires no data migration.

### Bundle 48 — Tauri/Python Sidecar Proof

#### Value

The team proves that the selected shell can securely start, supervise and stop the real Python application boundary before building product screens.

#### Schema tree

```text
minimal React window
  → typed Tauri command
  → Rust sidecar supervisor
  → packaged Python readiness service
  → authenticated loopback response
```

#### Deliverables

- minimal React/TypeScript frontend workspace,
- minimal Tauri 2 core,
- target-specific Python sidecar build proof,
- readiness handshake and protocol version,
- per-session credential hidden from renderer,
- native folder dialog returning opaque capability ID,
- graceful shutdown and forced-timeout fallback,
- package-layout verification,
- measured artifact size, startup time and idle memory,
- macOS packaged smoke test.

#### Out of scope

- library table,
- actual folder scan UI,
- analysis screens,
- composition or export UI,
- updater rollout.

#### Acceptance

- renderer has no arbitrary shell/filesystem permission,
- renderer cannot call sidecar directly,
- sidecar binds loopback only,
- wrong credential and wrong readiness nonce fail closed,
- sidecar terminates with desktop exit,
- signed/notarized build plan is executable,
- Electron fallback decision is recorded if proof gates fail.

### Bundle 49 — Desktop Library Shell

#### Value

A DJ can select a folder, import tracks and inspect library state without terminal use.

#### Schema tree

```text
Library screen
  → native LibraryRootCapability
  → LibraryImportService
  → progress/events
  → paged library read model
```

#### Deliverables

- application shell/navigation,
- native folder picker,
- import command,
- progress and cancellation,
- library table with title/artist/format/duration/state,
- skipped/error presentation,
- empty/loading/error states,
- keyboard navigation and accessibility baseline.

#### Acceptance

A clean local user can choose a real folder and see deterministic imported library rows through the packaged desktop app.

### Bundle 50 — Analysis Job and Inspector

#### Value

A DJ can analyze imported tracks and review uncertain results before using them in a set.

#### Schema tree

```text
selected track scope
  → typed AnalysisJob
  → baseline provider
  → normalized persisted analysis
  → inspector filters and corrections
```

#### Deliverables

- repository-backed typed analysis job,
- pending/running/done/failed/cancelled states,
- count-based progress,
- BPM/key/Camelot/energy/confidence display,
- provider/version/warnings,
- failed/uncertain filters,
- manual correction command and audit trail,
- explicit re-analysis.

#### Acceptance

- one file failure does not corrupt the batch,
- cancellation is visible and bounded,
- manual correction survives restart and is distinguishable from provider output.

### Bundle 51 — Transition Intelligence v1

#### Value

APPLAYLIST can explain whether two tracks are suitable neighbors rather than using opaque composition scores.

#### Schema tree

```text
Track A analysis + Track B analysis
  → transition feature adapter
  → versioned scoring profile
  → component scores + penalties
  → explanation
```

#### Deliverables

- versioned transition contract,
- BPM compatibility,
- Camelot/harmonic compatibility,
- energy movement,
- rhythm/percussive continuity,
- configurable penalties,
- normalized total score,
- structured explanation,
- deterministic pairwise tests.

#### Acceptance

- every score is bounded and reproducible,
- missing evidence produces controlled degradation or rejection,
- component weights and profile version are recorded,
- no external network call occurs while scoring.

### Bundle 52 — Explainable Set Builder

#### Value

A DJ can generate a set under explicit musical and time constraints and understand why tracks were selected.

#### Schema tree

```text
source-scoped analyzed tracks
  → transition graph
  → set constraints
  → deterministic optimizer
  → ordered proposal + trace
```

#### Initial modes

- `smooth_journey`,
- `build_to_peak`,
- `wave`.

#### Deliverables

- target count and duration,
- BPM range and maximum jump,
- start/end energy or mode,
- genre filters,
- optional start key,
- artist/label spacing,
- locked tracks/positions,
- transition reason panel,
- total duration and unresolved warnings.

#### Acceptance

The same source snapshot, scoring version and constraints produce the same set and decision trace.

### Bundle 53 — Manual Playlist Editor

#### Value

A DJ can turn the generated proposal into an approved performance plan.

#### Schema tree

```text
generated proposal
  → playlist revision
  → reorder / remove / lock / replace
  → transition recalculation
  → approved revision
```

#### Deliverables

- persisted playlist/revision model,
- drag or keyboard reorder,
- remove and replace,
- lock track/position,
- regenerate selected section,
- undo/redo or revision checkpoints,
- transition-warning recalculation,
- explicit approved state.

#### Acceptance

Manual edits survive restart, remain auditable and do not mutate the original generated evidence.

### Bundle 54 — M3U8 End-to-End Release Slice

#### Value

A DJ completes the full APPLAYLIST workflow and opens the exported playlist in declared supported DJ software.

#### Schema tree

```text
approved playlist revision
  → path integrity validation
  → UTF-8 M3U8 adapter
  → temporary file
  → atomic publish
  → export manifest
```

#### Deliverables

- native export destination capability,
- M3U8 adapter,
- atomic write,
- path and encoding validation,
- export manifest,
- desktop action and success/error presentation,
- clean-install operator guide,
- packaged end-to-end smoke test,
- compatibility record for at least one declared DJ application.

#### Definition of Done

- install signed desktop build,
- select local folder,
- import tracks,
- analyze real audio,
- inspect evidence,
- generate explainable set,
- manually edit and approve,
- export M3U8,
- open exported playlist successfully in declared software.

## Decision Gate A — Provider authority

A provider cannot become production-authoritative until:

- licensed public/private benchmark reports exist,
- quality thresholds are reviewed,
- native dependency and packaging obligations pass,
- human DJ review is recorded,
- persistence/rollback compatibility is proven.

The desktop UI may expose the baseline provider as experimental/local evidence before this gate, but it must display its provider/version/warnings and must not claim parity with a commercial analyzer.

## Post-MVP candidates

Only after Bundle 54:

- rekordbox XML,
- Traktor NML,
- advanced/licensed provider rollout,
- cue/phrase/section research,
- library filesystem monitoring,
- OneLibrary-compatible integration,
- additional platforms and stores,
- optional remote/browser service mode.

## Stop list through Bundle 54

- cloud accounts and synchronization,
- streaming-service catalog dependence,
- market popularity scoring,
- mobile clients,
- live performance engine,
- stems,
- waveform/beatgrid editor,
- generative AI chat as primary surface,
- automatic live mixing,
- proprietary DJ database reverse engineering,
- further composition authority abstractions without accepted product need.

## Release governance

Every bundle requires:

1. issue with named value and schema tree,
2. branch from exact canonical head,
3. smallest isolated diff,
4. applicable Python and/or frontend/Rust CI,
5. product acceptance evidence,
6. security and rollback statement,
7. documentation update when contracts change,
8. packaged smoke evidence for desktop-facing bundles.

A green unit-test count alone is never sufficient for a product-facing release claim.
