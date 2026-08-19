# Bundle 57 — Governed Manual Editor Revisions R1

## Status

Implementation slice for Issue #133. This document does not authorize merge, release, deploy, production optimizer activation, export, or Personal DJ Model training.

Exact base: `61b6cadd56adc841db8725265293e4e032feb768` on `feature/bundle-0-bootstrap`.

## Purpose

Bundle 56B made Set Proposal inspection real in the desktop application. Bundle 57 adds the first governed human-edit boundary:

```text
verified Set Proposal
  -> explicit accept
  -> immutable root PlaylistRevision
  -> explicit reorder / lock / replace
  -> immutable child PlaylistRevision
  -> inspectable revision history
```

No existing revision is mutated or deleted.

## Canonical authority

`PlaylistRevisionRepository` is the sole persistence authority for the editor revision ledger.

SQLite uses two append-only tables:

- `playlist_revisions`
- `playlist_revision_items`

Database triggers reject `UPDATE` and `DELETE` on both tables. Each child stores one `parent_revision_id` and increments `revision_index` inside `BEGIN IMMEDIATE` optimistic-concurrency transactions.

## Root acceptance

The renderer is not trusted to supply the authoritative proposal sequence.

`accept` carries:

- original bounded proposal track scope,
- seed track,
- target track count,
- expected proposal ID,
- selected path ID.

The authenticated sidecar performs one deterministic evidence-only Bundle 56B proposal replay. Acceptance proceeds only when proposal and path identity still match current evidence.

If analysis evidence or an active correction changed after the proposal was displayed, acceptance fails closed as `playlist_proposal_stale`.

The replay does not read/hash audio, invoke a MIR provider, or persist optimizer/transition state.

## Child operations

### reorder

- exact current revision required,
- exact track membership preserved,
- duplicates rejected,
- locked tracks must retain their exact positions,
- no-op rejected.

### lock

- exact current revision required,
- full lock set is explicit,
- only current members may be locked,
- ordering and membership are unchanged,
- no-op rejected.

### replace

- exact current revision required,
- source must be a current unlocked member,
- target must not already be present,
- target must exist in the local TrackRepository,
- latest analysis attempt must be the current successful evidence,
- required duration/BPM/energy/provider-version/algorithm-version evidence must exist,
- replacement preserves the source position,
- no audio or provider execution occurs.

No child operation reruns the optimizer.

## Deterministic identity and idempotency

Root `playlist_id` derives from proposal ID + accepted path ID.

Every `revision_id` derives from a SHA-256 content fingerprint over:

- playlist identity,
- parent revision,
- source proposal/path,
- operation type,
- ordered track IDs and safe labels,
- lock state,
- bounded operation metadata,
- explicit false training/activation authorities.

An exact retry returns the already-existing identical revision. A different child request against a stale parent fails closed.

## Renderer boundary

Renderer-safe revision DTO schema:

`applaylist-desktop-playlist-revision-r1`

History DTO schema:

`applaylist-desktop-playlist-history-r1`

Renderer receives only:

- stable playlist/revision/proposal/path IDs,
- revision lineage/index/operation,
- SHA-256 content fingerprint,
- created-at evidence,
- ordered stable track IDs,
- safe display labels,
- lock state,
- explicit false authority flags.

Renderer never receives filesystem paths, provider internals, AnalysisEvidence IDs, sidecar credentials, raw operation JSON, or raw domain/repository objects.

## Desktop security

New commands:

- `playlist_editor_accept`
- `playlist_editor_reorder`
- `playlist_editor_lock`
- `playlist_editor_replace`
- `playlist_editor_history`

They are isolated in `main-playlist-editor` capability.

Rust request bounds and nested `deny_unknown_fields` response parsing are fail closed. The existing loopback secret + readiness nonce + packaged executable lifecycle remains unchanged.

The renderer observes successful `set_proposal_generate` calls only to offer explicit acceptance choices. It passes the proposal result through unchanged; authoritative acceptance is still sidecar replay verified.

## Training boundary

Manual edits are explicit human evidence but Bundle 57 does **not** feed them into Personal DJ Model training.

Every revision and history response contains:

```text
personal_dj_model_training_authorized=false
production_activation_authorized=false
```

Preference learning remains a later governed slice.

## Rollback

Code rollback removes the Bundle 57 transport, sidecar extension, Tauri commands/capability and renderer surface.

Existing append-only revision rows are evidence and must not be destructively deleted as part of code rollback.

## Non-scope

- M3U/M3U8 export,
- rekordbox XML,
- Traktor NML,
- destructive undo/history rewrite,
- implicit preference learning,
- Personal DJ Model training,
- optimizer rerun for child editor operations,
- new MIR/provider work,
- audio reads,
- production activation,
- release/deploy/signing/notarization.

## Next dependency

Bundle 58 — interoperability/export from one explicitly selected approved `PlaylistRevision`.
