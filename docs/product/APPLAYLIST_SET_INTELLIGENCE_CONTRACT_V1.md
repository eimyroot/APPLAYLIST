# APPLAYLIST Set Intelligence Contract v1

## Status

Proposed governed contract for the layer between Transition Intelligence and graph/path optimization.

This contract is intentionally defined after Music DNA and Transition Intelligence and before any set optimizer implementation.

It does not authorize merge, release, deployment, graph database adoption, vector database adoption, automatic live mixing, model promotion, cloud processing, or production effects.

## Product purpose

Transition Intelligence answers whether a bounded source region and target region can plausibly work together in a named context.

Set Intelligence answers a different question:

> Given the DJ's intent, the current set state, the available transition evidence and explicit constraints, what are the best next candidates and what sequence states should an optimizer explore?

The purpose of this layer is to prevent the future optimizer from becoming an opaque container for product semantics.

The optimizer must search over a domain model; it must not define that domain model.

## Position in the canonical pipeline

```text
Music DNA
    ↓
Music Segments
    ↓
TransitionAssessment edges
    ↓
PlaylistIntent
    +
PlaylistContext
    +
SequenceState
    +
SetPhase
    ↓
Set Intelligence candidate generation/ranking
    ↓
Top-N eligible next states
    ↓
bounded graph/path optimizer
    ↓
Explainable SetPlanRevision
```

## Core design rules

1. A set is not a chain of independently good pairwise transitions.
2. Pairwise transition quality is necessary but insufficient.
3. Hard constraints are applied before soft ranking.
4. Intent, context, phase, sequence history and transition evidence are versioned inputs.
5. Identical versioned inputs must produce deterministic candidate ordering.
6. No hidden mutable global state may influence ranking.
7. No renderer or optimizer may call a MIR provider directly.
8. Missing evidence remains missing; it is not replaced by invented neutral scores.
9. Human locks and explicit bans are stronger than model or heuristic preferences.
10. The graph is a domain model. A graph database is not required to implement it.
11. Vector search is optional future candidate-retrieval infrastructure, not a prerequisite for Set Intelligence v1.
12. The first optimizer should be bounded, inspectable and reproducible before it is sophisticated.

---

# 1. Terminology

## Track node

A canonical APPLAYLIST track identity with one or more immutable Music DNA revisions.

## Segment node

A bounded musical region belonging to an exact Music DNA revision.

## Transition edge

An immutable `TransitionAssessment` between a source segment and target segment under an explicit assessment/policy version.

## Set state

The current ordered selection plus all sequence-level facts required to make the next decision without reconstructing hidden state.

## Candidate

An eligible target track/segment and transition assessment that survives hard gates for the current intent/context/state.

## Set plan

An ordered, explainable sequence of track/segment decisions with exact input/version references.

---

# 2. Set intelligence identity

Every set-intelligence request must have an explicit identity.

```text
SetIntelligenceIdentity
├── set_request_id
├── contract_version
├── intent_version
├── context_version
├── sequence_state_version
├── transition_policy_version
├── ranking_policy_version
├── optimizer_policy_version | null
└── created_at
```

Rules:

- `contract_version` is explicit,
- policy versions are immutable identifiers,
- changing a weight, hard gate, tie-break rule or phase interpretation requires a new relevant policy version,
- an optimizer policy is optional for `recommend_next` because candidate ranking exists before path search,
- timestamps are provenance, not ranking inputs unless explicitly declared by policy.

---

# 3. PlaylistIntent

`PlaylistIntent` describes what the DJ wants to create.

It is comparatively stable across one set-planning session.

```text
PlaylistIntent
├── intent_id
├── intent_version
├── goal
├── target_duration_seconds | null
├── target_track_count | null
├── eligible_library_scope
├── required_track_ids[]
├── forbidden_track_ids[]
├── locked_positions[]
├── start_constraints
├── end_constraints
├── phase_plan[]
├── energy_trajectory
├── tempo_policy
├── harmonic_risk_policy
├── vocal_overlap_policy
├── style_policy
├── novelty_policy
├── repetition_policy
├── transition_strategy_policy
├── evidence_policy
├── ranking_weights
└── metadata
```

