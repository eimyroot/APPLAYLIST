# APPLAYLIST Bundle 52 — Set Path Optimizer v1

## Status

First governed graph/path optimizer slice after canonical R2.5 reconciliation.

Canonical base at implementation start:

`e03300f990c4da9237516174377d1b2d7ce150ab`

This slice does not authorize merge, release, deployment, graph database adoption, vector database adoption, renderer/Tauri exposure, or automatic set acceptance.

## Product boundary

The optimizer is a sequence-search layer, not a second music-scoring system.

```text
Music DNA
  -> TransitionAssessment
  -> persisted context-specific adjacency
  -> Set Intelligence recommend_next
  -> deterministic bounded beam/lookahead
  -> Top-K SetPathAlternative
  -> human decision
```

`TransitionAssessment` remains the only pairwise musical transition assessment.

`recommend_next` remains the single authority for candidate hard gates and Set Intelligence candidate scoring.

The optimizer only decides which already-evaluated next-state expansions to keep across a bounded sequence horizon.

## Graph model

The graph is the persisted domain relation:

```text
(track, segment, explicit TransitionContext)
            |
            v
persisted TransitionAssessment snapshot
            |
            v
(target track, target segment)
```

No Neo4j, graph DB, vector DB, embeddings, or cloud planner is needed for optimizer correctness.

SQLite adjacency from `MusicIntelligenceRepository.list_outgoing()` is sufficient for v1.

## Search algorithm

V1 uses deterministic layer-by-layer bounded beam search.

Policy contract:

```text
SetOptimizerPolicy
├── beam_width                1..128
├── max_depth                 1..16
├── per_state_candidate_limit 1..256
├── max_expanded_candidates   1..100000
└── alternative_limit         1..beam_width
```

Each frontier state:

1. derives the current SetPhase from target track-count or duration position,
2. maps that phase to an explicit TransitionContext,
3. loads only persisted outgoing assessments for that exact context,
4. attaches explicit duration/style/warning evidence,
5. invokes `recommend_next`,
6. expands only eligible ranked candidates,
7. records immutable path/state provenance,
8. sorts deterministically,
9. retains at most `beam_width` children.

## Deterministic beam priority

V1 beam ordering is explicit and versioned by the optimizer policy.

Priority is lexicographic:

1. target reached,
2. fewer remaining required tracks,
3. greater required-track completion,
4. greater mean SetCandidate score,
5. greater minimum SetCandidate score,
6. transition-id path ordering,
7. track/segment path ordering.

There is no hidden universal path score.

The objective object exposes the evidence used by the ordering:

```text
SetPathObjective
├── depth
├── mean_candidate_score
├── minimum_candidate_score
├── required_track_completion
├── remaining_required_count
└── target_reached
```

## Global constraints

The optimizer does not duplicate hard-gate logic.

At every expansion `recommend_next` continues to enforce, among other existing rules:

- source track/segment consistency,
- forbidden tracks,
- repeat policy,
- explicit library scope,
- scope tag evidence,
- locked next positions/segments/strategies,
- phase-forbidden transition strategies,
- TransitionAssessment projection blocks,
- critical analysis warning policy,
- target-duration ceiling.

The optimizer itself additionally stops expansion at explicit set target boundaries and does not claim a completed target while required tracks remain unresolved.

## Phase-aware context

Unlike the R2.5 future-feasibility evaluator, the optimizer derives a fresh phase-scoped TransitionContext at every search depth.

This allows a path such as:

```text
phase-1 context: A -> B
phase-2 context: B -> C
```

without silently reusing the phase-1 transition projection after the phase boundary.

Persisted adjacency must exist for the exact derived phase context. Missing adjacency is not fabricated.

## Future-feasibility boundary

R2.5 `evaluate_future_feasibility()` currently evaluates one fixed TransitionContext over its whole horizon.

For that reason Bundle 52 v1 deliberately does **not** use it as a hard beam prune across a multi-phase path. Doing so could incorrectly eliminate a path that becomes valid under a later phase context.

The feasibility layer remains valid as an independent proof tool and as a future optimizer input after a phase-aware feasibility contract exists.

This is an explicit correctness decision, not a missing integration hidden behind a default.

## Evidence completeness

Path expansion requires target duration evidence because SequenceState duration must remain truthful.

If a persisted outgoing edge lacks target duration evidence:

- that edge is not fabricated or assigned a default duration,
- the run records `missing_evidence_detected=true`,
- if no path can be established, result status is `NOT_PROVEN_MISSING_EVIDENCE`, not a false `NO_ELIGIBLE_PATH`.

Missing optional style evidence remains governed by existing Set Intelligence rules.

## Result contract

```text
SetOptimizerResult
├── input_fingerprint
├── optimizer_ref
├── intent_ref
├── root_state_ref
├── base_transition_context_ref
├── status
├── alternatives[]
├── deepest_depth
├── expanded_candidates
├── beam_pruned_candidates
├── budget_exhausted
├── missing_evidence_detected
├── deterministic_ordering
├── explanation_codes
└── warnings
```

Statuses:

- `TARGET_REACHED`
- `PATHS_FOUND`
- `NO_ELIGIBLE_PATH`
- `NOT_PROVEN_MISSING_EVIDENCE`
- `BUDGET_EXHAUSTED`

Every alternative contains concrete added SetSteps, resulting SequenceState, transition IDs, candidate scores, path objective, explanation codes and evidence refs.

## Determinism

For identical:

- persisted adjacency,
- PlaylistIntent,
- root PlaylistContext,
- root SequenceState,
- base TransitionContext,
- SetRankingPolicy,
- SetOptimizerPolicy,
- track-duration/style/warning evidence,

the optimizer returns identical path ordering and result identity.

No wall-clock time is used in path ranking or identity.

`generated_at` is forwarded only to the existing CandidateSet evidence contract.

## Human authority

Optimizer output is a recommendation set, not an accepted playlist.

No path is automatically published, exported, played, written into a DJ library, or treated as user preference evidence.

Human edit/acceptance remains downstream.

## Explicit non-goals

- no Neo4j or other graph DB,
- no vector DB,
- no embeddings,
- no LLM planning authority,
- no new MIR provider,
- no TransitionAssessment semantic change,
- no SetRankingPolicy activation change,
- no Personal DJ Model training,
- no renderer/Tauri surface,
- no auto-export,
- no release/deploy,
- no automatic merge.

## Next hardening after v1

Before any broader optimizer activation:

1. benchmark beam widths and lookahead depths against curated DJ sequences,
2. add phase-aware future-feasibility if evidence shows it improves path quality,
3. benchmark greedy baseline vs bounded beam,
4. add explicit alternative-path diversity metrics,
5. persist accepted SetPlan revisions separately from search candidates,
6. only then consider Personal DJ Model influence as another explicit versioned context signal.
