# APPLAYLIST Product Architecture v3

## Status

Proposed governed architecture for the post-Bundle-50 product direction.

This document does not authorize a provider promotion, merge, release, deployment, cloud processing, model download, or production effect. It defines the target product structure that subsequent bundles must implement and verify.

## Product thesis

APPLAYLIST is a local-first, explainable Music Intelligence platform for DJs first and producers later.

Its core value is not detecting isolated metadata such as BPM or key. Its value is converting evidence-backed music analysis into practical, inspectable decisions:

```text
understand
  -> explain
  -> compare
  -> decide
  -> prepare
  -> export
  -> learn from explicit human choices
```

The product must remain interoperable with the DJ tools the artist already uses. It is not a DAW, live performance engine, streaming service, social network, or generic AI-chat product.

## Strategic product boundary

### Primary user

A DJ preparing a local music library and an intentional set.

### Primary problem

Given a local library and a desired musical trajectory, determine:

- which tracks fit next,
- which sections of those tracks are compatible,
- what transition strategies are plausible,
- what musical risks exist,
- how a recommendation changes energy and narrative,
- why the system recommends one option over another.

### Later user

A producer using the same Music DNA and evidence contracts for arrangement, tonal, mix and reference analysis.

Producer functionality must not delay the DJ release path.

## Canonical product pipeline

```text
LOCAL AUDIO
   |
   v
IDENTITY + INTEGRITY
   |
   v
ANALYSIS PROVIDERS
   |
   v
NORMALIZED MUSIC FACTS
   |
   v
MUSIC DNA
   |
   v
SEGMENTS / PHRASES
   |
   v
TRANSITION GRAPH
   |
   +--------------------+
   |                    |
   v                    v
PERSONAL CONTEXT     SET CONSTRAINTS
   |                    |
   +----------+---------+
              |
              v
      SET PATH OPTIMIZER
              |
              v
    EXPLAINABLE DECISION
              |
              v
        HUMAN EDIT
              |
              v
          EXPORT
              |
              v
    EXPLICIT FEEDBACK
              |
              +-------> preference model
```

## Layer 1 — Library identity and integrity

Responsibilities:

- stable content identity,
- file identity/history,
- supported-format validation,
- duplicate and near-duplicate evidence,
- codec/container/sample-rate/bit-depth/channel metadata,
- bounded corruption/readability checks,
- provenance for imported metadata.

Rules:

- filesystem paths remain host-authority data and must not become generic renderer authority,
- track identity is independent from filename and mutable tags,
- external metadata enrichment must never overwrite measured audio facts without explicit provenance.

## Layer 2 — Analysis Truth Layer

The analysis layer produces typed, normalized facts with confidence and provenance.

Core families:

1. Rhythm DNA
2. Tonal DNA
3. Acoustic DNA
4. Structure DNA
5. Vocal DNA
6. Semantic DNA

A scalar BPM, key, genre, energy or similarity value is not sufficient as the canonical domain model.

### Rhythm DNA

Target contract includes:

- dominant tempo,
- alternative tempo hypotheses,
- confidence,
- beat positions,
- downbeats,
- bars,
- meter,
- local tempo curve,
- tempo stability,
- swing/groove descriptors,
- syncopation/onset/percussion density,
- human correction evidence.

### Tonal DNA

Target contract includes:

- global key,
- scale/mode,
- Camelot/OpenKey projection,
- confidence,
- alternative hypotheses,
- tuning deviation,
- segment-level key,
- modulation evidence,
- normalized chroma/HPCP-like representation,
- chord timeline when an approved provider exists,
- harmonic tension/dissonance descriptors.

### Acoustic DNA

Target contract includes:

- loudness evidence,
- peak/true-peak evidence where supported,
- RMS/dynamic profile,
- spectral centroid/bandwidth/rolloff/flatness/contrast,
- low/mid/high energy distribution,
- transient profile,
- stereo/phase descriptors where reliable,
- feature confidence and provider provenance.

### Structure DNA

Target contract includes:

- section boundaries,
- phrase boundaries,
- repeated regions,
- novelty/change evidence,
- intro/outro/build/break/drop-like labels as hypotheses rather than unquestioned truth,
- candidate mix-in and mix-out regions.

### Vocal DNA

Target contract includes:

- vocal/instrumental probability,
- vocal activity timeline,
- lead/background or speech/rap/singing labels only when benchmarked,
- vocal overlap/clash inputs for transition analysis.