## Intent goal

Initial bounded vocabulary:

- `warm_up`
- `club_flow`
- `festival_arc`
- `peak_time`
- `afterhours`
- `closing`
- `style_bridge`
- `custom`

The goal is descriptive context. It must not silently inject undocumented weights.

## Eligible library scope

```text
EligibleLibraryScope
├── explicit_track_ids[] | null
├── collection_ids[] | null
├── include_tags[]
├── exclude_tags[]
└── scope_revision
```

Rules:

- scope is explicit and reproducible,
- an empty explicit scope is not equivalent to "all tracks",
- filesystem folder paths must not become generic decision authority,
- local host authority may resolve collections to canonical track IDs before entering Set Intelligence.

## Required and forbidden tracks

- forbidden tracks are hard exclusions,
- required tracks must be represented as plan obligations,
- a required track does not automatically mean it is eligible at every step,
- the optimizer must preserve future feasibility for unsatisfied required tracks when possible,
- an impossible required-track set must fail explicitly rather than silently dropping requirements.

## Locked positions

```text
LockedPosition
├── position_index | null
├── track_id
├── segment_id | null
├── transition_strategy | null
└── lock_version
```

Locks are human authority.

A search algorithm may plan around a lock but may not remove or move it unless a new intent revision changes the lock.

---

# 4. PlaylistContext

`PlaylistContext` describes where the planning process currently is.

It is not the same as `PlaylistIntent`.

```text
PlaylistContext
├── context_id
├── context_version
├── current_phase_id
├── current_position_index
├── elapsed_duration_seconds
├── remaining_duration_seconds | null
├── remaining_track_count | null
├── current_track_id | null
├── current_segment_id | null
├── current_energy_state | null
├── current_tempo_family | null
├── current_tonal_state | null
├── phase_progress
├── active_phase_overrides
└── context_evidence_refs[]
```

Rules:

- context is derivable from recorded state wherever possible,
- values that are not known remain null,
- context must not smuggle in unversioned user preferences,
- phase progress is normalized and deterministic from phase boundaries/plan state,
- current musical state references Music DNA/segment evidence rather than ad-hoc renderer values.

---

# 5. SetPhase

A good set has a trajectory through phases rather than one global target.

Initial phase vocabulary:

- `intro`
- `warmup`
- `groove`
- `lift`
- `peak`
- `afterglow`
- `closing`
- `custom`

A phase is a policy object, not just a label.

```text
SetPhase
├── phase_id
├── phase_type
├── ordinal
├── target_fraction_start
├── target_fraction_end
├── target_energy_band | null
├── target_tempo_band | null
├── desired_energy_direction | null
├── harmonic_risk_override | null
├── style_targets[]
├── style_avoid[]
├── preferred_transition_strategies[]
├── forbidden_transition_strategies[]
├── novelty_target | null
├── repetition_tolerance | null
├── candidate_limit_override | null
└── explanation_label
```

## Phase invariants

- phases are ordered,
- target fractions are bounded to `0.0..1.0`,
- phase ranges may touch but must not contradict declared ordering,
- a phase-specific hard constraint overrides a softer global preference,
- phase overrides cannot weaken explicit human bans/locks,
- phase interpretation is versioned.

---

# 6. Energy trajectory

Energy trajectory is sequence-level intent, not a single next-track target.

```text
EnergyTrajectory
├── trajectory_id
├── trajectory_version
├── control_points[]
├── interpolation_policy
├── tolerance_policy
└── contrast_events[]
```

```text
EnergyControlPoint
├── normalized_set_position
├── target_energy
├── tolerance
└── phase_id | null
```

Rules:

- an energy trajectory may rise, fall, plateau or deliberately contrast,
- local transition energy delta is evaluated against the future trajectory,
- a locally perfect energy match may rank below a slightly weaker local match when the latter preserves future trajectory feasibility,
- the optimizer must not rewrite Music DNA energy facts to make the trajectory easier to satisfy.

