# Bundle 46 — MIR Benchmark Harness

## Status

Implemented on an isolated feature branch. Not yet merged and not a production-provider approval.

## Goal

Measure APPLAYLIST music-analysis providers using reproducible DJ-relevant evidence rather than unit tests or marketing claims.

## Schema Tree

```text
DatasetManifest
├── dataset identity/version/source/license/checksum
├── absolute external dataset root
├── manifest SHA-256
└── BenchmarkItem[]
    ├── stable item ID
    ├── contained relative audio path
    └── BenchmarkReference
        ├── BPM + accepted alternates
        ├── tonic/scale/Camelot
        └── ordinal energy rank
            ↓
MIRBenchmarkRunner
├── runtime containment revalidation
├── RoutedAnalysisService
├── BenchmarkResultRow per attempted item
│   ├── success
│   ├── controlled failure
│   └── uncontrolled failure
├── BPM metrics
│   ├── exact
│   ├── half/double
│   └── miss
├── key metrics
│   ├── exact
│   ├── relative
│   ├── adjacent Camelot
│   └── incompatible
├── energy Spearman rank correlation
├── runtime median + p95
└── BenchmarkReport
    ├── source/provider/environment provenance
    ├── proposed acceptance gates
    └── decision_status=manual_review_required
```

## Key Decisions

- Dataset audio and restricted annotations remain outside the repository.
- The harness performs no download or network request.
- Manifest and dataset paths must be absolute at the operator boundary.
- Item paths must remain inside the explicit dataset root.
- Duplicate item IDs and paths fail closed.
- Provider failures produce rows and affect aggregate reliability.
- Half/double-tempo equivalence is represented explicitly.
- Energy is evaluated as an ordinal ranking, not an absolute universal truth.
- Report output is deterministic when generated timestamp, environment and inputs are fixed.
- Acceptance gates are evidence only; they do not automatically activate a provider.

## Safety Boundaries

- no production database write,
- no API or worker activation,
- no provider-default switch,
- no committed audio,
- no secret or remote credential,
- atomic report write,
- source containment checked during manifest load and again immediately before analysis,
- uncontrolled exceptions are visible and fail the reliability gate.

## Operator Flow

```text
prepare licensed external dataset
  → create versioned manifest
  → run scripts/run_mir_benchmark.py
  → inspect per-track failures
  → inspect aggregate gates
  → run human DJ review
  → create provider decision ADR
```

See `docs/operations/MIR_BENCHMARK_OPERATOR_GUIDE.md`.

## Verification Requirements

- manifest validation and containment tests,
- duplicate ID/path rejection,
- BPM classification tests,
- Camelot relationship tests,
- energy rank-correlation tests,
- controlled provider-failure retention,
- deterministic JSON serialization,
- real synthetic-audio end-to-end harness test,
- existing compatibility helper tests,
- Python 3.11 and 3.12 full CI.

## Explicitly Out of Scope

- downloading GiantSteps or other datasets,
- committing benchmark audio,
- approving Librosa as production-authoritative,
- adding Essentia,
- measuring full private collection in CI,
- human transition evaluation,
- persistence migration,
- desktop UI.

## Rollback

Before merge, close the pull request. After an isolated squash merge, revert one commit. No data rollback is required.

## Next Decision

A provider decision can only follow real licensed dataset runs, private DJ evaluation, runtime/memory evidence, human review and license approval.

The desktop-shell planning issue may use IPTVnator as an architectural reference for typed host capabilities, release packaging and desktop/PWA separation, but no desktop implementation begins in this bundle.