### Semantic DNA

Semantic analysis is probabilistic and multi-label.

It may include:

- genre/subgenre probabilities,
- mood/atmosphere,
- production character,
- instrumentation,
- acoustic/electronic descriptors,
- stylistic descriptors such as hypnotic, driving, broken, rolling or industrial.

It must not collapse the canonical track identity into a single hard genre label.

## Layer 3 — Analysis Consensus

No single provider owns truth merely because it is configured as default.

The consensus layer reconciles compatible hypotheses from one or more approved providers.

Example:

```text
provider A -> 174.03 BPM @ 0.72
provider B ->  87.01 BPM @ 0.91
provider C -> 174.02 BPM @ 0.95

canonical tempo family -> 87.01 / 174.02
DJ interpretation       -> 174.02
confidence              -> high
reason                  -> half/double-time family agreement
```

Consensus must preserve:

- all source evidence,
- provider version,
- model/algorithm provenance,
- alternatives,
- warnings,
- benchmark status,
- human correction history.

Consensus never deletes provider evidence.

## Layer 4 — Music DNA

Music DNA is the normalized product representation used by ranking and transition logic.

It is provider-independent.

```text
MusicDNA
├── identity
├── rhythm
├── tonal
├── acoustic
├── structure
├── vocal
├── semantic
├── energy_vector
├── embeddings/reference representations
├── confidence_summary
└── provenance_refs
```

### Energy Vector

Energy is multi-dimensional rather than a single 1–10 score.

Candidate dimensions:

- perceived loudness,
- transient intensity,
- rhythmic density,
- kick/percussion density,
- bass pressure,
- spectral brightness,
- vocal activity,
- melodic density,
- harmonic tension,
- dynamic range,
- build/drop intensity,
- repetition/hypnosis,
- aggression,
- time-varying energy curve.

A compact scalar may be derived for UI convenience, but the vector is the decision input and the scalar must remain explainable.

## Layer 5 — Segment model

Transition decisions operate on musical regions, not only whole tracks.

```text
Track
  -> Segment[]
      -> Phrase[] / candidate mix windows
```

Each segment may reference:

- time range,
- phrase/bar alignment,
- local tempo,
- local tonal state,
- energy state,
- vocal activity,
- spectral/bass profile,
- structural role,
- confidence/provenance.

## Layer 6 — Transition Intelligence

This is the primary differentiation layer.

A transition is modeled as an immutable assessment edge between a source region and a target region.

```text
Track A / Segment A
        |
        v
TransitionAssessment
        |
        v
Track B / Segment B
```

Canonical assessment dimensions:

- tempo fit,
- beat/grid fit,
- phrase fit,
- harmonic fit,
- bass collision risk,
- vocal collision risk,
- spectral masking risk,
- loudness discontinuity,
- groove continuity,
- energy delta,
- structural fit,
- melodic collision risk where evidence exists,
- time-stretch cost,
- key-shift cost,
- usable mix-window length,
- confidence,
- evidence references.

Transition strategy candidates may include:

- long blend,
- short blend,
- EQ blend,
- bass swap,
- cut,
- drop swap,
- breakdown transition,
- loop transition,
- tempo bridge,
- half/double-time switch,
- stem-assisted transition when stems are available,
- deliberate contrast.

The engine returns a vector plus explanation. A single overall score may exist only as a context-specific projection.

## Layer 7 — Contextual scoring

There is no universal transition score.

Decision function:

```text
transition evidence
+ user goal
+ set context
+ explicit constraints
+ personal preference weights
= contextual recommendation
```

Example contexts:

- hypnotic warehouse / preserve groove,
- peak-time / increase impact,
- warm-up / avoid abrupt energy growth,
- UK bass -> techno bridge,
- harmonic long blend,
- deliberate contrast.

Context weights must be versioned and inspectable.

## Layer 8 — Set Intelligence

The set builder is a graph/path optimizer over tracks, segments and TransitionAssessment edges.

Inputs:

- eligible library scope,
- required/forbidden tracks,
- locks,
- target duration,
- BPM/tempo constraints,
- energy trajectory,
- style/genre constraints,
- key/harmonic risk policy,
- novelty/repetition policy,
- personal preference profile.

Outputs:

- ordered set path,
- selected transition windows,
- alternatives,
- explanations,
- unresolved risks,
- evidence references.

