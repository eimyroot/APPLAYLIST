# APPLAYLIST Transition Intelligence Contract v1

## Status

Proposed Bundle 51 domain and decision contract.

This contract defines how APPLAYLIST represents an explainable transition between bounded musical regions. It does not authorize production provider promotion, automatic live mixing, audio rendering, release, or deployment.

## Product purpose

Transition Intelligence answers:

- which region of track B is compatible with a chosen region of track A,
- what kind of transition is musically plausible,
- what risks exist,
- how the transition changes the set trajectory,
- why one option ranks above another,
- how confident the system is and which evidence supports the decision.

The core entity is not a track-to-track scalar score. It is an immutable assessment of a source region, target region and context.

## Canonical graph model

```text
TrackAnalysis node
  -> MusicSegment
      -> TransitionAssessment edge
          -> MusicSegment
              -> TrackAnalysis node
```

The graph is append-only by assessment version. Re-analysis or a changed policy produces a new assessment revision rather than silently rewriting an old edge.

## Transition identity

```text
TransitionIdentity
├── transition_id
├── source_track_id
├── source_segment_id
├── target_track_id
├── target_segment_id
├── assessment_version
├── policy_version
├── music_dna_revision_refs
└── created_at
```

Invariants:

- source and target tracks must exist,
- source and target segments must belong to the referenced Music DNA revisions,
- assessment version is immutable,
- policy version is explicit,
- a transition may be reassessed without deleting historical evidence.

## TransitionAssessment

```text
TransitionAssessment
├── identity
├── compatibility_vector
├── risk_vector
├── cost_vector
├── energy_effect
├── candidate_strategies[]
├── preferred_strategy | null
├── usable_window
├── contextual_projection | null
├── confidence
├── explanations[]
├── evidence_refs[]
└── warnings[]
```

## Compatibility vector

```text
TransitionCompatibility
├── tempo_fit
├── beat_grid_fit
├── phrase_fit
├── harmonic_fit
├── groove_continuity
├── structural_fit
├── timbral_fit | null
├── melodic_fit | null
└── semantic_fit | null
```

Each dimension is normalized to a documented range and may be `null` when the required evidence is unavailable or not benchmarked.

A missing value must never be replaced by an invented neutral score.

## Risk vector

```text
TransitionRisk
├── bass_collision
├── vocal_collision
├── spectral_masking
├── loudness_discontinuity
├── harmonic_clash
├── phrase_mismatch
├── tempo_instability
├── transient_overload
└── uncertainty
```

Risk describes what can go wrong even when the pair is otherwise compatible.

A recommendation may therefore have high compatibility and high risk simultaneously.

## Cost vector

```text
TransitionCost
├── tempo_change_percent
├── time_stretch_cost
├── pitch_shift_semitones
├── key_shift_cost
├── loop_dependency
├── stem_dependency
├── effect_dependency
└── preparation_complexity
```

Cost captures operational effort or transformation needed to make the transition work.

The default local-first DJ preparation path should prefer low-cost transitions unless the active context says otherwise.

## Energy effect

```text
TransitionEnergyEffect
├── source_energy_state
├── target_energy_state
├── delta
├── local_curve_alignment
├── direction
└── confidence
```

`direction` may be:

- rise,
- hold,
- fall,
- contrast,
- uncertain.

The set optimizer uses the full energy representation, not only `delta`.

## Usable transition window

```text
TransitionWindow
├── source_start_ms
├── source_end_ms
├── target_start_ms
├── target_end_ms
├── source_bar_count | null
├── target_bar_count | null
├── preferred_entry_ms | null
├── preferred_exit_ms | null
├── confidence
└── evidence_refs[]
```

Rules:

- all times must be within track duration,
- start < end,
- bar/phrase alignment is evidence-backed,
- renderer-facing windows never expose local paths.

## Strategy taxonomy

Initial bounded strategy vocabulary:

- `long_blend`
- `short_blend`
- `eq_blend`
- `bass_swap`
- `cut`
- `drop_swap`
- `breakdown_transition`
- `loop_transition`
- `tempo_bridge`
- `half_double_time_switch`
- `stem_assisted`
- `deliberate_contrast`

Each candidate strategy contains:

```text
TransitionStrategyCandidate
├── strategy
├── suitability
├── required_capabilities[]
├── recommended_window
├── risks[]
├── costs[]
├── explanation_codes[]
└── evidence_refs[]
```

A strategy requiring stems, looping or other capability is ineligible when that capability is unavailable.

## Context contract

There is no universal overall transition score.

