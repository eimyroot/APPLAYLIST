# Bundle 45 — Baseline Librosa MIR Provider

## Status

Implemented on an isolated feature branch. Not yet merged or production-authoritative.

## Product Goal

Replace the Librosa stub with a real local baseline analyzer that produces versioned BPM, key/Camelot, energy and confidence evidence suitable for Bundle 46 benchmarking.

This bundle proves a working analysis path. It does not prove commercial-analyzer parity or production accuracy.

## Schema Tree

```text
APPLAYLIST
└── Track intelligence
    ├── RoutedAnalysisService
    │   ├── provider selection
    │   ├── controlled provider failure mapping
    │   └── canonical result normalization
    │
    └── LibrosaAnalyzerProvider
        ├── lazy BaselineLibrosaMIR import
        ├── no database write
        └── BaselineLibrosaMIR
            ├── absolute regular-file validation
            ├── local mono decode @ 22 050 Hz
            ├── finite/duration/silence guards
            ├── harmonic-percussive separation
            ├── onset envelope + beat tracking
            ├── BPM
            ├── beat stability
            ├── internal BPM confidence
            ├── CQT chroma
            │   └── STFT fallback with warning
            ├── 24 tonic/mode profile scoring
            ├── tonic + scale + Camelot
            ├── internal tonal confidence
            ├── RMS dBFS
            ├── harmonic/percussive ratios
            ├── relative energy components
            ├── provider + algorithm provenance
            └── warnings
                ↓
        normalize_provider_result
                ↓
        CanonicalAnalysisResult
```

## Runtime Flow

```text
absolute local audio path
  → explicit provider selection
  → lazy Librosa import
  → local decode
  → deterministic feature extraction
  → raw provider evidence
  → fail-closed canonical normalization
  → CanonicalAnalysisResult
```

No API route, worker, database repository or composition authority is switched to this provider by Bundle 45.

## Canonical Evidence

The canonical result preserves current compatibility and adds explicit evidence:

```text
key                 existing composition-compatible value
key_tonic           tonic, for example C
key_scale           major or minor
camelot             for example 8B
key_confidence      bounded internal tonal confidence
bpm                 estimated tempo
bpm_confidence      bounded internal beat confidence
beat_stability      interval-consistency evidence
energy              provider-relative 0..1 score
loudness_db         RMS dBFS evidence
harmonic_ratio      normalized harmonic power share
percussive_ratio    normalized percussive power share
provider_version    resolved Librosa version
algorithm_version   baseline-librosa-mir-v1
warnings             controlled limitations/fallback evidence
```

## Algorithm Decisions

### Tempo

- Beat tracking runs on the percussive component and onset envelope.
- Confidence combines beat-interval stability, expected-beat coverage and onset strength.
- Half/double-tempo ambiguity is not silently corrected in this bundle; Bundle 46 evaluates it against reference data.

### Key

- Harmonic chroma is preferred.
- CQT chroma is used for normal-length audio.
- STFT chroma is the controlled fallback.
- Twenty-four major/minor key hypotheses are scored with tonal profiles.
- Camelot is derived from tonic and mode.
- Confidence is an internal relative measure based on absolute fit and winner margin.

### Energy

Energy is a relative provider-specific score combining:

- RMS loudness component,
- percussive power ratio,
- onset activity,
- spectral brightness,
- RMS dynamics.

It is not a universal physical energy value. Bundle 46 must measure ranking usefulness against DJ annotations.

## Safety Boundaries

- Input must be an absolute path to an existing regular file.
- Analysis is local and performs no network upload.
- Optional audio dependencies remain off mandatory boot paths.
- Empty, silent, non-finite or undecodable audio fails in a controlled provider boundary.
- Provider output is normalized and bounded before acceptance.
- Provider code performs no database write.
- No quality or production-default claim is made before benchmark review.

## Verification Scope

Synthetic-audio tests prove:

- real WAV decoding,
- tempo evidence including half/double-compatible tolerance,
- duration,
- key/scale/Camelot output,
- bounded confidence and energy,
- loudness and harmonic/percussive evidence,
- deterministic repeated output,
- silence rejection,
- lazy import,
- malformed Camelot/warning payload rejection.

Synthetic tests prove software behavior, not accuracy on real DJ music.

## Explicitly Out of Scope

- provider persistence,
- API or desktop activation,
- worker/job wiring,
- production-default selection,
- automatic beatgrid correction,
- downbeat, phrase, section or cue-point detection,
- genre classification,
- embeddings or pretrained models,
- Essentia activation,
- claims of parity with Mixed In Key, Rekordbox or other commercial analyzers.

## Rollback

Before merge, close the pull request without changing the canonical branch.

After an isolated squash merge, revert that one merge commit. No data rollback is required because Bundle 45 introduces no database writes or migration.

## Next Slice

```text
Bundle 46 — MIR Benchmark Harness
  ├── licensed dataset manifests
  ├── decode reliability
  ├── BPM exact + half/double metrics
  ├── exact and Camelot-compatible key metrics
  ├── energy rank correlation
  ├── runtime and memory evidence
  ├── human DJ review
  └── provider decision report
```
