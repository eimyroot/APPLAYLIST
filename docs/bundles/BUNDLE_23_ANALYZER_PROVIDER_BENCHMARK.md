# Bundle 23 — Analyzer Provider Layer + MIR Benchmark Harness

## Intent
This bundle introduces a safe extension point for multiple audio analysis providers.

## Included
- `core/analysis/providers.py`
- `core/analysis/benchmark.py`
- `scripts/benchmark_analysis.py`
- `tests/unit/test_analysis_providers.py`

## Design rules
- `librosa` remains the default/safe provider
- `Essentia` is optional and disabled by default
- no hard dependency on Essentia in baseline installs
- benchmark harness is additive and non-destructive

## Why
This creates the foundation for:
- comparative benchmarking
- runtime profiling
- future quality scoring against MIR-style evaluation tasks
- optional advanced providers without polluting baseline installs

## Notes
Essentia is intentionally protected behind `APPLAYLIST_ENABLE_ESSENTIA=1`
because it should not become an accidental hard dependency.
