# APPLAYLIST Rhythmic Beat-Grid Shadow Evidence v1

## Status

This document records CANONICAL R3 / WB006C on local baseline
`778743ede4b5c8ac88dd1eaa6a0959e6ad38a48e`.

The earlier R2 rhythm design at `a2d35146959e2a195a869ef04351579283297b31` is a reviewed design
donor only. Its Git history is divergent from the current local canonical development line and is not
merged, rebased, fetched, or granted authority by this work block.

Runtime authority remains unchanged:

- `RUNTIME_AUTHORITY=NONE`
- `TRANSITION_INTELLIGENCE_ACTIVATION=NONE`
- `WB006D=HOLD`

## Current baseline reality

The current `services.analysis.analyzer.AudioAnalyzer` calls `librosa.beat.beat_track`, but discards the
returned beat frames and persists its scalar `AnalysisRecord` through `AnalysisRepository`.

WB006C must therefore not call `AudioAnalyzer` as its shadow extraction path. Doing so would create a
persistence side effect and would still not expose beat timestamps.

## WB006C boundary

WB006C adds three isolated concepts:

1. immutable beat-grid evidence contracts,
2. an explicit-only Librosa shadow beat-grid analyzer that reads one audio file and performs no DB/API
   write or provider registration,
3. a pure reconciliation receipt comparing canonical scalar BPM evidence with independent shadow BPM
   evidence, including half-time and double-time relationships.

No existing runtime module imports the shadow analyzer or reconciliation service.

## Canonical scalar evidence

`CanonicalTempoEvidence` adapts an existing `AnalysisRecord` plus explicit `ProviderMetadata` into a
small immutable comparison contract. Missing canonical BPM confidence remains `None`; WB006C never
fabricates it.

The current baseline mapping is:

- provider identity/version: `ProviderMetadata`,
- algorithm identity: `AnalysisRecord.extractor_name`,
- source analysis version: `AnalysisRecord.analysis_version`,
- BPM/confidence/duration: existing `AnalysisRecord` values.

## Shadow evidence

`LibrosaBeatGridShadowAnalyzer` is not registered in provider selection. It is invoked only by an
explicit caller or test.

Its output rules are:

- beat timestamps are derived from Librosa beat frames,
- per-beat and tempo confidence are explicit deterministic heuristics derived from onset strength,
  interval stability, and beat coverage,
- those confidence values are marked uncalibrated and must not be interpreted as benchmark-approved,
- downbeat state is `unknown`,
- meter is unavailable,
- silence or insufficient evidence returns `UNAVAILABLE`, never fabricated values.

## Non-goals

WB006C does not:

- modify `services/analysis/analyzer.py`,
- modify provider registry/selection/orchestration,
- modify API routes, workers, composer, transition scoring, or explainability runtime,
- write analysis records or database state,
- infer downbeats, bars, phrases, sections, vocal activity, or bass activity,
- activate Transition Intelligence,
- change public API or database schemas,
- add a dependency,
- merge or rebase the divergent R2 history.

## Acceptance gate

The slice is acceptable only when local verification proves:

- exact seven-file diff scope,
- Ruff passes for targeted files and repository scope,
- targeted contract/reconciliation/shadow tests pass,
- full pytest regression passes,
- no transition/runtime registration imports are introduced,
- no secret-like material appears in the diff,
- the resulting commit has exactly one parent: the audited baseline SHA.

GitHub Actions are not an authoritative gate for this work block.

## PR isolation

The local source branch is currently ahead of its remote tracking branch. A draft PR is created only if
GitHub already has a branch whose head equals the exact WB006C parent SHA. Otherwise the feature branch
may be pushed, but PR creation remains `HOLD` to avoid presenting unrelated predecessor commits as part
of WB006C.

## Future sequence

1. Collect deterministic synthetic beat-grid evidence.
2. Add licensed real-world annotated benchmark data in a separate evidence work block.
3. Calibrate beat/tempo confidence before granting any runtime authority.
4. Keep WB006D on hold until independent downbeat/phrase acceptance gates exist.
5. Only after explicit authorization may Transition Intelligence consume accepted rhythmic evidence.
