# APPLAYLIST Bundle 51 Runtime Schema Tree

## Status

Implementation boundary for the first runtime slice of Music DNA and Transition Intelligence.

This document implements a narrow subset of the accepted Product Architecture v3 contracts. It does not promote a MIR provider, implement persistence, expose a desktop command, build a set optimizer, or authorize merge/release/deploy.

## Runtime schema

```text
CanonicalAnalysisResult
+ optional RhythmicStructureAnalysis
+ stable track/content/evidence identity
        |
        v
MusicDNARevision                         music-dna-v1
├── MusicDNAIdentity
├── RhythmDNA
│   ├── dominant_bpm
│   ├── explicit half/double tempo-family hypotheses
│   ├── beat_stability
│   ├── percussive_ratio
│   ├── timing_status
│   └── phrase_boundaries_seconds[]
├── TonalDNA
│   ├── key / tonic / scale / Camelot
│   └── confidence + availability state
├── EnergyVector
│   ├── baseline_energy
│   ├── perceived_loudness_db
│   ├── harmonic_ratio
│   └── percussive_ratio
├── MusicSegmentDNA[]
│   └── structural segments when available, otherwise an explicit unknown whole-track region
└── EvidenceRef[]
        |
        v
assess_transition(source segment, target segment, named context)
        |
        v
TransitionAssessment                    transition-assessment-v1
├── TransitionIdentity
├── TransitionCompatibility
│   ├── tempo_fit
│   ├── phrase_fit when evidence exists
│   ├── harmonic_fit
│   ├── groove_continuity when evidence exists
│   └── structural_fit when evidence exists
├── TransitionRisk
│   ├── loudness_discontinuity when evidence exists
│   ├── harmonic_clash when evidence exists
│   ├── phrase_mismatch when evidence exists
│   ├── tempo_instability when evidence exists
│   └── unavailable future risk dimensions remain null
├── TransitionCost
│   └── tempo change / time-stretch cost
├── TransitionEnergyEffect
├── TransitionStrategyCandidate[]
├── TransitionWindow
├── ContextualTransitionProjection
├── structured explanations[]
└── evidence_refs[]
```

## Truth boundary

The runtime must not manufacture evidence merely to fill the target contract.

Current normalized provider evidence can support:

- dominant BPM and deterministic tempo-family relations,
- BPM confidence,
- key/Camelot confidence,
- baseline energy,
- loudness,
- beat stability,
- harmonic/percussive ratios,
- provider/algorithm provenance.

Existing rhythmic-structure evidence can additionally support:

- beat/downbeat availability state,
- phrase boundaries,
- structural segments.

The following dimensions remain explicitly unavailable until a benchmarked provider supplies evidence:

- bass collision,
- vocal collision,
- spectral masking,
- transient overload,
- timbral compatibility,
- melodic compatibility,
- semantic compatibility.

An unavailable value is `None`; it is never replaced by an invented neutral value.

## Whole-track fallback

A track without structural segmentation receives one bounded region:

```text
segment_id = <track_id>:whole
start = 0
end = track duration
structural_label = unknown
status = derived
confidence = unknown
code = whole_track_fallback
```

This is a time-bounds fallback only. It does not claim that the entire track is a musical phrase or valid long-blend window.

## Tempo-family rule

For a measured dominant BPM, v1 preserves the primary value and may add deterministic half-time/double-time hypotheses when they remain inside the canonical 20–400 BPM range.

The original dominant BPM is never rewritten. Transition tempo compatibility searches the explicit family and records a `tempo_family_match` explanation when the best pair uses a derived relation.

## Context projection rule

There is no context-free overall transition score.

The initial named context is:

```text
context_id = preserve-groove
context_version = 1
```

Projection steps:

1. evaluate hard constraints,
2. collect only available compatibility dimensions with non-zero declared weights,
3. calculate the weighted compatibility mean,
4. calculate the mean of available measured/derived risk dimensions,
5. apply the declared context risk penalty,
6. clamp the result to the normalized 0–1 range.

Missing dimensions are excluded rather than silently assigned a neutral score.

Hard-constraint failure produces `score=None` plus explicit `blocked_reasons`.

## Strategy rule

Strategy candidates are bounded by the active context and evidence. V1 does not introduce stems, loops, effects or live-mixing authority.

The initial engine may propose only evidence-compatible members of the accepted strategy vocabulary, primarily:

- cut,
- short blend,
- EQ blend,
- long blend when phrase and harmony evidence support it,
- half/double-time switch when an explicit tempo-family relation supports it,
- deliberate contrast when energy direction supports it.

## Determinism

For identical:

- Music DNA revisions,
- selected segment IDs,
- transition policy version,
- context version,
- explicit created-at value,

`assess_transition` must return an equal immutable value object and the same deterministic `ta_...` transition identifier.

## Security boundary

Music DNA and TransitionAssessment do not expose:

- local filesystem paths,
- sidecar secret/nonce/port,
- process identifiers,
- SQLite handles/queries,
- raw provider exceptions,
- arbitrary provider payloads.

The adapter consumes the existing canonical result but intentionally does not copy its `path` into Music DNA.

## Out of scope

- changing legacy `services/composition/scoring.py`,
- graph/path optimization,
- TransitionAssessment persistence,
- desktop/Tauri commands,
- renderer UI,
- provider promotion or new MIR dependencies,
- automatic stems,
- vocal/semantic/timbral models,
- personal preference learning,
- automatic live mixing,
- release, signing, notarization or deployment.

## Next slice gate

Graph optimization remains blocked until this transition layer has:

- passing deterministic contract tests,
- exact-head CI evidence,
- fail-closed missing-evidence behavior,
- a persistence design for append-only TransitionAssessment edges,
- a bounded ranking/query surface suitable for a set optimizer.