---

# 7. SequenceState

`SequenceState` is the complete immutable decision state for one point in the search.

```text
SequenceState
├── state_id
├── state_version
├── selected_steps[]
├── current_track_id | null
├── current_segment_id | null
├── used_track_ids[]
├── used_artist_history[]
├── used_label_history[]
├── used_style_history[]
├── used_transition_strategy_history[]
├── cumulative_duration_seconds
├── current_energy_state | null
├── current_tempo_family | null
├── satisfied_required_track_ids[]
├── remaining_required_track_ids[]
├── active_locks[]
├── phase_state
├── cumulative_objective_components
├── warnings[]
└── evidence_refs[]
```

## Selected step

```text
SetStep
├── order_index
├── track_id
├── segment_id
├── incoming_transition_id | null
├── chosen_strategy | null
├── phase_id
├── local_projection_score | null
├── sequence_contribution
├── explanation_codes[]
└── evidence_refs[]
```

## Sequence-state invariants

- a track may not appear twice unless duplicate use is explicitly allowed by intent policy,
- used-track history is canonical-ID based,
- selected-step order is contiguous,
- cumulative duration is derived from selected plan semantics and recorded transition policy,
- required-track satisfaction is explicit,
- state mutation creates a new state; an existing state is not edited in place,
- equivalent inputs must create equivalent normalized state content even if storage IDs differ.

---

# 8. Hard constraints

Hard constraints determine eligibility before ranking.

Examples:

- candidate track is forbidden,
- candidate duplicates an already-used track when repeats are disallowed,
- explicit locked-next track does not match candidate,
- required analysis evidence is missing,
- transition assessment is blocked in the active transition context,
- transition strategy is forbidden,
- tempo change exceeds hard maximum,
- minimum harmonic evidence/fit is not met when policy requires it,
- candidate makes a fixed future lock unreachable under bounded feasibility rules,
- target duration would be exceeded beyond declared tolerance,
- phase-specific hard policy is violated,
- candidate belongs to excluded scope,
- candidate has a known critical analysis warning rejected by evidence policy.

Rules:

- hard failures cannot be outweighed by soft scores,
- each rejection has a structured reason code,
- multiple hard failures may be retained for explanation,
- unknown evidence is not equivalent to a pass.

---

# 9. Soft preferences

Soft preferences rank candidates that already passed hard constraints.

Initial sequence-level dimensions may include:

```text
SetCandidateFeatures
├── transition_quality
├── phase_fit
├── energy_trajectory_fit
├── tempo_trajectory_fit
├── harmonic_policy_fit
├── style_fit
├── novelty_fit
├── repetition_penalty
├── artist_spacing_fit
├── label_spacing_fit
├── strategy_diversity_fit
├── required_track_progress
├── duration_fit
├── future_feasibility
└── uncertainty_penalty
```

Each dimension:

- is normalized under a named policy,
- may be unavailable when evidence is unavailable,
- has an explicit weight,
- has a structured explanation code,
- must not reinterpret raw Music DNA evidence.

---

# 10. Ranking policy

There is no universal set-candidate score.

```text
SetRankingPolicy
├── ranking_policy_id
├── ranking_policy_version
├── feature_weights
├── missing_feature_policy
├── uncertainty_policy
├── tie_break_policy
├── sequence_penalties
├── sequence_rewards
└── normalization_policy
```

## Missing feature policy

Allowed behaviors must be explicit, for example:

- exclude dimension and renormalize declared active weights,
- apply a documented uncertainty penalty,
- hard-block when the evidence policy requires the dimension.

It is forbidden to silently substitute `0.5` or any other invented neutral value.

## Tie-break policy

Tie-breaking must be deterministic.

Recommended v1 order after equal normalized score:

1. lower uncertainty,
2. lower operational/preparation cost,
3. stable canonical `track_id`,
4. stable `segment_id`,
5. stable `transition_id`.

