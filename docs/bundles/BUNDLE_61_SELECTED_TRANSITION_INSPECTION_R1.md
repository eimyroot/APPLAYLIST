# Bundle 61 — Selected Transition Inspection R1

## Canonical dependency

- base branch: `feature/bundle-0-bootstrap`
- exact base SHA: `72fd76f033d484a8fa093a6ba38f58b26c6ac782`
- issue: #141

## Purpose

Complete the R4 `selected transition inspection` capability without introducing transition recomputation, editor mutation, optimizer execution, filesystem authority or Personal DJ Model training.

## Authority chain

```text
explicit immutable PlaylistRevision
  -> pair_index
  -> source/target derived from immutable revision order
  -> TransitionEvidenceIndex
  -> integrity-verified persisted TransitionAssessment snapshot
  -> renderer-safe inspection DTO
```

The renderer never supplies source or target track IDs. It supplies only the exact immutable `revision_id` plus the adjacent `pair_index`. Pair identity is derived on the authenticated sidecar from the canonical revision ledger.

## Persisted evidence only

Bundle 61 never calls an MIR provider and never constructs a new TransitionAssessment. `TransitionEvidenceIndex` finds existing snapshots for the derived source/target pair. `MusicIntelligenceRepository.get_transition_snapshot()` verifies the stored payload digest before decoding the immutable assessment.

When no persisted snapshot exists, the response is explicit:

```text
state = missing
selected_snapshot_id = null
assessment = null
```

No fallback recomputation occurs.

When multiple context-bound snapshots exist, the existing index ordering is authoritative: `created_at DESC, snapshot_id DESC`. The first snapshot is selected deterministically while metadata for all bounded available snapshots remains visible.

## Renderer-safe projection

The inspection DTO may expose:

- exact revision and pair identity;
- safe track labels and lock flags;
- snapshot/context/version/digest metadata;
- compatibility vector;
- risk vector;
- cost vector;
- energy effect;
- candidate and preferred strategies;
- usable transition window;
- contextual projection;
- confidence;
- explanations and warnings;
- opaque evidence references.

It does not expose raw `payload_json`, filesystem paths, audio bytes, sidecar credentials, provider execution handles or write authority.

## Desktop boundary

- authenticated sidecar route: `/v1/playlist/transition/inspect`
- strict request keys: `revision_id`, `pair_index`
- dedicated Tauri command: `playlist_transition_inspect`
- dedicated capability: `main-transition-inspector`
- no native save dialog
- no filesystem write
- renderer CSP remains `connect-src 'none'`

## Immutable/non-authorized effects

The response hard-codes:

```text
personal_dj_model_training_authorized = false
production_activation_authorized = false
transition_recomputation_authorized = false
playlist_mutation_authorized = false
```

## Acceptance gates

- exact revision identity required;
- pair index must identify an adjacent edge;
- renderer cannot choose arbitrary source/target IDs;
- missing evidence stays explicit;
- stored evidence integrity is verified;
- full assessment projection is bounded and path-safe;
- inspection does not append playlist revisions;
- strict authenticated route tests;
- renderer authority tests;
- Desktop Rust rustfmt/check/test;
- Python 3.11/3.12 full CI;
- packaged sidecar proof on Ubuntu and macOS;
- PR Guard;
- zero unresolved review threads.

## Non-scope

- regeneration around locks;
- transition recomputation;
- changing preferred strategy;
- persisting human review decisions;
- audio read/hash;
- MIR/provider execution;
- optimizer rerun;
- playlist revision mutation;
- vendor export mutation;
- Personal DJ Model training;
- production activation;
- release/deploy/signing/notarization.

## Next dependency

Bundle 62 may implement the remaining R4 capability: bounded regeneration around explicit locks, while preserving immutable revision history and keeping the DJ in control.

`MERGE_AUTHORIZATION=NO`

`RELEASE_AUTHORIZATION=NO`

`DEPLOY_AUTHORIZATION=NO`
