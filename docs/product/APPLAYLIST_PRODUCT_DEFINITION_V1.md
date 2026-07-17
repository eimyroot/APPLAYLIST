# APPLAYLIST Product Definition v1

## Status

Accepted target for the product-first roadmap. Bundle 41 does not change runtime behavior.

## Product statement

APPLAYLIST is a local-first DJ preparation application that turns a selected local music library into an explainable, editable and interoperable DJ set.

The product must help a DJ move from audio files to a playable set:

```text
select local library
-> import track metadata
-> analyze musical evidence
-> build a constrained set
-> inspect and edit transitions
-> export to an existing DJ workflow
```

## Primary user

The first release targets a working DJ who:

- owns or controls local audio files,
- prepares sets before a performance,
- understands BPM and harmonic mixing,
- wants automation without surrendering final control,
- already uses software such as rekordbox, Traktor, Serato or Mixxx,
- needs a reliable playlist rather than an automatic live-mixing system.

## Core problem

Existing DJ platforms are strong at library management, performance and hardware integration. APPLAYLIST must not reproduce those products.

Its focused problem is:

> Produce a musically defensible starting set from real local tracks, explain why each transition was selected, let the DJ correct it quickly, and export the approved order safely.

## Product promise

For a selected folder of supported audio files, APPLAYLIST will:

1. import each supported file with stable identity and metadata,
2. analyze BPM, key/Camelot, energy and duration with quality evidence,
3. reject or visibly flag incomplete and invalid analysis,
4. compose a deterministic set under explicit constraints,
5. display transition reasons and warnings,
6. preserve manual edits,
7. export only tracks with valid existing paths.

## Product principles

### Human authority

The DJ is the final authority. Automatic composition produces a proposal, never an irreversible result.

### Evidence before confidence

BPM, key and energy values must include provider/version provenance, confidence where available, and warnings when uncertain.

### Local-first

The first release operates on local audio files and a local database. Cloud accounts and remote synchronization are outside the MVP.

### Interoperability

APPLAYLIST exports into existing DJ ecosystems. It does not require the DJ to abandon their current performance software.

### Determinism

The same library snapshot, constraints and engine version must produce the same initial result.

### Fail closed for data quality

Invalid paths, NaN/inf values, malformed keys and fake provider success must never silently enter an exported playlist.

## MVP user journey

### 1. Import

The user selects one explicit folder. APPLAYLIST performs a bounded scan and displays imported, skipped and failed files.

### 2. Analyze

The user starts analysis for new or changed tracks. Progress and controlled errors are visible.

### 3. Inspect

The library shows at minimum:

- title and artist,
- source path,
- duration,
- BPM and confidence,
- key and Camelot,
- energy,
- provider and analysis version,
- warning/error state.

### 4. Build set

The user chooses:

- target track count or target duration,
- BPM range,
- composition mode/energy curve,
- optional genres,
- optional start key,
- maximum transition constraints.

### 5. Edit

The user can reorder, remove, lock and replace tracks and regenerate a selected section.

### 6. Export

The approved result is exported as M3U8 with a machine-readable manifest and path-integrity evidence.

## MVP Definition of Done

The MVP is complete only when a clean installation can demonstrate this end-to-end flow with real local files:

- an explicit folder is imported,
- supported files receive stable track records,
- BPM, key/Camelot, energy and duration are produced by a real provider,
- no provider returns `stub` or fake success,
- analysis is normalized and persisted outside the provider,
- canonical composition respects source scope and user constraints,
- transition reasons are visible,
- the playlist can be manually edited,
- every exported path exists,
- the M3U8 opens successfully in at least one supported DJ application,
- the complete flow has a documented smoke test,
- Python 3.11 and 3.12 CI remains green.

## Explicit non-goals before MVP

- live DJ performance or audio playback,
- automatic live mixing,
- stems generation,
- waveform or beatgrid editing,
- streaming-catalog integration,
- cloud sync and multi-user accounts,
- mobile applications,
- generative chat as the primary UI,
- reverse engineering proprietary DJ databases,
- additional authority, receipt or governance abstractions without a product requirement.

## Success metrics

### Technical

- 100% exported-path integrity,
- deterministic composition for an unchanged snapshot,
- zero invalid numeric values persisted,
- controlled failures instead of optional-provider startup crashes.

### Product

- first set created from a local folder without manual database work,
- a DJ can identify why each transition was selected,
- a DJ can correct a weak transition without rebuilding the full set,
- exported order is usable in an existing DJ workflow.

## Release sequence

The product-first sequence is:

```text
product baseline
-> bounded library import
-> metadata and identity
-> analysis jobs
-> real baseline provider
-> MIR benchmark decision
-> desktop library UI
-> analysis inspector
-> set builder/editor
-> M3U8 vertical-slice release
```

Any new proposal must state which step it advances and how its completion will be verified by a user-visible outcome.