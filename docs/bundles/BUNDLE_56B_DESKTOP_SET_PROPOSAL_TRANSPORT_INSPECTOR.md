# Bundle 56B — Desktop Set Proposal Transport + Inspector R1

## Status

Implementation slice for issue #130.

Base branch: `feature/bundle-0-bootstrap`  
Exact base SHA: `32e15a38696839b1e684892611e4f8ce9bd7ce4d`

This bundle does not authorize merge, release, deployment, optimizer production activation, playlist mutation, or Personal DJ Model training.

## Product outcome

A DJ can load already-successfully analyzed local tracks, choose a seed and a bounded target track count, and inspect ranked explainable set alternatives directly in the desktop application.

No terminal or CSV handoff is required.

## Canonical flow

```text
renderer selected stable track IDs
  -> set_proposal_generate
  -> trusted Rust host
  -> authenticated packaged sidecar
  -> DesktopSetProposalTransport
  -> persisted successful AnalysisEvidence + active correction overlay
  -> path-free MusicDNA
  -> canonical TransitionAssessment
  -> canonical balanced Set Intelligence ranking
  -> canonical bounded beam/lookahead optimizer
  -> Bundle 56 renderer-safe projection
  -> Set Proposal Inspector
```

## Bounds

- selected scope: 3–24 unique stable track IDs,
- seed track must be inside the selected scope,
- target track count: 3–8 and no larger than the selected scope,
- one explicit `GROOVE` preview phase,
- neutral hold-current-energy trajectory seeded from persisted energy evidence,
- maximum three rendered alternatives,
- bounded beam width 8,
- bounded maximum depth 2–7,
- bounded expanded candidate budget 2,048.

## Evidence-only authority

The transport reads:

- `TrackRepository` display metadata,
- latest analysis attempt,
- latest successful `AnalysisEvidence`,
- active correction anchored to that exact successful evidence.

The transport does **not**:

- open an audio path,
- hash or read audio bytes,
- invoke `RoutedAnalysisService`,
- invoke an MIR provider,
- mutate provider evidence,
- persist `TransitionAssessment`,
- persist `SequenceState`,
- persist a playlist revision.

A correction changes the effective MusicDNA analysis revision used for the proposal while the underlying provider evidence remains append-only and unchanged.

## Transient graph rule

Transition adjacency is request-local and in memory.

The canonical optimizer still owns path search and `recommend_next` remains the candidate eligibility/ranking authority. The transient repository is only a bounded `list_outgoing` adapter over canonical `TransitionAssessment` objects generated from persisted evidence.

## Sidecar integration

The existing packaged `applaylist-sidecar` executable remains the only packaged process boundary.

`scripts/applaylist_sidecar_entry.py` installs one narrow route extension before entering the existing canonical sidecar `main()`:

```text
POST /v1/set/proposal/generate
```

The route reuses the existing startup envelope, loopback binding, random secret, readiness nonce, health proof and shutdown lifecycle.

Unexpected request fields fail closed.

## Renderer projection

The renderer receives only Bundle 56 schema:

`applaylist-desktop-set-proposal-r1`

It may render:

- proposal ID,
- optimizer status,
- ranked alternatives,
- safe track display names and track IDs,
- phase IDs,
- transition IDs,
- candidate scores,
- objective summary,
- bounded reason / warning codes.

It never receives:

- filesystem paths,
- provider identities or versions,
- AnalysisEvidence IDs,
- optimizer input fingerprints,
- sidecar port / secret / nonce / PID,
- raw exceptions,
- raw domain objects.

`activation_authorized` and `personal_dj_model_training_authorized` must remain `false` through Python, Rust and renderer validation.

## Warning compatibility boundary

Canonical optimizer warnings currently include three human-readable internal warning strings. Bundle 56 accepts renderer-safe token codes only.

56B therefore performs an exact allowlisted trusted-side translation:

- bounded frontier prune -> `bounded_search_pruned_frontier`,
- missing duration evidence -> `candidate_duration_evidence_missing`,
- v1 future-feasibility limitation -> `future_feasibility_not_hard_prune_v1`.

Any unknown optimizer warning fails closed instead of passing arbitrary text to the renderer.

## Verification

Required before review-ready status:

- full Python CI on supported versions,
- set proposal transport tests,
- authenticated sidecar route proof,
- renderer contract tests,
- Desktop Sidecar Proof,
- Desktop Rust rustfmt/check/test,
- PR Guard,
- zero unresolved review threads.

The evidence-only regression fixture stores deliberately nonexistent audio paths. A successful proposal from that fixture proves this slice does not require audio reads.

## Non-scope

- accept / reject mutation,
- reorder,
- lock / unlock,
- replace,
- immutable playlist revision persistence,
- export,
- new analysis/provider work,
- audio reads,
- persistent graph storage,
- Human DJ Review completion,
- Personal DJ Model training,
- optimizer production activation,
- release/deploy/signing/notarization.

## Next dependency

Bundle 57 may add governed Manual Editor revision commands only after 56B transport and Inspector gates are proven.
