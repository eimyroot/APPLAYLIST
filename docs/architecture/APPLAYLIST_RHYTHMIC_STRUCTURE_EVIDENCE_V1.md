# APPLAYLIST Rhythmic Beat-Grid Shadow Evidence v1

## Status

This document records CANONICAL R3 / WB006C on local baseline
`778743ede4b5c8ac88dd1eaa6a0959e6ad38a48e`.

The earlier R2 rhythm design at `a2d35146959e2a195a869ef04351579283297b31` is a reviewed
design donor only. Its Git history is divergent from the current local canonical development line
and is not
merged, rebased, fetched, or granted authority by this work block.

Runtime authority remains unchanged:

- `RUNTIME_AUTHORITY=NONE`
- `TRANSITION_INTELLIGENCE_ACTIVATION=NONE`
- `WB006D=HOLD`

## Current baseline reality

The current `services.analysis.analyzer.AudioAnalyzer` calls `librosa.beat.beat_track`, but
discards the returned beat frames and persists its scalar `AnalysisRecord` through
`AnalysisRepository`.

WB006C must therefore not call `AudioAnalyzer` as its shadow extraction path. Doing so would
create a persistence side effect and would still not expose beat timestamps.

## WB006C boundary

WB006C adds three isolated concepts:

1. immutable beat-grid evidence contracts,
2. an explicit-only Librosa shadow beat-grid analyzer that reads one audio file and performs no
   DB/API write or provider registration,
3. a pure reconciliation receipt comparing canonical scalar BPM evidence with independent shadow BPM
   evidence, including half-time and double-time relationships.

No existing runtime module imports the shadow analyzer or reconciliation service.

## Canonical scalar evidence

`CanonicalTempoEvidence` adapts an existing `AnalysisRecord`, explicit `ProviderMetadata`, and an
explicit `SourceAudioIdentity` into a small immutable comparison contract. Missing canonical BPM
confidence remains `None`; WB006C never fabricates it.

A bare `AnalysisRecord` is intentionally insufficient for reconciliation because the current
baseline record does not persist source path or source content hash. The caller must supply source
identity that was captured for the canonical analysis input. That identity contains the resolved
path, file size, and SHA-256 digest.

The current baseline mapping is:

- provider identity/version: `ProviderMetadata`,
- algorithm identity: `AnalysisRecord.extractor_name`,
- source analysis version: `AnalysisRecord.analysis_version`,
- BPM/confidence/duration: existing `AnalysisRecord` values,
- source binding: explicit `SourceAudioIdentity` supplied outside the current persistence schema.

## Shadow evidence

`LibrosaBeatGridShadowAnalyzer` is not registered in provider selection. It is invoked only by an
explicit caller or test.

Before decoding, and again immediately after decoding, the analyzer requires the requested file to
match the canonical source identity by resolved path, byte size, and SHA-256 digest. The same source
identity is carried inside `EvidenceProvenance` so reconciliation can reject a beat grid from
another source even when track IDs, durations, or BPM values happen to match.

Its output rules are:

- beat timestamps are derived from Librosa beat frames,
- per-beat and tempo confidence are explicit deterministic heuristics derived from onset strength,
  interval stability, and beat coverage,
- those confidence values are marked uncalibrated and must not be interpreted as benchmark-approved,
- provenance must identify the WB006C Librosa shadow provider, supported 0.10.x provider series,
  algorithm version, method, source analysis version, and exact source identity,
- downbeat state is `unknown`,
- meter is unavailable,
- silence or insufficient evidence returns `UNAVAILABLE`, never fabricated values.

## Non-goals

WB006C does not:

- modify `services/analysis/analyzer.py`,
- modify provider registry/selection/orchestration,
- modify API routes, workers, composer, transition scoring, or explainability runtime,
- write analysis records or database state,
- change the current database schema to persist source identity,
- infer downbeats, bars, phrases, sections, vocal activity, or bass activity,
- activate Transition Intelligence,
- change public API schemas,
- add a dependency,
- merge or rebase the divergent R2 history.

## Acceptance gate

The slice is acceptable only when local verification proves:

- exact seven-file PR scope,
- targeted Ruff passes for every WB006C Python file,
- full-Ruff diagnostics contain zero WB006C findings and exactly match the audited parent-HEAD
  snapshot for all pre-existing baseline findings,
- targeted contract/reconciliation/shadow tests pass, including wrong-source and provenance-negative
  regression tests,
- full pytest regression passes,
- no transition/runtime registration imports are introduced,
- no secret-like material appears in the diff,
- the initial WB006C commit has exactly one parent: the audited baseline SHA,
- corrective commits remain linear descendants of that isolated WB006C commit.

GitHub Actions are not an authoritative gate for this work block.

## PR isolation

The local source branch was ahead of its remote tracking branch when WB006C was prepared. The
draft PR was created only after GitHub exposed a base branch whose head exactly matched the audited
WB006C parent SHA. This prevents unrelated predecessor commits from being presented as part of
WB006C.

Corrective review commits may update the existing WB006C draft branch only by normal fast-forward
push. Force push, rebase, merge, runtime activation, and release remain outside this work block.

## Future sequence

1. Collect deterministic synthetic beat-grid evidence.
2. Add licensed real-world annotated benchmark data in a separate evidence work block.
3. Calibrate beat/tempo confidence before granting any runtime authority.
4. Keep WB006D on hold until independent downbeat/phrase acceptance gates exist.
5. Only after explicit authorization may Transition Intelligence consume accepted rhythmic evidence.
