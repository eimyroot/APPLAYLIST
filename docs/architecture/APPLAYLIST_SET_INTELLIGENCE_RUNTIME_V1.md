# APPLAYLIST Set Intelligence Runtime v1

## Status

Implementation note for the first runtime slice of `APPLAYLIST_SET_INTELLIGENCE_CONTRACT_V1`.

This slice is stacked on Bundle 51 Transition Intelligence and does not authorize merge, release, deployment, graph database adoption, vector database adoption, cloud processing, or production effects.

## Runtime position

```text
Music DNA
  -> TransitionAssessment
  -> PlaylistIntent + PlaylistContext + SequenceState
  -> recommend_next v1
  -> deterministic eligible Top-N
  -> future bounded optimizer
```

## Delivered runtime types

`core/intelligence/set_contract.py` provides immutable, path-free contracts for:

- `PlaylistIntent`,
- `EligibleLibraryScope`,
- `LockedPosition`,
- `SetPhase`,
- `EnergyTrajectory`,
- `PlaylistContext`,
- `SetStep`,
- `SequenceState`,
- `CandidateDescriptor`,
- `SetCandidateFeatures`,
- `SetRankingPolicy`,
- `SetCandidate`,
- `CandidateSet`,
- deterministic result previews.

## Delivered operation

`services/intelligence/set_engine.py` provides:

```text
recommend_next(
  intent,
  context,
  sequence_state,
  transition_edges,
  ranking_policy,
  candidate_limit,
  generated_at,
) -> CandidateSet
```

The operation:

1. validates intent/context/state consistency,
2. sorts transition inputs into canonical deterministic order,
3. applies hard gates before scoring,
4. derives only features supported by available evidence,
5. excludes unavailable soft features and renormalizes declared weights under the v1 policy,
6. ranks eligible candidates deterministically,
7. applies stable tie-breaking,
8. returns bounded Top-N plus explicit rejected candidates and warnings.

## Hard-gate semantics implemented

The v1 runtime blocks candidates for:

- source track/segment mismatch,
- forbidden track,
- duplicate track when repeats are disabled,
- explicit library-scope exclusion,
- missing tag evidence when tag scope is a hard condition,
- required include-tag mismatch,
- excluded tag presence,
- fixed next-position lock mismatch,
- no transition strategy surviving active phase bans,
- blocked Transition Intelligence projection,
- unscored transition projection with no explicit block reason,
- known critical analysis warnings when rejected by intent,
- target-duration hard overflow.

A hard-blocked candidate has no score and no rank.

## Soft features implemented

The first ranking projection can use:

- Transition Intelligence contextual projection,
- phase fit from available target-energy/style evidence,
- energy-trajectory fit,
- harmonic fit,
- style fit where metadata evidence is supplied,
- novelty/repeat state,
- required-track progress,
- duration fit,
- Transition Intelligence uncertainty.

The following remain explicitly unavailable in this slice rather than being invented:

- absolute tempo-trajectory fit when target tempo evidence is not supplied through a governed normalized contract,
- artist-spacing fit,
- bounded future-feasibility lookahead.

`future_feasibility_not_evaluated_v1` is emitted when ranked candidates do not yet carry lookahead evidence.

## Determinism

The input fingerprint excludes `generated_at` and is built from normalized intent, context, sequence state, sorted candidate descriptors, ranking policy and candidate limit.

For equal normalized inputs:

- eligibility is stable,
- feature projection is stable,
- score ordering is stable,
- Top-N ordering is stable,
- reason codes are stable.

Tie-breaking after equal score is:

1. lower uncertainty,
2. lower available transition operational/preparation cost,
3. canonical target `track_id`,
4. canonical target `segment_id`,
5. canonical transition ID.

No wall clock, process ID, filesystem enumeration order, random source or hash-map iteration order participates in ranking.

## Seed boundary

`recommend_next v1` intentionally requires a seeded current track and segment.

The first-track problem is not represented by a TransitionAssessment edge and therefore is not silently fabricated as one.

A later governed slice may add explicit set-start candidate generation under start constraints. Until then, callers must seed a valid initial `SequenceState`.

## Persistence boundary

This runtime is in-memory/domain-only.

It does not yet implement:

- `TransitionAssessment` persistence,
- `SequenceState` persistence,
- `CandidateSet` persistence,
- adjacency indexes,
- optimizer checkpoint persistence.

Those are independent storage-authority changes and should be implemented only after exact runtime behavior is verified.

## Optimizer boundary

No beam search, graph search, A*, dynamic programming or path optimizer is included here.

The next optimizer must consume the deterministic state-expansion semantics established by `recommend_next`; it must not redefine hard constraints or scoring semantics.

## Infrastructure boundary

There is no Neo4j, graph database, vector database or ANN dependency in this slice.

The graph remains a domain relationship:

```text
SequenceState
  -> eligible SetCandidate
  -> resulting state preview
```

A storage engine remains an implementation detail until measured requirements justify otherwise.

## Verification focus

Regression tests cover:

- input-order-independent deterministic ranking,
- stable tie-breaking,
- required-track progress,
- forbidden/locked/repeat hard gates,
- missing scope evidence fail-closed behavior,
- propagation of Transition Intelligence hard blocks,
- duration hard limits,
- bounded candidate limits,
- explicit seeded-state boundary,
- required-track state reconciliation.

## Next governed slice

After this runtime is reconciled and merged through the normal authorization boundary:

1. persist immutable TransitionAssessment adjacency,
2. persist/reconstruct normalized SequenceState,
3. add bounded future-feasibility lookahead,
4. benchmark greedy `recommend_next` against bounded beam/lookahead,
5. only then introduce the first graph/path optimizer runtime.
