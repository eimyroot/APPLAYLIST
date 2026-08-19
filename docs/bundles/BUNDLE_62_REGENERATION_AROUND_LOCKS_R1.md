# Bundle 62 — Regeneration Around Locks R1

Status: governed implementation slice
Issue: #143
Canonical dependency: `f5747ee01a413cecac208d7051dce21fee6958ad`

## Purpose

Bundle 62 closes the remaining R4 manual-editor gap: regenerate the unlocked part of one exact current immutable `PlaylistRevision` while preserving explicit DJ locks and appending a new immutable child revision.

```text
current PlaylistRevision
  + explicit analyzed candidate pool
  + persisted lock positions
  -> bounded Set Intelligence preview
  -> human path selection
  -> exact deterministic replay
  -> immutable child revision(operation=regenerate)
```

## R1 anchor boundary

R1 deliberately requires playlist position `0` to be locked. The existing Set Intelligence runtime is seeded from one actual track, so this restriction avoids inventing a synthetic pre-set root or a second path-search authority.

Additional locks are represented by the canonical `LockedPosition(position_index=...)` contract and remain hard constraints in the existing bounded optimizer.

A later governed slice may consider unanchored first-position regeneration only if the Set Intelligence contract gains an explicit neutral-root model.

## Authority model

The renderer may choose only:

- the exact current revision,
- a bounded explicit candidate pool of 3–24 already analyzed tracks,
- one renderer-safe preview path.

The renderer may not submit pairwise transition scores, filesystem paths, MusicDNA payloads, MIR results, optimizer scores, or arbitrary output sequences.

The sidecar reconstructs candidate MusicDNA from current persisted AnalysisEvidence/corrections, creates request-local `TransitionAssessment` objects, and calls the existing bounded Set Intelligence optimizer. These transient assessments are not persisted as canonical transition evidence.

## Preview

`/v1/playlist/editor/regeneration/preview` requires:

- exact current `revision_id`,
- unique candidate track IDs,
- all persisted locked tracks present in the candidate pool,
- position 0 locked.

The deterministic identity binds:

- parent revision ID,
- parent content fingerprint,
- sorted candidate pool,
- exact locked positions,
- regeneration policy version,
- current analysis/correction revisions through the optimizer result identity.

The renderer-safe response exposes only IDs, display labels, locks, bounded objective data, explanation/warning codes, and authority-false flags.

## Apply

`/v1/playlist/editor/regeneration/apply` additionally requires the expected `regeneration_id` and selected `path_id`.

Apply reruns the full preview from the current persisted state. A changed revision, lock, candidate pool, analysis result, or active correction invalidates the prior identity/path and fails closed.

Successful apply appends exactly one child `PlaylistRevision` with:

- `operation = regenerate`,
- parent revision lineage,
- selected path/rank,
- candidate-pool count + SHA-256,
- exact locked-position provenance,
- deterministic content fingerprint,
- Personal DJ Model training = false,
- production activation = false.

No in-place playlist mutation exists.

## Revision-ledger compatibility

Bundle 57 originally constrained SQLite revision operations to `accept`, `reorder`, `lock`, and `replace`. Bundle 62 adds a bounded compatibility migration that rebuilds only the revision header table with `regenerate` added to the CHECK constraint, copies existing rows, restores append-only triggers/indexes, re-enables foreign keys, and executes `PRAGMA foreign_key_check`.

Existing revision items and their immutable triggers remain unchanged.

## Desktop boundary

Dedicated Tauri commands:

- `playlist_editor_regeneration_preview`
- `playlist_editor_regeneration_apply`

Dedicated capability:

- `main-playlist-regeneration`

The command surface has no filesystem, shell, HTTP, save-dialog, release, deployment, or provider capability. The sidecar remains authenticated by the packaged loopback secret/readiness-nonce lifecycle.

The Manual Set Editor exposes the candidate pool explicitly. Current members start selected, locked tracks cannot be deselected, and additional successfully analyzed tracks may be added up to the bounded maximum.

## Cross-feature continuity

Regenerated immutable revisions remain valid inputs for:

- revision history,
- Selected Transition Inspection,
- M3U8 export,
- JSON evidence export,
- vendor interoperability handoff.

Those consumers accept `regenerate` as a revision-history operation while keeping their existing read/write authority boundaries.

## Fail-closed conditions

Examples include:

- stale/non-current revision,
- missing first-position lock,
- locked track omitted from candidate pool,
- duplicate/out-of-bounds candidate pool,
- missing/failed/incomplete current analysis evidence,
- invalid renderer projection,
- replay identity mismatch,
- selected path no longer present,
- no-op regeneration,
- malformed or authority-escalating sidecar response.

## Explicit non-scope

- moving locked positions,
- segment-level/strategy lock editing,
- unanchored position-0 regeneration,
- persisting transient regenerated transition assessments as canonical evidence,
- audio read/hash,
- MIR/provider execution,
- Human DJ Review execution,
- Personal DJ Model training,
- production activation,
- release/deploy/signing/notarization.

## Next dependency

After Bundle 62 is merged and independently green, R4 can proceed to the already-prepared **Human DJ Review execution** and aggregation/governance decision. That boundary requires separate authorization and is not implied by this bundle.
