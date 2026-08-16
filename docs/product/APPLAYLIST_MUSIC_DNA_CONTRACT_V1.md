# APPLAYLIST Music DNA Contract v1

## Status

Proposed domain contract for normalized, provider-independent music intelligence.

This contract defines the shape and invariants required before Bundle 51 Transition Intelligence can treat analysis outputs as decision evidence.

It does not promote any MIR provider to production authority.

## Design goals

Music DNA must be:

- provider-independent,
- immutable by version,
- evidence-backed,
- confidence-aware,
- correction-aware,
- segment-addressable,
- deterministic for identical normalized evidence and contract version,
- safe to expose through bounded read models,
- extensible without silently changing existing semantics.

## Non-goals

Music DNA is not:

- a raw provider payload,
- a mutable metadata bag,
- an LLM-generated free-text description,
- a single embedding vector,
- a single genre label,
- a single energy score,
- direct filesystem authority.

## Canonical identity

```text
MusicDNAIdentity
├── track_id
├── content_identity
├── analysis_revision
├── contract_version
└── evidence_refs[]
```

Invariants:

- `track_id` references an existing canonical track identity,
- `analysis_revision` is immutable once published,
- a new effective analysis creates a new revision rather than rewriting history,
- `contract_version` is explicit,
- source paths are not part of Music DNA.

## Evidence reference

```text
EvidenceRef
├── evidence_id
├── provider_id
├── provider_version
├── algorithm_or_model_id
├── algorithm_or_model_version
├── input_identity
├── observed_at
├── benchmark_status
├── confidence
└── warnings[]
```

Rules:

- provider/model provenance is mandatory for measured or inferred facts,
- missing confidence must be represented as unknown rather than guessed,
- warnings are bounded, sanitized and structured,
- no raw exception, credential, local path, process identity or arbitrary provider object is exposed.

## Confidence contract

```text
Confidence
├── score: 0.0..1.0 | null
├── calibration_state: unknown | uncalibrated | calibrated
├── evidence_count: integer >= 1
└── disagreement: 0.0..1.0 | null
```

A high provider-reported confidence must not be treated as globally calibrated unless benchmark evidence supports it.

## Hypothesis contract

Several musical facts require alternatives rather than a single winner.

```text
Hypothesis<T>
├── value: T
├── confidence
├── evidence_refs[]
└── relation_to_primary
```

Examples of `relation_to_primary`:

- alternative,
- half_time,
- double_time,
- enharmonic,
- neighboring_key,
- ambiguous,
- provider_disagreement.

## Rhythm DNA

```text
RhythmDNA
├── dominant_bpm
├── bpm_hypotheses[]
├── beat_times[]
├── downbeat_times[]
├── bar_boundaries[]
├── meter
├── local_tempo_curve[]
├── tempo_stability
├── swing_ratio
├── groove_descriptors
├── syncopation
├── onset_density_curve[]
├── percussion_density_curve[]
├── confidence
└── evidence_refs[]
```

### BPM invariants

- BPM must be positive and bounded by product policy,
- half/double-time compatible hypotheses remain explicitly linked,
- the canonical DJ interpretation must not destroy alternate tempo-family evidence,
- local tempo may vary independently from dominant BPM.

### Beat/downbeat invariants

- timestamps are monotonic,
- timestamps fall within track duration,
- downbeats must reference valid time positions,
- invalid grids fail closed rather than being silently repaired by UI code.

## Tonal DNA

```text
TonalDNA
├── global_key
├── scale_or_mode
├── camelot
├── open_key
├── key_hypotheses[]
├── tuning_deviation_cents
├── segment_tonality[]
├── modulation_events[]
├── chroma_summary
├── chord_timeline[]
├── harmonic_tension_curve[]
├── dissonance_curve[]
├── confidence
└── evidence_refs[]
```

Rules:

- Camelot/OpenKey are projections, not source truth,
- unknown or ambiguous mode remains explicit,
- chord timeline is optional and provider-gated,
- segment tonality must preserve time bounds and source evidence.

## Acoustic DNA

```text
AcousticDNA
├── loudness
├── peak
├── true_peak
├── rms_curve[]
├── dynamic_range
├── spectral_centroid_curve[]
├── spectral_bandwidth_curve[]
├── spectral_rolloff_curve[]
├── spectral_flatness_curve[]
├── spectral_contrast_summary
├── band_energy_curve[]
├── transient_intensity_curve[]
├── stereo_width_curve[]
├── phase_correlation_curve[]
├── confidence
└── evidence_refs[]
```

Rules:

- unsupported measurements remain null/absent with explicit capability state,
- units are explicit in the typed contract,
- loudness semantics must identify the measurement standard/configuration,
- UI must not compare differently defined loudness values as if they were identical.