Random tie-breaking is not allowed in reproducibility-sensitive planning.

---

# 11. Candidate contract

```text
SetCandidate
├── candidate_id
├── target_track_id
├── target_segment_id
├── transition_assessment_id
├── transition_context_id
├── phase_id
├── eligibility
├── blocked_reasons[]
├── feature_vector
├── score | null
├── confidence
├── rank
├── explanation_codes[]
├── evidence_refs[]
└── resulting_state_preview
```

Rules:

- blocked candidates carry no positive rank score,
- score is meaningful only with the ranking-policy and context versions,
- rank is assigned only among eligible candidates in the same candidate set,
- `resulting_state_preview` is a bounded deterministic projection, not an uncommitted mutable state object.

---

# 12. CandidateSet / recommend_next

The first public Set Intelligence operation is conceptually:

```text
recommend_next(
    intent,
    context,
    sequence_state,
    transition_edges,
    ranking_policy,
    candidate_limit,
) -> CandidateSet
```

```text
CandidateSet
├── candidate_set_id
├── input_fingerprint
├── intent_ref
├── context_ref
├── sequence_state_ref
├── transition_policy_ref
├── ranking_policy_ref
├── eligible_candidates[]
├── rejected_candidate_summary
├── generated_at
├── deterministic_ordering
└── warnings[]
```

## Determinism

For identical normalized inputs and policy versions:

- candidate eligibility must be identical,
- feature values must be identical,
- ranking must be identical,
- tie-break ordering must be identical,
- explanations must use the same structured reason codes.

Wall-clock time, process ID, filesystem ordering or hash-map iteration order must not influence ranking.

---

# 13. TransitionAssessment use

Set Intelligence consumes persisted/versioned TransitionAssessment edges.

It must not recompute raw MIR evidence inside the ranking loop.

A candidate edge is eligible only if:

- its source segment corresponds to the current state,
- its Music DNA revision refs are resolvable,
- its assessment/policy version is accepted by active Set Intelligence policy,
- required evidence is present,
- its transition context can be projected or mapped deterministically to the active phase/context.

## Context mapping

A SetPhase may derive a named TransitionContext configuration.

The mapping must be explicit and versioned:

```text
SetPhase
    ↓ phase_to_transition_context_policy_vN
TransitionContext
    ↓
ContextualTransitionProjection
```

Set Intelligence may consume the projection but may not pretend it is context-free truth.

---

# 14. Sequence-level reasoning

A candidate can be locally strong but globally weak.

Examples:

- excellent A→B transition, but B makes the required closing track unreachable under tempo policy,
- excellent harmonic transition, but it repeats the same artist too soon,
- excellent energy match now, but it overshoots the planned peak too early,
- strong next track, but it consumes the only viable bridge into a required style change,
- acceptable local edge that preserves several high-quality future branches and therefore outranks a brittle local maximum.

This is why Set Intelligence exists separately from Transition Intelligence.

---

# 15. Future feasibility

`future_feasibility` is a bounded planning feature, not an oracle.

Initial implementation may estimate feasibility using:

- number of eligible outgoing edges from resulting state,
- existence of paths toward unsatisfied required/locked tracks within bounded lookahead,
- remaining duration compatibility,
- remaining phase/energy compatibility,
- hard tempo-policy reachability,
- style-bridge availability.

Rules:

- feasibility horizon is explicit,
- search budget is explicit,
- inability to prove feasibility within the budget is not proof of impossibility unless the hard-gate algorithm is complete for that constraint,
- warnings distinguish `infeasible` from `not_proven_within_budget`.

---

# 16. Graph/path optimizer boundary

The optimizer receives normalized Set Intelligence states and candidate expansions.

It does not own:

- Music DNA semantics,
- TransitionAssessment calculation,
- hard-constraint definitions,
- phase semantics,
- ranking feature semantics,
- explanation wording authority,
- provider access,
- persistence authority outside its bounded result contract.