The optimizer must remain deterministic for identical inputs, configuration and provider evidence unless an explicitly versioned stochastic mode is enabled.

## Layer 9 — Personal DJ Model

Personalization learns preference weights from explicit product interactions, not hidden destructive mutation of measured facts.

Candidate signals:

- accepted recommendation,
- rejected recommendation,
- manually selected alternative,
- changed cue/transition region,
- corrected analysis value,
- locked/replaced/reordered track,
- explicit transition rating,
- imported performance-history signal only with explicit user authorization.

Personal model may learn:

- preferred energy trajectories,
- harmonic-risk tolerance,
- preferred transition duration,
- tempo movement tolerance,
- genre/style bridges,
- vocal-overlap tolerance,
- low-end continuity preferences,
- transition-strategy preferences,
- novelty vs consistency.

Rules:

- original analysis evidence is immutable,
- human corrections are append-only evidence,
- preference learning changes ranking, not historical facts,
- privacy remains local-first by default.

## Layer 10 — Explainability

Every recommendation must be able to answer:

- why this track,
- why this segment,
- why this transition strategy,
- what risks exist,
- what alternatives were rejected,
- what confidence is based on,
- which measured/provider evidence contributed.

LLMs may translate structured evidence into human-readable language, but they are not the authority for beat, downbeat, key, loudness or other deterministic/specialist MIR facts.

## Layer 11 — Interoperability

Priority:

1. local folders / drag and drop,
2. M3U/M3U8,
3. JSON evidence,
4. rekordbox XML where contractually safe,
5. Traktor NML,
6. additional documented adapters as separate governed slices.

Adapters must preserve approved playlist revisions and must not require proprietary database mutation as the primary strategy.

## Layer 12 — Optional advanced providers

Later capabilities may include:

- stems,
- note/pitch transcription,
- audio-to-MIDI,
- chord timelines,
- semantic embeddings,
- higher-cost local GPU models,
- explicitly approved optional cloud inference.

These capabilities are provider extensions, not the identity of APPLAYLIST.

## Runtime architecture

The accepted desktop boundary remains:

```text
React / TypeScript renderer
        |
        | typed Tauri commands/events
        v
Tauri Rust desktop core
        |
        | authenticated loopback
        v
Packaged Python sidecar
        |
        v
Application services
        |
        +---- provider registry
        |
        +---- repository boundary
```

No Music Intelligence feature is allowed to bypass existing host-authority, sidecar-authentication or repository boundaries.

## DevOps / ML governance

Every analysis provider must move through:

```text
RESEARCHED
  -> LICENSE_REVIEWED
  -> BENCHMARKED
  -> SECURITY_REVIEWED
  -> HUMAN_REVIEWED
  -> APPROVED
  -> PRODUCTION_ELIGIBLE
```

Production eligibility is separate from benchmark accuracy.

Required decision dimensions:

- accuracy,
- calibration/confidence quality,
- robustness,
- runtime performance,
- memory/artifact cost,
- reproducibility,
- privacy behavior,
- license/model/data provenance,
- rollback capability.

## Product moat

The intended defensible assets are:

1. segment-level Transition Graph,
2. explainable contextual decision model,
3. Personal DJ preference model,
4. provider-independent Music DNA contract,
5. append-only human corrections and evidence history,
6. benchmark/licensing governance that allows safe provider replacement.

## Explicit non-goals for the DJ release path

Do not prioritize before the core release:

- full DAW functionality,
- live performance/mixing engine,
- broad controller/hardware support,
- streaming service,
- social network,
- proprietary catalog scraping,
- generic AI chat as the primary product surface,
- music generation,
- cloud-only analysis,
- stems as the principal product identity.

## Required implementation order

1. close Bundle 50 desktop analysis transport,
2. define Music DNA + TransitionAssessment contracts,
3. implement Transition Intelligence v1,
4. implement graph-based Explainable Set Builder,
5. complete manual editor and export release slice,
6. add preference learning after explicit feedback evidence exists,
7. add advanced semantic/stem/producer capabilities only behind provider governance.

## Acceptance rule

A new feature belongs in APPLAYLIST only if it improves at least one of:

- music understanding,
- decision quality,
- explainability,
- workflow interoperability,
- user control,
- evidence quality,
- provider replaceability,

without weakening privacy, auditability, bounded authority or product focus.