## Structure DNA

```text
StructureDNA
├── segments[]
├── phrase_boundaries[]
├── recurrence_regions[]
├── novelty_curve[]
├── candidate_mix_in_windows[]
├── candidate_mix_out_windows[]
├── confidence
└── evidence_refs[]
```

### Segment

```text
MusicSegment
├── segment_id
├── start_ms
├── end_ms
├── role_hypotheses[]
├── phrase_alignment
├── local_rhythm_ref
├── local_tonality_ref
├── local_energy_ref
├── vocal_activity_ref
├── spectral_profile_ref
├── confidence
└── evidence_refs[]
```

Candidate role labels may include:

- intro,
- verse,
- break,
- build,
- pre_drop,
- drop,
- chorus,
- bridge,
- outro,
- unknown.

Labels are hypotheses, not unquestioned truth.

## Vocal DNA

```text
VocalDNA
├── vocal_probability
├── vocal_activity_curve[]
├── vocal_regions[]
├── content_type_hypotheses[]
├── density_curve[]
├── overlap_risk_inputs
├── confidence
└── evidence_refs[]
```

Content type labels such as speech, rap or singing are optional and benchmark-gated.

## Semantic DNA

```text
SemanticDNA
├── genre_probabilities[]
├── style_probabilities[]
├── mood_probabilities[]
├── instrumentation_probabilities[]
├── production_character[]
├── acoustic_electronic_axis
├── era_hypotheses[]
├── confidence
└── evidence_refs[]
```

Rules:

- multi-label by default,
- no hard genre is required,
- taxonomies are versioned,
- unknown and out-of-taxonomy are first-class states,
- labels do not become provider-independent truth until normalized into a named taxonomy.

## Energy Vector

```text
EnergyVector
├── perceived_loudness
├── transient_intensity
├── rhythmic_density
├── percussion_density
├── bass_pressure
├── spectral_brightness
├── vocal_activity
├── melodic_density
├── harmonic_tension
├── dynamic_range
├── build_drop_intensity
├── repetition_hypnosis
├── aggression
├── trajectory[]
├── projection_score
├── projection_version
├── confidence
└── evidence_refs[]
```

Rules:

- vector dimensions are canonical inputs,
- `projection_score` is optional UI convenience,
- projection formula/version must be explicit,
- changing the projection does not rewrite the underlying vector.

## Similarity representation

Similarity is multi-axis.

```text
SimilarityVector
├── rhythmic
├── tonal
├── melodic
├── timbral
├── spectral
├── structural
├── energy
├── mood
├── vocal
├── groove
├── contextual_projection
├── projection_version
└── evidence_refs[]
```

No overall similarity value may be used without a named context/projection version.

## Consensus representation

```text
ConsensusFact<T>
├── primary
├── hypotheses[]
├── confidence
├── disagreement
├── consensus_policy_version
├── evidence_refs[]
└── correction_ref | null
```

Consensus policy must be deterministic and versioned.

## Human correction overlay

Human correction does not mutate provider evidence.

```text
HumanCorrection
├── correction_id
├── track_id
├── field
├── value
├── reason
├── actor
├── source_evidence_ref
├── created_at
└── supersedes_correction_id | null
```

The effective read model may overlay the latest valid correction while preserving complete history.

## Bounded renderer DTO

Renderer-facing Music DNA is a projection, not the domain object.

It may contain:

- safe identifiers,
- values,
- confidence,
- alternatives,
- warnings,
- bounded explanation tokens,
- evidence IDs.

It must not contain:

- filesystem paths,
- sidecar secret/nonce/port,
- process identifiers,
- SQL or repository internals,
- raw provider exceptions,
- arbitrary model payloads.

## Versioning

Changes are classified as:

### Compatible

- adding optional fields,
- adding new semantic labels to a new taxonomy version,
- adding provider evidence that does not change existing field semantics.

### Breaking

- changing units,
- changing field meaning,
- changing normalization range,
- changing required invariants,
- changing consensus interpretation without a new policy version.

Breaking changes require a new contract version and migration/read compatibility plan.

## Bundle 51 minimum usable subset

Transition Intelligence v1 does not require every future Music DNA field.

Required minimum:

- stable track identity,
- duration,
- dominant BPM + tempo-family alternatives,
- beat/downbeat or phrase-compatible timing evidence,
- key/Camelot + confidence,
- scalar baseline energy plus versioned normalized components where available,
- segment/mix-window representation,
- basic spectral/bass/vocal risk inputs where benchmarked,
- provider/evidence references,
- human correction overlay.

Everything else may remain optional until benchmarked and product-justified.