Conceptually:

```text
state_0
  ├── candidate A -> state_1A
  ├── candidate B -> state_1B
  └── candidate C -> state_1C

bounded search
  ↓
state_path_1
state_path_2
state_path_3
```

The optimizer chooses which valid state paths to explore.

Set Intelligence defines what a valid expansion means.

---

# 17. First optimizer recommendation

The first production-oriented optimizer SHOULD use deterministic bounded beam/lookahead search rather than introducing graph-database-specific or vector-database-specific architecture.

Suggested policy shape:

```text
BoundedSearchPolicy
├── beam_width
├── branching_limit
├── lookahead_depth
├── max_expanded_states
├── max_runtime_budget_ms | null
├── terminal_condition
├── path_objective_weights
├── tie_break_policy
└── policy_version
```

## Why bounded beam/lookahead first

- deterministic behavior is straightforward,
- memory and runtime are bounded,
- candidate explanations remain inspectable,
- it works directly over persisted TransitionAssessment adjacency,
- it can optimize beyond greedy one-step selection,
- it is easier to benchmark against greedy and legacy composition baselines,
- it does not commit the product to infrastructure that may not be necessary.

## Not a permanent algorithm mandate

Beam search is a recommended v1 implementation, not part of musical truth.

A later optimizer may use dynamic programming, A*, constrained shortest path, Monte Carlo methods or another bounded algorithm if it demonstrably improves product outcomes while preserving contract semantics and reproducibility requirements.

---

# 18. Storage boundary: graph domain != graph database

The domain is naturally a graph:

```text
MusicSegment node
    ↓
TransitionAssessment edge
    ↓
MusicSegment node
```

This does not require Neo4j or another graph database.

For v1, acceptable persistence may use existing repository/storage boundaries with indexes such as:

- source segment → eligible TransitionAssessment IDs,
- target segment → incoming TransitionAssessment IDs,
- transition ID → immutable assessment payload,
- Music DNA revision → segment IDs.

A graph database should be introduced only if measured product/storage/query requirements justify it.

The burden of proof is on added infrastructure.

---

# 19. Vector database boundary

Vector embeddings may later improve semantic or timbral candidate retrieval.

They are not required for v1 Set Intelligence because:

- TransitionAssessment already expresses decision-relevant edges,
- the first optimizer can search an explicit bounded candidate graph,
- semantic/timbral evidence is currently optional/provider-gated,
- vector similarity is not equivalent to transition suitability,
- adding a vector database before validated need increases operational and governance surface.

If vector retrieval is later introduced:

- embeddings are provider/version specific evidence,
- approximate nearest-neighbor retrieval is candidate generation only,
- retrieved candidates still pass hard constraints and Transition Intelligence,
- ANN similarity never becomes hidden authority.

---

# 20. Path objective

A full set path has sequence-level objective components.

```text
SetPathObjective
├── transition_quality_sum
├── trajectory_fit
├── phase_fit
├── diversity_fit
├── repetition_penalty
├── required_track_completion
├── duration_fit
├── strategy_balance
├── uncertainty_penalty
├── operational_cost_penalty
└── terminal_goal_fit
```

Rules:

- path objective weights are explicit,
- hard constraints are not path-objective penalties; they remove invalid paths,
- objective components remain inspectable,
- score magnitude has meaning only under an exact policy version,
- path score is not marketed as objective musical quality.

---

# 21. Alternative paths

Set Intelligence should preserve meaningful alternatives.

```text
SetPlanAlternatives
├── primary_plan
├── alternatives[]
└── distinction_reasons[]
```

Alternative plans should differ for a reason, for example:

- higher-energy route,
- safer harmonic route,
- more novel/style-diverse route,
- lower-preparation-cost route,
- different required-track placement,
- different peak timing.

Near-duplicate paths should not consume the alternative budget without an explicit reason.

---

# 22. Explainability contract

Explanations are structured before they are rendered as prose.