```text
TransitionContext
├── context_id
├── context_version
├── goal
├── desired_energy_direction
├── tempo_policy
├── harmonic_risk_policy
├── vocal_overlap_policy
├── groove_policy
├── novelty_policy
├── allowed_strategies[]
├── weights
└── hard_constraints[]
```

Example goals:

- preserve_groove,
- build_energy,
- reduce_energy,
- harmonic_long_blend,
- bridge_styles,
- create_contrast,
- peak_time,
- warm_up.

## Contextual projection

```text
ContextualTransitionProjection
├── context_id
├── context_version
├── score
├── rank_features[]
├── blocked_reasons[]
├── confidence
└── explanation_codes[]
```

Rules:

- the score is meaningful only with its context version,
- hard constraint failure blocks the candidate regardless of weighted score,
- no hidden weights,
- identical evidence + context + policy must yield deterministic output.

## Hard constraints vs soft preferences

### Hard constraint examples

- target track forbidden,
- insufficient transition window,
- tempo change exceeds allowed maximum,
- required analysis evidence missing,
- incompatible capability requirement,
- explicit user lock/ban.

### Soft preference examples

- prefer small energy rise,
- prefer harmonic continuity,
- prefer minimal vocal overlap,
- prefer 32-bar blend,
- prefer familiar style bridge.

A hard constraint cannot be outweighed by a high soft score.

## Explanation contract

Explanations are structured first and natural-language second.

```text
TransitionExplanation
├── code
├── severity
├── dimension
├── message_params
├── evidence_refs[]
└── confidence
```

Example explanation codes:

- `tempo_family_match`
- `phrase_alignment_strong`
- `harmonic_adjacent_key`
- `bass_collision_high`
- `vocal_overlap_low`
- `energy_rise_matches_goal`
- `target_window_short`
- `provider_disagreement`
- `human_correction_applied`

An optional LLM may render these codes into readable prose. It must not invent evidence or replace the deterministic assessment.

## Confidence aggregation

Transition confidence is derived from:

- source Music DNA confidence,
- target Music DNA confidence,
- segment-boundary confidence,
- provider disagreement,
- dimension-specific evidence coverage,
- transition-policy calibration evidence.

Unknown confidence is not zero and not one. It remains unknown/partial.

## Human review and feedback

A DJ can:

- accept transition,
- reject transition,
- choose an alternative strategy,
- move source/target window,
- rate compatibility,
- lock the transition into a set,
- replace the target track.

These actions create append-only feedback events.

They do not mutate the original TransitionAssessment.

## Transition feedback event

```text
TransitionFeedbackEvent
├── event_id
├── transition_id
├── action
├── actor
├── before_ref | null
├── after_ref | null
├── reason | null
├── created_at
└── session_context_ref | null
```

This event stream becomes input to the future Personal DJ Model.

## Set graph interface

Bundle 52 may consume Transition Intelligence only through a stable graph projection:

```text
TransitionGraphEdge
├── transition_id
├── source_node
├── target_node
├── context_projection
├── hard_constraint_state
├── energy_effect
├── strategy_summary
├── confidence
└── evidence_refs[]
```

The set optimizer does not call MIR providers directly.

## Fail-closed rules

Transition assessment must fail closed when:

- referenced track or segment does not exist,
- Music DNA revision is unavailable,
- required timing evidence is invalid,
- source/target window is out of range,
- policy/context version is unknown,
- unsupported strategy is requested,
- hard constraint input is malformed,
- provider evidence is structurally invalid.

Failure returns a typed decision state rather than fake success.

## Bundle 51 v1 minimum dimensions

Required for the first implementation:

1. tempo fit,
2. phrase/window fit,
3. harmonic fit,
4. energy delta,
5. basic bass/spectral collision risk from available evidence,
6. basic vocal-overlap risk when evidence exists,
7. usable transition window,
8. at least `long_blend`, `short_blend`, `cut`, `drop_swap`, `deliberate_contrast`,
9. structured explanations,
10. deterministic context projection,
11. append-only assessment persistence,
12. safe renderer DTO.

Deferred until justified and benchmarked:

- stem-dependent scoring,
- note-level melodic collision,
- generative transition audio,
- live mixing automation,
- cloud inference,
- learned user weights.

## Acceptance gates

Bundle 51 is not complete until:

- domain contracts are typed and validated,
- deterministic regression fixtures exist,
- half/double-time ambiguity is tested,
- harmonic compatibility is tested across valid/ambiguous/unknown cases,
- hard constraints cannot be bypassed by score,
- missing evidence remains explicit,
- assessment history is append-only,
- renderer DTO contains no path/credential/process authority,
- explanations reference real evidence,
- full Python/Rust/renderer security regression remains green.