```text
SetDecisionExplanation
├── code
├── severity
├── decision_scope
├── feature
├── value | null
├── policy_ref
├── evidence_refs[]
└── message_params
```

Initial explanation codes may include:

- `phase_energy_match`
- `energy_peak_too_early`
- `tempo_trajectory_match`
- `transition_edge_strong`
- `transition_uncertainty_high`
- `artist_spacing_penalty`
- `label_spacing_penalty`
- `style_repetition_penalty`
- `novelty_target_match`
- `required_track_progress`
- `future_lock_preserved`
- `future_feasibility_low`
- `duration_target_preserved`
- `strategy_diversity_match`
- `hard_forbidden_track`
- `hard_required_evidence_missing`
- `hard_tempo_limit`
- `hard_locked_position_conflict`

An optional LLM may turn structured explanations into human-readable text.

It must not create new evidence, weights, policy decisions or hidden reasons.

---

# 23. SetPlanRevision

A generated plan is immutable by revision.

```text
SetPlanRevision
├── set_plan_id
├── revision
├── parent_revision | null
├── intent_ref
├── initial_context_ref
├── ranking_policy_ref
├── optimizer_policy_ref
├── transition_assessment_refs[]
├── music_dna_revision_refs[]
├── steps[]
├── path_objective
├── terminal_state
├── explanations[]
├── warnings[]
├── input_fingerprint
└── created_at
```

Rules:

- regenerate creates a new revision,
- reorder/replace/lock operations create a new revision or explicit edit overlay,
- old plans remain auditable,
- exact input references make a plan reproducible when the same policy/runtime remains available,
- export consumes an approved plan revision rather than live mutable state.

---

# 24. Human editing boundary

Human editing is not optimizer failure.

The product explicitly supports:

- lock,
- reorder,
- replace,
- ban,
- choose alternative transition strategy,
- move transition window when supported,
- regenerate before/after locks.

Human decisions become explicit product signals.

They do not rewrite Music DNA or TransitionAssessment history.

A later Personal DJ Model may learn ranking preferences from those events under a separate versioned contract.

---

# 25. Failure and partial-result contract

Set Intelligence must fail transparently.

Initial result states:

- `success`
- `partial`
- `no_eligible_candidate`
- `hard_constraints_unsatisfiable`
- `required_track_unreachable`
- `insufficient_transition_evidence`
- `search_budget_exhausted`
- `invalid_input`
- `policy_version_unsupported`

Rules:

- partial results carry explicit unmet obligations,
- `search_budget_exhausted` is not reported as mathematical infeasibility,
- no fallback silently weakens hard constraints,
- no hidden switch to legacy composition is permitted.

---

# 26. Security and authority boundary

Renderer-facing Set Intelligence DTOs may expose:

- canonical safe IDs,
- rank/score under named policy,
- bounded explanation codes/text,
- confidence,
- warnings,
- track display metadata already approved for renderer use.

They must not expose:

- filesystem paths as generic authority,
- sidecar secrets/nonces/ports,
- process IDs,
- database credentials,
- arbitrary SQL,
- raw provider payloads,
- raw exceptions,
- hidden model prompts,
- unrestricted repository mutation authority.

Set optimization is a decision service, not a privilege-escalation path.

---

# 27. Observability

The implementation should measure without leaking private library content.

Useful bounded metrics:

- candidate count before/after hard gates,
- rejection reason counts,
- ranking feature availability,
- average branching factor,
- expanded-state count,
- beam survival count,
- search termination reason,
- wall-clock duration,
- recommendation acceptance/replacement rate at product layer,
- policy/version identifiers.

Track titles, filesystem paths and user-private tags should not be required for infrastructure telemetry.

---

# 28. Benchmark strategy

The first Set Intelligence implementation must be compared against simpler baselines.

Required baselines should include:

1. legacy composition/scoring behavior,
2. greedy best-next candidate using Transition Intelligence only,
3. bounded lookahead/beam search using Set Intelligence.

Evaluation dimensions:

- hard-constraint satisfaction,
- deterministic reproducibility,
- trajectory fit,
- required-track completion,
- diversity/repetition behavior,
- runtime and memory,
- candidate/path explanation coverage,
- blinded DJ preference/acceptance where human evaluation is available.

A more complex optimizer is not promoted because it is more complex.

It must beat a simpler baseline on named product outcomes.

---

# 29. Acceptance gates for Set Intelligence v1

Before graph/path optimizer implementation is treated as product-ready, the Set Intelligence contract/runtime must prove:

- `PlaylistIntent` is explicit and versioned,
- `PlaylistContext` is separate from intent,
- `SetPhase` policy is explicit,
- `SequenceState` is immutable/reconstructable,
- hard constraints execute before soft ranking,
- candidate ranking is deterministic,
- tie-breaking is deterministic,
- missing evidence remains explicit,
- TransitionAssessment IDs/revisions are preserved,
- no MIR provider is called from candidate ranking,
- no filesystem-path authority leaks to renderer DTOs,
- Top-N `recommend_next` has regression fixtures,
- sequence-history penalties/rewards have regression fixtures,
- required/forbidden/locked track behavior has regression fixtures,
- phase/trajectory behavior has deterministic fixtures,
- no graph DB is required for correctness,
- no vector DB is required for correctness,
- search budgets and termination reasons are explicit,
- generated plans carry enough refs for audit/replay.

---

# 30. Minimum implementation slice after PR #112

The smallest safe runtime slice should implement, in order:

1. typed immutable `PlaylistIntent`,
2. typed immutable `SetPhase`,
3. typed immutable `PlaylistContext`,
4. typed immutable `SequenceState`,
5. deterministic hard-gate engine,
6. deterministic `SetCandidateFeatures`,
7. versioned ranking policy,
8. Top-N `recommend_next`,
9. fixtures for phase/history/required/forbidden/lock behavior,
10. evidence/receipt proving deterministic output.

Only after this slice is green should the graph/path optimizer be added.

---

# 31. First optimizer implementation slice

After Set Intelligence runtime is proven:

1. persist/index immutable TransitionAssessment adjacency,
2. implement bounded state expansion using `recommend_next`,
3. implement deterministic beam/lookahead search,
4. enforce max expanded states and branching limits,
5. produce primary path plus bounded alternatives,
6. record terminal/search reason,
7. emit `SetPlanRevision`,
8. benchmark against greedy and legacy baselines,
9. add human-readable explanation rendering,
10. expose through desktop only after backend boundaries are proven.

---

# 32. Explicit non-goals

Set Intelligence v1 is not:

- a graph database migration,
- a vector database migration,
- a generic recommender platform,
- a live DJ automation engine,
- an autonomous performance system,
- a cloud-only planning service,
- a generative-music system,
- a personal-model training system,
- a replacement for Transition Intelligence,
- a replacement for human editing,
- proof that one optimizer algorithm is permanently canonical.

---

# 33. Canonical architecture after this contract

```text
LOCAL AUDIO
    ↓
ANALYSIS TRUTH
    ↓
MUSIC DNA
    ↓
SEGMENTS
    ↓
TRANSITION INTELLIGENCE
    ↓
immutable TransitionAssessment edges
    ↓
SET INTELLIGENCE
    ├── PlaylistIntent
    ├── PlaylistContext
    ├── SetPhase
    ├── SequenceState
    ├── hard constraints
    ├── sequence-level features
    └── Top-N recommend_next
    ↓
BOUNDED GRAPH/PATH OPTIMIZER
    ↓
SetPlanRevision + alternatives
    ↓
EXPLAINABLE HUMAN EDITOR
    ↓
EXPORT
    ↓
EXPLICIT FEEDBACK
```

This separation is deliberate:

- Music DNA owns normalized musical facts,
- Transition Intelligence owns evidence-backed edge assessments,
- Set Intelligence owns sequence semantics and candidate eligibility/ranking,
- the optimizer owns bounded path search,
- the human owns final editorial authority.
